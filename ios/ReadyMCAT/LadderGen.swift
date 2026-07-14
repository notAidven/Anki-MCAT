// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Runtime generation of ReadyMCAT teach-on-miss ladders — the iOS port of the
// desktop source of truth `readymcat/tools/ladder_gen.py`. It is a FAITHFUL,
// line-for-line reproduction of that module's public surface: the same prompt
// (`buildMessages`), the same tolerant MCQ parser (`parseLadder`), and the
// same three deterministic guardrails with the same constants —
//   * schema        (MIN_RUNGS…MAX_RUNGS rungs, each an MCQ with a stem,
//                    3-4 distinct options, an in-range correctIndex and an
//                    explanation),
//   * answer-leak   (the first rung must not hand over the final answer), and
//   * grounding     (each rung's correct option + explanation must trace to the
//                    card's own material).
// A generated ladder is shown to the student ONLY when it passes all three; the
// reviewer otherwise falls back to a normal reveal.
//
// The one bit of IO — the model call — is INJECTABLE (`ChatFn`) so the unit
// tests run fully offline and deterministically, exactly like the Python core's
// injectable `chat_fn`. In the app that `ChatFn` is wired to `LadderProxyClient`,
// which POSTs the structured card to the ReadyMCAT Cloudflare Worker that holds
// the OpenAI key SERVER-side (see ios/backend/openai-proxy) — no OpenAI key ever
// ships on the phone. The Worker returns the raw completion text, so the parser
// and the three guardrails below run byte-for-byte unchanged. Keeping the prompt
// + parser + guardrails identical to the desktop means what ships on the phone
// is what the desktop eval harness scores.
//
// Foundation-only (no SwiftUI/UIKit, no app types) so the guardrail logic can be
// compiled and unit-tested standalone on the host (see ios/scripts/test-laddergen.sh).

import Foundation

// MARK: - Tunable, honest-by-intent constants (mirror ladder_gen.py)

enum LadderGen {
    /// Ladders shorter than this teach nothing; longer than this stop being a
    /// "short ladder" and start drilling (the PRD's single-level rule).
    static let minRungs = 2
    static let maxRungs = 4

    /// Each guiding MCQ rung offers this many options. A stem with fewer than
    /// three choices barely tests retrieval; more than four is noise for a
    /// scaffold rung. (Mirrors ladder_gen.MIN_OPTIONS / MAX_OPTIONS.)
    static let minOptions = 3
    static let maxOptions = 4

    /// A rung's correct option + explanation is considered grounded when at
    /// least this fraction of its content words appear in the card's own
    /// material (question + answer + source). A lexical containment proxy for
    /// "traces to a named source". Distractors are intentionally wrong, so
    /// grounding scores the correct answer + explanation only.
    static let groundingMin = 0.5

    /// The FIRST rung must not already contain most of the final answer's
    /// content words in its stem/correct option — otherwise the ladder reveals
    /// the answer instead of scaffolding toward it.
    static let answerLeakMax = 0.7

    /// Cheap, capable default (matches the desktop DEFAULT_MODEL). The model +
    /// temperature are now applied SERVER-side by the proxy Worker; these mirror
    /// its defaults so the documented contract and the UI stay in sync.
    static let defaultModel = "gpt-4o-mini"
    static let defaultTimeoutSecs = 30
    static let defaultAttempts = 2
    static let defaultTemperature = 0.4

    /// Short, deliberately generic stopword set — enough to stop the lexical
    /// proxies keying on filler words, without pretending to be real NLP.
    /// (Verbatim from ladder_gen._STOPWORDS.)
    static let stopwords: Set<String> = Set(
        """
        the a an and or but if then than that this these those of to in on at for
        with without from by as is are was were be been being it its it's do does
        did done have has had having will would can could should may might must
        not no yes into onto over under about above below between which who whom
        whose what when where why how each any all both some such more most other
        another one two three you your they them their he she his her we our us
        """
        .split(whereSeparator: { $0 == " " || $0 == "\n" }).map(String.init)
    )
}

// MARK: - Card context (grounding material for one card)

