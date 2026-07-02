// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The host around the pure LadderGen core (the iOS analogue of the desktop's
// qt/aqt/readymcat_ladder_gen.py). It:
//   * decides whether generation is enabled (a key is present), and
//   * turns a parsed review item into the grounding CardContext, then
//   * generates + validates a ladder, caching a validated one per note so a card
//     is only ever generated once per session and every later miss is instant.
//
// It hands back a `[LadderRung]` ONLY when the guardrails pass; the reviewer
// shows it iff non-nil and otherwise falls back to a normal reveal — the same
// contract as the desktop.

import Foundation
import SwiftUI

@MainActor
final class AILadderService: ObservableObject {
    private let keyStore: APIKeyStore

    /// Per-note cache of validated ladders (generate once, reuse on later misses).
    private var cache: [Int64: [LadderRung]] = [:]

    /// Last generation's human-readable guardrail summary (for the Settings/debug
    /// surface and NSLog); nil until the first attempt.
    @Published private(set) var lastSummary: String?

    init(keyStore: APIKeyStore) { self.keyStore = keyStore }

    /// True when a key is present. When false the reviewer never calls generate,
    /// so the app behaves exactly as authored-ladders-only.
    var isEnabled: Bool { keyStore.isEnabled }

    /// Generate + validate a ladder for a missed card. Returns the rungs to show
    /// (guardrails passed) or nil (disabled / transport error / failed a
    /// guardrail) — in which case the reviewer falls back to a normal reveal.
    func ladder(forNoteId noteId: Int64?, context: CardContext) async -> [LadderRung]? {
        guard isEnabled else { return nil }
        if let noteId, let cached = cache[noteId] { return cached }

        let apiKey = keyStore.trimmedKey
        let chat: ChatFn = { messages, model in
            try await LadderGen.openAIChat(messages, model: model, apiKey: apiKey)
        }
        let outcome = await LadderGen.generateLadder(context, chat: chat)
        lastSummary = summarize(outcome)
        NSLog("[ReadyMCAT][AI] ladder generation: \(lastSummary ?? "")")

        guard outcome.ok, let rungs = outcome.ladder, !rungs.isEmpty else { return nil }
        if let noteId { cache[noteId] = rungs }
        return rungs
    }

    private func summarize(_ outcome: GenerationOutcome) -> String {
        if !outcome.error.isEmpty {
            return "error after \(outcome.attempts) attempt(s): \(outcome.error)"
        }
        guard let v = outcome.validation else {
            return "no validation (\(outcome.attempts) attempts)"
        }
        let grounding = String(format: "%.2f", v.groundingScore)
        return "ok=\(outcome.ok) attempts=\(outcome.attempts) "
            + "schema=\(v.schemaOk) leak=\(v.answerLeak) grounding=\(grounding)"
    }
}

// MARK: - Review item -> grounding CardContext

/// Join A/B/C/D option labels the way the rendered card shows them, so the model
/// sees the full stem the student saw (faithful to the desktop's use of the
/// rendered question HTML as grounding).
private func labeledOptions(_ options: [String]) -> String {
    options.enumerated().compactMap { i, opt in
        let text = opt.plainText
        guard !text.isEmpty, let scalar = UnicodeScalar(65 + i) else { return nil }
        return "\(Character(scalar)). \(text)"
    }.joined(separator: "\n")
}

private func joinedNonEmpty(_ parts: [String], separator: String = "\n") -> String {
    parts.map { $0.plainText }.filter { !$0.isEmpty }.joined(separator: separator)
}

extension MCQItem {
    /// question = stem + options (what the student saw); answer = correct choice
    /// + explanation (the correction, which rung 1 must not leak); source grounds.
    var ladderContext: CardContext {
        let correct = options.indices.contains(correctIndex) ? options[correctIndex] : ""
        return CardContext(
            question: joinedNonEmpty([question, labeledOptions(options)]),
            answer: joinedNonEmpty(["Correct answer: \(correct)", explanation]),
            source: source,
            tags: subtopic.isEmpty ? [] : [subtopic]
        )
    }
}

extension FRItem {
    var ladderContext: CardContext {
        let accepted = acceptedAnswers
            .map { $0.plainText }
            .filter { !$0.isEmpty && !$0.lowercased().hasPrefix("tolerance") && !$0.lowercased().hasPrefix("unit") }
        let acceptedLine = accepted.isEmpty ? "" : "Accepted: \(accepted.prefix(6).joined(separator: "; "))"
        return CardContext(
            question: prompt,
            answer: joinedNonEmpty([acceptedLine, modelAnswer, explanation]),
            source: source,
            tags: subtopic.isEmpty ? [] : [subtopic]
        )
    }
}

extension PassageItem {
    var ladderContext: CardContext {
        let correct = options.indices.contains(correctIndex) ? options[correctIndex] : ""
        return CardContext(
            question: joinedNonEmpty([passage, question, labeledOptions(options)]),
            answer: joinedNonEmpty(["Correct answer: \(correct)", explanation]),
            source: source,
            tags: subtopic.isEmpty ? [] : [subtopic]
        )
    }
}
