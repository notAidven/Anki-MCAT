// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Offline, deterministic tests for the iOS ladder-generator core (LadderGen.swift).
// These mirror the desktop's pylib/tests/test_readymcat_ladder_gen.py so the
// ported prompt/parser/guardrails are checked against the SAME cases the Python
// source of truth is. Each guiding rung is a MULTIPLE-CHOICE question
// ({question, options, correctIndex, explanation}) the student works out by
// choosing. The OpenAI call is injectable, so nothing here touches the network.
// Compiled + run standalone on the host by ios/scripts/test-laddergen.sh (no
// Xcode / simulator needed): LadderGen.swift is Foundation-only.

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

/// Two well-formed MCQ rungs whose correct options + explanations are drawn from
/// the card's own material (so grounding is high) and whose first rung sets up a
/// prerequisite without handing over the answer.
func goodLadder() -> [LadderRung] {
    [
        LadderRung(
            question: "In the investment phase, how many ATP does glycolysis consume?",
            options: ["2 ATP", "4 ATP", "0 ATP"],
            correctIndex: 0,
            explanation: "Glycolysis invests 2 ATP, at hexokinase and phosphofructokinase."),
        LadderRung(
            question: "In the payoff phase, how many ATP and NADH are produced?",
            options: ["2 ATP and 2 NADH", "4 ATP and 2 NADH", "4 ATP and 4 NADH"],
            correctIndex: 1,
            explanation: "The payoff phase produces 4 ATP and 2 NADH."),
    ]
}

// MARK: - parsing

func testParsing() {
    print("parsing")
    let fenced = "Sure! Here is the ladder:\n```json\n"
        + "[{\"question\": \"q1?\", \"options\": [\"a\", \"b\", \"c\"], \"correctIndex\": 0, \"explanation\": \"e1\"}, "
        + "{\"question\": \"q2?\", \"options\": [\"a\", \"b\", \"c\"], \"correctIndex\": 1, \"explanation\": \"e2\"}]\n```"
    check(
        LadderGen.parseLadder(fenced) == [
            LadderRung(question: "q1?", options: ["a", "b", "c"], correctIndex: 0, explanation: "e1"),
            LadderRung(question: "q2?", options: ["a", "b", "c"], correctIndex: 1, explanation: "e2"),
        ],
        "parse handles code fences and prose")

    // good rung + missing-fields + junk + no-question + uninterpretable index -> only the good one survives.
    let malformed = "[{\"question\": \"ok?\", \"options\": [\"a\", \"b\", \"c\"], \"correctIndex\": 0, \"explanation\": \"e\"}, "
        + "{\"question\": \"no options or explanation\"}, "
        + "\"junk\", "
        + "{\"options\": [\"a\", \"b\", \"c\"], \"correctIndex\": 0, \"explanation\": \"no stem\"}, "
        + "{\"question\": \"bad index?\", \"options\": [\"a\", \"b\", \"c\"], \"correctIndex\": \"two\", \"explanation\": \"x\"}]"
    check(
        LadderGen.parseLadder(malformed)
            == [LadderRung(question: "ok?", options: ["a", "b", "c"], correctIndex: 0, explanation: "e")],
        "parse drops malformed rungs")

    // the model sometimes stringifies / floats the index.
    let coerced = "[{\"question\": \"q1?\", \"options\": [\"a\", \"b\", \"c\"], \"correctIndex\": \"1\", \"explanation\": \"e1\"}, "
        + "{\"question\": \"q2?\", \"options\": [\"a\", \"b\", \"c\"], \"correctIndex\": 2.0, \"explanation\": \"e2\"}]"
    check(LadderGen.parseLadder(coerced)?.map { $0.correctIndex } == [1, 2],
          "parse coerces string/float correctIndex")

    check(LadderGen.parseLadder("no json here") == nil, "parse returns nil on prose")
    check(LadderGen.parseLadder("") == nil, "parse returns nil on empty")
    check(LadderGen.parseLadder("{\"question\": \"obj not array\"}") == nil, "parse returns nil on non-array")
}

// MARK: - schema