/// The grounding material for one card, extracted from its fields. Mirrors
/// `ladder_gen.CardContext`.
struct CardContext {
    let question: String
    let answer: String
    let source: String
    let tags: [String]

    init(question: String, answer: String, source: String = "", tags: [String] = []) {
        self.question = question.trimmingCharacters(in: .whitespacesAndNewlines)
        self.answer = answer.trimmingCharacters(in: .whitespacesAndNewlines)
        self.source = source.trimmingCharacters(in: .whitespacesAndNewlines)
        self.tags = tags
    }

    /// True when the card cites a real source; otherwise generation is grounded
    /// on the card's own answer text only.
    var hasSource: Bool { !source.isEmpty }

    /// All material a sub-answer is allowed to draw on.
    var groundingText: String {
        [question, answer, source].filter { !$0.isEmpty }.joined(separator: "\n")
    }
}

/// One rung of a generated ladder: an interactive multiple-choice question the
/// student *works out* by choosing. Mirrors the desktop MCQ rung shape
/// `{question, options, correctIndex, explanation}`; the reviewer renders it as
/// a selectable choice list with correct/incorrect feedback + explanation.
struct LadderRung: Equatable, Identifiable {
    let id = UUID()
    let question: String
    let options: [String]
    let correctIndex: Int
    let explanation: String

    static func == (lhs: LadderRung, rhs: LadderRung) -> Bool {
        lhs.question == rhs.question && lhs.options == rhs.options
            && lhs.correctIndex == rhs.correctIndex && lhs.explanation == rhs.explanation
    }
}

/// Outcome of running the deterministic guardrails over a ladder. Mirrors
/// `ladder_gen.ValidationResult`.
struct ValidationResult {
    let schemaProblems: [String]
    let answerLeak: Bool
    let groundingScore: Double

    var schemaOk: Bool { schemaProblems.isEmpty }
    var grounded: Bool { groundingScore >= LadderGen.groundingMin }

    /// Schema + no-leak + grounded are all hard gates, so a ladder shown to a
    /// student is always well-formed, retrieval-first and traceable.
    var passed: Bool { schemaOk && !answerLeak && grounded }
}

// MARK: - lexical helpers (pure)

extension LadderGen {
    /// Lowercased content words (>= 3 chars, non-stopword) from `text`.
    /// Matches Python's `[a-z0-9]+` tokenizer + the >= 3 / stopword filter.
    static func contentTokens(_ text: String) -> Set<String> {
        var tokens = Set<String>()
        var current = String.UnicodeScalarView()
        func flush() {
            if !current.isEmpty {
                let tok = String(current)
                if tok.count >= 3 && !stopwords.contains(tok) { tokens.insert(tok) }
                current = String.UnicodeScalarView()
            }
        }
        for scalar in text.lowercased().unicodeScalars {
            let v = scalar.value
            let isLower = v >= 97 && v <= 122   // a-z
            let isDigit = v >= 48 && v <= 57    // 0-9
            if isLower || isDigit {
                current.append(scalar)
            } else {
                flush()
            }
        }
        flush()
        return tokens
    }

    /// Fraction of `part`'s content words that also appear in `whole`.
    /// Asymmetric on purpose ("how much of A is covered by B"). Returns 0.0 when
    /// `part` has no content words.
    static func containment(_ part: String, _ whole: String) -> Double {
        let partTokens = contentTokens(part)
        if partTokens.isEmpty { return 0.0 }
        let wholeTokens = contentTokens(whole)
        return Double(partTokens.intersection(wholeTokens).count) / Double(partTokens.count)
    }
}

// MARK: - prompt + parsing

