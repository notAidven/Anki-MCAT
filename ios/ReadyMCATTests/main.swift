// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Offline, deterministic tests for the iOS ladder-generator core (LadderGen.swift).
// These mirror the desktop's pylib/tests/test_readymcat_ladder_gen.py so the
// ported prompt/parser/guardrails are checked against the SAME cases the Python
// source of truth is. The OpenAI call is injectable, so nothing here touches the
// network. Compiled + run standalone on the host by ios/scripts/test-laddergen.sh
// (no Xcode / simulator needed): LadderGen.swift is Foundation-only.

import Foundation

// MARK: - tiny assert harness

var failures = 0
var checks = 0

func check(_ condition: Bool, _ label: String) {
    checks += 1
    if condition {
        print("  ok   \(label)")
    } else {
        failures += 1
        print("  FAIL \(label)")
    }
}

private final class Box<T> { var value: T? }

/// Block on an async op so the async orchestration can be tested from a plain
/// command-line tool (mirrors the Python async-free stub tests).
func runBlocking<T>(_ op: @escaping () async -> T) -> T {
    let sem = DispatchSemaphore(value: 0)
    let box = Box<T>()
    Task { box.value = await op(); sem.signal() }
    sem.wait()
    return box.value!
}

// MARK: - shared fixtures (same as the Python tests)

let QUESTION = "What is the net ATP yield of glycolysis?"
let ANSWER = """
Glycolysis invests 2 ATP in the investment phase at hexokinase and \
phosphofructokinase, then produces 4 ATP and 2 NADH in the payoff phase, \
for a net yield of 2 ATP and 2 NADH.
"""

func context() -> CardContext {
    CardContext(question: QUESTION, answer: ANSWER, source: "", tags: ["#Biochemistry"])
}

func goodLadder() -> [LadderRung] {
    [
        LadderRung(q: "In the investment phase, how many ATP does glycolysis consume?",
                   a: "Glycolysis invests 2 ATP, at hexokinase and phosphofructokinase."),
        LadderRung(q: "In the payoff phase, how many ATP and NADH are produced?",
                   a: "The payoff phase produces 4 ATP and 2 NADH."),
    ]
}

// MARK: - parsing

func testParsing() {
    print("parsing")
    let fenced = "Sure! Here is the ladder:\n```json\n"
        + "[{\"q\": \"q1?\", \"a\": \"a1\"}, {\"q\": \"q2?\", \"a\": \"a2\"}]\n```"
    let parsed = LadderGen.parseLadder(fenced)
    check(parsed == [LadderRung(q: "q1?", a: "a1"), LadderRung(q: "q2?", a: "a2")],
          "parse handles code fences and prose")

    let malformed = "[{\"q\": \"ok?\", \"a\": \"yes\"}, {\"q\": \"no answer\"}, \"junk\", {\"a\": \"no q\"}]"
    check(LadderGen.parseLadder(malformed) == [LadderRung(q: "ok?", a: "yes")],
          "parse drops malformed rungs")

    check(LadderGen.parseLadder("no json here") == nil, "parse returns nil on prose")
    check(LadderGen.parseLadder("") == nil, "parse returns nil on empty")
    check(LadderGen.parseLadder("{\"q\": \"obj not array\"}") == nil, "parse returns nil on non-array")
}

// MARK: - schema

func testSchema() {
    print("schema")
    check(!LadderGen.checkSchema([LadderRung(q: "a", a: "b")]).isEmpty, "schema flags too few rungs")
    let tooMany = Array(repeating: LadderRung(q: "q", a: "a"), count: LadderGen.maxRungs + 1)
    check(!LadderGen.checkSchema(tooMany).isEmpty, "schema flags too many rungs")
    check(LadderGen.checkSchema(goodLadder()).isEmpty, "schema passes a good ladder")

    check(!LadderGen.checkSchema(nil).isEmpty, "schema flags a non-list (nil)")
    let empties = [LadderRung(q: "", a: "x"), LadderRung(q: "y", a: "")]
    let problems = LadderGen.checkSchema(empties)
    check(problems.contains { $0.contains("empty question") }, "schema flags empty question")
    check(problems.contains { $0.contains("empty answer") }, "schema flags empty answer")
}