func testSchema() {
    print("schema")
    check(!LadderGen.checkSchema([goodLadder()[0]]).isEmpty, "schema flags too few rungs")
    let tooMany = Array(repeating: goodLadder()[0], count: LadderGen.maxRungs + 1)
    check(!LadderGen.checkSchema(tooMany).isEmpty, "schema flags too many rungs")
    check(LadderGen.checkSchema(goodLadder()).isEmpty, "schema passes a good ladder")
    check(!LadderGen.checkSchema(nil).isEmpty, "schema flags a non-list (nil)")

    let empties = [
        LadderRung(question: "", options: ["a", "b", "c"], correctIndex: 0, explanation: "x"),
        LadderRung(question: "y", options: ["a", "b", "c"], correctIndex: 0, explanation: ""),
    ]
    let problems = LadderGen.checkSchema(empties)
    check(problems.contains { $0.contains("empty question") }, "schema flags empty question")
    check(problems.contains { $0.contains("empty explanation") }, "schema flags empty explanation")

    let tooFewOpts = [
        LadderRung(question: "q", options: ["only", "two"], correctIndex: 0, explanation: "e"),
        goodLadder()[1],
    ]
    check(LadderGen.checkSchema(tooFewOpts).contains { $0.contains("options") }, "schema flags too few options")

    let emptyOpt = [
        LadderRung(question: "q", options: ["a", "", "c"], correctIndex: 0, explanation: "e"),
        goodLadder()[1],
    ]
    check(LadderGen.checkSchema(emptyOpt).contains { $0.contains("empty option") }, "schema flags empty option")

    let dupOpt = [
        LadderRung(question: "q", options: ["Same", "same", "b"], correctIndex: 0, explanation: "e"),
        goodLadder()[1],
    ]
    check(LadderGen.checkSchema(dupOpt).contains { $0.contains("duplicate") }, "schema flags duplicate options")

    let badIndex = [
        LadderRung(question: "q", options: ["a", "b", "c"], correctIndex: 9, explanation: "e"),
        goodLadder()[1],
    ]
    check(LadderGen.checkSchema(badIndex).contains { $0.contains("correctIndex") },
          "schema flags out-of-range correctIndex")
}

// MARK: - answer-leak

func testAnswerLeak() {
    print("answer-leak")
    let shortAnswer = "The net yield is 2 ATP and 2 NADH."
    let leakCtx = CardContext(question: QUESTION, answer: shortAnswer)
    // The first rung's correct option IS the final answer -> a blatant leak.
    let leaky = [
        LadderRung(question: "What is the result?",
                   options: [shortAnswer, "Only 2 ATP", "Only 2 NADH"],
                   correctIndex: 0,
                   explanation: "That is the net result."),
        goodLadder()[1],
    ]
    check(LadderGen.checkAnswerLeak(leaky, leakCtx) == true, "leak catches verbatim answer in first rung")
    check(LadderGen.checkAnswerLeak(goodLadder(), context()) == false, "leak allows a scaffolded first rung")
}

// MARK: - grounding

func testGrounding() {
    print("grounding")
    check(LadderGen.groundingScore(goodLadder(), context()) >= LadderGen.groundingMin,
          "grounding high when correct options use card material")
    let invented = [
        LadderRung(question: "q1?",
                   options: ["Chloroplast thylakoid membranes", "Cytosol", "Nucleus"],
                   correctIndex: 0,
                   explanation: "Photosynthesis occurs in chloroplast thylakoid membranes."),
        LadderRung(question: "q2?",
                   options: ["Rubisco carboxylation", "Hydrolysis", "Osmosis"],
                   correctIndex: 0,
                   explanation: "Rubisco fixes carbon dioxide in the Calvin cycle."),
    ]
    check(LadderGen.groundingScore(invented, context()) < LadderGen.groundingMin,
          "grounding low when correct options are invented")

    // Distractors are deliberately off-topic; grounding scores only the correct
    // option + explanation, so wild distractors still ground high.
    let wildDistractors = [
        LadderRung(question: "In the investment phase, how many ATP does glycolysis consume?",
                   options: ["2 ATP", "The Krebs cycle in the mitochondria", "Photosystem II"],
                   correctIndex: 0,
                   explanation: "Glycolysis invests 2 ATP, at hexokinase and phosphofructokinase."),
        goodLadder()[1],
    ]
    check(LadderGen.groundingScore(wildDistractors, context()) >= LadderGen.groundingMin,
          "grounding ignores wrong distractors")
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
        "[{\"question\": \"In the investment phase, how many ATP does glycolysis "
        + "consume?\", \"options\": [\"2 ATP\", \"4 ATP\", \"0 ATP\"], \"correctIndex\": 0, "
        + "\"explanation\": \"Glycolysis invests 2 ATP, at hexokinase and "
        + "phosphofructokinase.\"}, {\"question\": \"In the payoff phase, how many ATP "
        + "and NADH are produced?\", \"options\": [\"2 ATP and 2 NADH\", \"4 ATP and 2 "
        + "NADH\", \"4 ATP and 4 NADH\"], \"correctIndex\": 1, \"explanation\": \"The "
        + "payoff phase produces 4 ATP and 2 NADH.\"}]"

    let okOutcome = runBlocking {
        await LadderGen.generateLadder(context(), chat: { messages, _ in
            precondition(messages.first?["role"] == "system")
            // The prompt must ask for the MCQ shape the parser expects.
            precondition(messages.first?["content"]?.contains("correctIndex") == true)
            return ladderJSON
        })
    }
    check(okOutcome.ok, "generate ok with a valid stub")
    check(okOutcome.attempts == 1, "generate stops after first valid attempt")
    check(okOutcome.validation?.passed == true, "generate outcome validation passed")
    check(okOutcome.ladder?.allSatisfy { !$0.options.isEmpty } == true, "generate yields MCQ rungs with options")

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