extension LadderGen {
    /// The chat messages sent to the model. Byte-for-byte the same prompt as
    /// `ladder_gen.build_messages`, so the phone generates what the desktop
    /// eval harness scores.
    static func buildMessages(_ context: CardContext) -> [[String: String]] {
        let system =
            "You are a tutor for the MCAT. A student just answered a question "
            + "WRONG. Do NOT reveal the answer outright. Instead, write a short "
            + "ladder of guiding MULTIPLE-CHOICE questions that make the student "
            + "WORK IT OUT by choosing (active retrieval, not passive reading).\n\n"
            + "Hard rules:\n"
            + "- Output \(minRungs)-\(maxRungs) rungs, ordered from foundational to "
            + "the step just before the answer; the LAST rung should lead the student "
            + "to recall the final answer themselves.\n"
            + "- Each rung is one multiple-choice question with a short stem "
            + "('question'), \(minOptions)-\(maxOptions) answer 'options', a "
            + "'correctIndex' (0-based index of the correct option), and a one-line "
            + "'explanation' of why that option is correct.\n"
            + "- The FIRST rung must NOT state or give away the final answer; it "
            + "establishes a prerequisite idea.\n"
            + "- Distractors must be plausible but clearly WRONG given the material; "
            + "options must be distinct.\n"
            + "- Every stem, option, correct answer and explanation must be grounded "
            + "ONLY in the provided material — do not introduce facts that are not "
            + "supported by it.\n"
            + "Return ONLY a JSON array: [{\"question\": \"...\", \"options\": [\"...\", "
            + "\"...\", \"...\"], \"correctIndex\": 0, \"explanation\": \"...\"}, ...] with no "
            + "prose, no markdown, no code fences."

        var parts = ["QUESTION THE STUDENT MISSED:\n\(context.question)"]
        if !context.answer.isEmpty {
            parts.append(
                "\nCORRECT ANSWER / EXPLANATION (for your reference only, "
                + "do NOT reveal it directly):\n\(context.answer)")
        }
        if !context.source.isEmpty {
            parts.append("\nCITED SOURCE MATERIAL:\n\(context.source)")
        }
        parts.append(
            "\nWrite the \(minRungs)-\(maxRungs) guiding multiple-choice questions "
            + "now as the JSON array described.")

        return [
            ["role": "system", "content": system],
            ["role": "user", "content": parts.joined(separator: "\n")],
        ]
    }

