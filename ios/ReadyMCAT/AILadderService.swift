// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The host around the pure LadderGen core (the iOS analogue of the desktop's
// qt/aqt/readymcat_ladder_gen.py). It:
//   * decides whether generation is enabled (a proxy URL is configured), and
//   * turns a parsed review item into the grounding CardContext, then
//   * generates + validates a ladder, caching a validated one per note so a card
//     is only ever generated once per session and every later miss is instant.
//
// It hands back a `[LadderRung]` ONLY when the guardrails pass; the reviewer
// shows it iff non-nil and otherwise falls back to a normal reveal — the same
// contract as the desktop.
//
// The OpenAI key is NO LONGER on the phone: the injected `ChatFn` now calls the
// ReadyMCAT proxy (a Cloudflare Worker, see ios/backend/openai-proxy) via
// `LadderProxyClient`, which returns the raw completion text. Everything after
// that — parsing, the three guardrails, the retry loop, per-note caching — is
// unchanged, so behavior (and the eval-scored guardrails) match exactly.

import Foundation
import SwiftUI

@MainActor
final class AILadderService: ObservableObject {
    private let config: ProxyConfigStore

    /// Per-note cache of validated ladders (generate once, reuse on later misses).
    private var cache: [Int64: [LadderRung]] = [:]

    /// Last generation's human-readable guardrail summary (for the Settings/debug
    /// surface and NSLog); nil until the first attempt.
    @Published private(set) var lastSummary: String?

    init(config: ProxyConfigStore) { self.config = config }

    /// True when a proxy URL is configured and AI is toggled on. When false the
    /// reviewer never calls generate, so the app behaves exactly as
    /// authored-ladders-only.
    var isEnabled: Bool { config.isEnabled }

    /// Generate + validate a ladder for a missed card. Returns the rungs to show
    /// (guardrails passed) or nil (disabled / transport error / failed a
    /// guardrail) — in which case the reviewer falls back to a normal reveal.
    func ladder(forNoteId noteId: Int64?, context: CardContext) async -> [LadderRung]? {
        guard isEnabled else { return nil }
        if let noteId, let cached = cache[noteId] { return cached }

        let baseURL = config.trimmedBaseURL
        let token = config.trimmedToken
        // The prompt is built SERVER-SIDE by the Worker from the structured card
        // context, so a leaked app token can't drive arbitrary prompts. The
        // `messages`/`model` args that generateLadder builds locally are
        // intentionally unused here — we send the CardContext and let the Worker
        // build the (identical) prompt. What comes back is the raw completion,
        // exactly what the old direct-OpenAI ChatFn returned.
        let chat: ChatFn = { _, _ in
            try await LadderProxyClient.generate(context: context, baseURL: baseURL, token: token)
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