// MARK: - answer-leak

func testAnswerLeak() {
    print("answer-leak")
    let shortAnswer = "The net yield is 2 ATP and 2 NADH."
    let leakCtx = CardContext(question: QUESTION, answer: shortAnswer)
    let leaky = [
        LadderRung(q: "What is the result?", a: "\(shortAnswer) That is the result."),
        LadderRung(q: "Why?", a: "Because of the payoff phase."),
    ]
    check(LadderGen.checkAnswerLeak(leaky, leakCtx) == true, "leak catches verbatim answer in first rung")
    check(LadderGen.checkAnswerLeak(goodLadder(), context()) == false, "leak allows a scaffolded first rung")
}

// MARK: - grounding

func testGrounding() {
    print("grounding")
    check(LadderGen.groundingScore(goodLadder(), context()) >= LadderGen.groundingMin,
          "grounding high when sub-answers use card material")
    let invented = [
        LadderRung(q: "q1?", a: "Photosynthesis occurs in chloroplast thylakoid membranes."),
        LadderRung(q: "q2?", a: "Rubisco fixes carbon dioxide in the Calvin cycle."),
    ]
    check(LadderGen.groundingScore(invented, context()) < LadderGen.groundingMin,
          "grounding low when sub-answers are invented")
}

// MARK: - validate aggregate

func testValidate() {
    print("validate")
    let result = LadderGen.validateLadder(goodLadder(), context())
    check(result.passed, "validate passes a good ladder")
    check(result.schemaOk, "validate schemaOk on a good ladder")
    check(!result.answerLeak, "validate no leak on a good ladder")
    check(result.grounded, "validate grounded on a good ladder")

    let none = LadderGen.validateLadder(nil, context())
    check(!none.passed, "validate not passed on nil")
    check(!none.schemaOk, "validate schema not ok on nil")
}

// MARK: - generate orchestration (stubbed, offline)

func testGenerate() {
    print("generate")
    let ladderJSON =
        "[{\"q\": \"In the investment phase, how many ATP does glycolysis "
        + "consume?\", \"a\": \"Glycolysis invests 2 ATP, at hexokinase and "
        + "phosphofructokinase.\"}, {\"q\": \"In the payoff phase, how many ATP and "
        + "NADH are produced?\", \"a\": \"The payoff phase produces 4 ATP and 2 "
        + "NADH.\"}]"

    let okOutcome = runBlocking {
        await LadderGen.generateLadder(context(), chat: { messages, _ in
            precondition(messages.first?["role"] == "system")
            return ladderJSON
        })
    }
    check(okOutcome.ok, "generate ok with a valid stub")
    check(okOutcome.attempts == 1, "generate stops after first valid attempt")
    check(okOutcome.validation?.passed == true, "generate outcome validation passed")

    final class Counter { var n = 0 }
    let counter = Counter()
    let failOutcome = runBlocking {
        await LadderGen.generateLadder(context(), chat: { _, _ in
            counter.n += 1
            return "[]"   // empty ladder -> schema fail every attempt
        }, attempts: 2)
    }
    check(!failOutcome.ok, "generate not ok on bad output")
    check(counter.n == 2, "generate retried on bad output")
    check(failOutcome.validation?.schemaOk == false, "generate reports schema failure")

    let errOutcome = runBlocking {
        await LadderGen.generateLadder(context(), chat: { _, _ in
            throw LadderGenError("boom")
        }, attempts: 2)
    }
    check(!errOutcome.ok, "generate not ok on transport error")
    check(errOutcome.error.contains("boom"), "generate records transport error")
}

// MARK: - run

print("LadderGen guardrail port — offline tests")
testParsing()
testSchema()
testAnswerLeak()
testGrounding()
testValidate()
testGenerate()

print("")
if failures == 0 {
    print("LADDERGEN TESTS OK — \(checks) checks passed.")
    exit(0)
} else {
    print("LADDERGEN TESTS FAILED — \(failures)/\(checks) checks failed.")
    exit(1)
}