    /// Extract a multiple-choice ladder from a model completion. Tolerant of
    /// code fences / stray prose around the JSON. Returns a normalized list of
    /// MCQ rungs, or `nil` when nothing parseable is found. Structurally
    /// malformed rungs are dropped rather than crashing. Mirrors
    /// `ladder_gen.parse_ladder`.
    static func parseLadder(_ rawCompletion: String?) -> [LadderRung]? {
        guard let rawCompletion, !rawCompletion.isEmpty else { return nil }
        var text = rawCompletion.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.hasPrefix("```") {
            text = replacingRegex(text, pattern: "^```[a-zA-Z]*\\n?", with: "")
            text = replacingRegex(text, pattern: "\\n?```$", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        guard let jsonSlice = firstJSONArray(text) else { return nil }
        guard let data = jsonSlice.data(using: .utf8),
              let parsed = try? JSONSerialization.jsonObject(with: data),
              let array = parsed as? [Any]
        else { return nil }

        var rungs: [LadderRung] = []
        for entry in array {
            if let rung = parseRung(entry) { rungs.append(rung) }
        }
        return rungs
    }

    /// Normalize one raw MCQ rung, or `nil` if structurally unusable. Lenient
    /// about counts (option count / index range) so `checkSchema` gates those.
    /// Mirrors `ladder_gen._parse_rung`.
    private static func parseRung(_ entry: Any) -> LadderRung? {
        guard let obj = entry as? [String: Any] else { return nil }
        let question = coerceString(obj["question"]).trimmingCharacters(in: .whitespacesAndNewlines)
        let explanation = coerceString(obj["explanation"]).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty, !explanation.isEmpty,
              let rawOptions = obj["options"] as? [Any]
        else { return nil }
        let options = rawOptions
            .map { coerceString($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        guard options.count >= 2, let correctIndex = coerceInt(obj["correctIndex"]) else {
            return nil
        }
        return LadderRung(question: question, options: options,
                          correctIndex: correctIndex, explanation: explanation)
    }

    /// str(value) for JSON scalars (mirrors Python's `str(entry.get(...))`).
    private static func coerceString(_ value: Any?) -> String {
        switch value {
        case let s as String: return s
        case let n as NSNumber: return n.stringValue
        case .none, is NSNull: return ""
        default: return "\(value!)"
        }
    }

    /// int(value) for a JSON index: tolerates 0 / 0.0 / "0", rejects booleans
    /// and non-numeric junk (mirrors Python's `int(entry.get("correctIndex"))`).
    private static func coerceInt(_ value: Any?) -> Int? {
        if let n = value as? NSNumber {
            if CFGetTypeID(n) == CFBooleanGetTypeID() { return nil }
            return n.intValue
        }
        if let s = value as? String {
            return Int(s.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return nil
    }

    /// The greedy `\[.*\]` (DOTALL) match Python uses to find the JSON array.
    private static func firstJSONArray(_ text: String) -> String? {
        guard let open = text.firstIndex(of: "["),
              let close = text.lastIndex(of: "]"),
              open <= close
        else { return nil }
        return String(text[open...close])
    }

    private static func replacingRegex(_ text: String, pattern: String, with repl: String) -> String {
        guard let re = try? NSRegularExpression(pattern: pattern, options: [.anchorsMatchLines]) else {
            return text
        }
        let range = NSRange(text.startIndex..., in: text)
        return re.stringByReplacingMatches(in: text, range: range, withTemplate: repl)
    }
}

// MARK: - guardrails (pure)

extension LadderGen {
    /// The text of a rung's correct option, or "" if the index is unusable.
    /// Mirrors `ladder_gen._correct_option`.
    static func correctOption(_ rung: LadderRung) -> String {
        guard rung.options.indices.contains(rung.correctIndex) else { return "" }
        return rung.options[rung.correctIndex]
    }

    /// Structural problems with a parsed MCQ ladder (empty == valid). Mirrors
    /// `ladder_gen.check_schema`.
    static func checkSchema(_ ladder: [LadderRung]?) -> [String] {
        guard let ladder else { return ["ladder is not a list"] }
        var problems: [String] = []
        if !(minRungs <= ladder.count && ladder.count <= maxRungs) {
            problems.append("ladder must have \(minRungs)-\(maxRungs) rungs, got \(ladder.count)")
        }
        for (i, rung) in ladder.enumerated() {
            if rung.question.trimmingCharacters(in: .whitespaces).isEmpty {
                problems.append("rung \(i) has an empty question")
            }
            if rung.explanation.trimmingCharacters(in: .whitespaces).isEmpty {
                problems.append("rung \(i) has an empty explanation")
            }
            let cleaned = rung.options.map { $0.trimmingCharacters(in: .whitespaces) }
            if !(minOptions <= cleaned.count && cleaned.count <= maxOptions) {
                problems.append(
                    "rung \(i) must have \(minOptions)-\(maxOptions) options, got \(cleaned.count)")
            }
            if cleaned.contains(where: { $0.isEmpty }) {
                problems.append("rung \(i) has an empty option")
            }
            let present = cleaned.filter { !$0.isEmpty }.map { $0.lowercased() }
            if Set(present).count != present.count {
                problems.append("rung \(i) has duplicate options")
            }
            if !(0 <= rung.correctIndex && rung.correctIndex < cleaned.count) {
                problems.append("rung \(i) has an out-of-range correctIndex")
            }
        }
        return problems
    }

    /// True when the FIRST rung blatantly gives away the final answer. Checks
    /// the first rung's stem + its correct option. Two triggers: the answer
    /// appears near-verbatim there, or a high fraction (`answerLeakMax`) of the
    /// answer's content words are already present. Mirrors
    /// `ladder_gen.check_answer_leak`.
    static func checkAnswerLeak(_ ladder: [LadderRung], _ context: CardContext) -> Bool {
        guard let first = ladder.first else { return false }
        let firstText = "\(first.question) \(correctOption(first))".trimmingCharacters(in: .whitespaces)
        let answer = context.answer
        if answer.isEmpty { return false }
        let normalizedAnswer = answer.lowercased().split(whereSeparator: { $0 == " " || $0 == "\n" || $0 == "\t" }).joined(separator: " ")
        let normalizedFirst = firstText.lowercased().split(whereSeparator: { $0 == " " || $0 == "\n" || $0 == "\t" }).joined(separator: " ")
        if !normalizedAnswer.isEmpty && normalizedFirst.contains(normalizedAnswer) {
            return true
        }
        return containment(answer, firstText) >= answerLeakMax
    }

    /// Mean fraction of each rung's correct option + explanation supported by
    /// the card's own material. 1.0 == fully grounded, 0.0 == invented. Only
    /// the correct answer + explanation are scored (distractors are meant to be
    /// wrong). Mirrors `ladder_gen.grounding_score`.
    static func groundingScore(_ ladder: [LadderRung], _ context: CardContext) -> Double {
        if ladder.isEmpty { return 0.0 }
        let grounding = context.groundingText
        let scores = ladder.map {
            containment("\(correctOption($0)) \($0.explanation)".trimmingCharacters(in: .whitespaces), grounding)
        }
        return scores.reduce(0, +) / Double(scores.count)
    }

    /// Run all deterministic guardrails. Safe on nil/empty input. Mirrors
    /// `ladder_gen.validate_ladder`.
    static func validateLadder(_ ladder: [LadderRung]?, _ context: CardContext) -> ValidationResult {
        let problems = checkSchema(ladder)
        let usable = ladder ?? []
        let leak = usable.isEmpty ? false : checkAnswerLeak(usable, context)
        let score = usable.isEmpty ? 0.0 : groundingScore(usable, context)
        return ValidationResult(schemaProblems: problems, answerLeak: leak, groundingScore: score)
    }
}

// MARK: - model call injection point (the one bit of IO; injectable for tests)

/// A chat function takes (messages, model) and returns the assistant's text.
/// Injectable so tests never touch the network (mirrors `ladder_gen.ChatFn`).
/// In the app it is wired to `LadderProxyClient` (the Cloudflare Worker proxy);
/// tests inject a stub. The direct api.openai.com call was removed from the app
/// when the OpenAI key moved server-side.
typealias ChatFn = (_ messages: [[String: String]], _ model: String) async throws -> String

/// Raised when generation cannot produce a valid ladder / a transport error.
struct LadderGenError: Error, CustomStringConvertible {
    let message: String
    init(_ message: String) { self.message = message }
    var description: String { message }
}

/// Everything a caller needs: the ladder (if any), why, and the checks. Mirrors
/// `ladder_gen.GenerationOutcome`.
struct GenerationOutcome {
    let ladder: [LadderRung]?
    let validation: ValidationResult?
    let attempts: Int
    let raw: String
    let error: String

    init(ladder: [LadderRung]?, validation: ValidationResult?, attempts: Int,
         raw: String = "", error: String = "") {
        self.ladder = ladder
        self.validation = validation
        self.attempts = attempts
        self.raw = raw
        self.error = error
    }

    var ok: Bool {
        guard let ladder, !ladder.isEmpty, let validation else { return false }
        return validation.passed
    }
}

extension LadderGen {
    /// Generate + validate a ladder, retrying up to `attempts` times. `chat` is
    /// injected (the app wires in `LadderProxyClient` → the Cloudflare Worker;
    /// tests inject a stub). The returned outcome's `ok` is true only when a
    /// produced ladder passed every guardrail. Mirrors `ladder_gen.generate_ladder`.
    static func generateLadder(
        _ context: CardContext,
        chat: ChatFn,
        model: String = defaultModel,
        attempts: Int = defaultAttempts
    ) async -> GenerationOutcome {
        let messages = buildMessages(context)
        var last: GenerationOutcome?
        for attempt in 1...max(1, attempts) {
            let raw: String
            do {
                raw = try await chat(messages, model)
            } catch {
                last = GenerationOutcome(ladder: nil, validation: nil,
                                         attempts: attempt, error: "\(error)")
                continue
            }
            let ladder = parseLadder(raw)
            let validation = validateLadder(ladder, context)
            let outcome = GenerationOutcome(ladder: ladder, validation: validation,
                                            attempts: attempt, raw: raw)
            if outcome.ok { return outcome }
            last = outcome
        }
        return last ?? GenerationOutcome(ladder: nil, validation: nil, attempts: 0,
                                         error: "no attempts made")
    }
}
