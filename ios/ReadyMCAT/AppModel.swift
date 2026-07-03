// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The single source of truth the SwiftUI screens observe. It opens the shared
// engine once against the bundled collection and exposes the two live data reads
// every screen needs: the deck due tree (Home tiles) and the points-at-stake
// payload (Dashboard + "study next"). The reviewers borrow the same engine so
// grades flow straight back into the shared scheduler and re-reading the tree /
// points reflects them immediately.

import Foundation
import SwiftUI

/// A deck id wrapped for SwiftUI `.fullScreenCover(item:)` presentation
/// (used to open the authorless AI demo review).
struct DeckRef: Identifiable { let id: Int64 }

@MainActor
final class AppModel: ObservableObject {
    @Published var loaded = false
    @Published var errorText: String?

    @Published var deckTree: DeckNode?
    @Published var points: PointsAtStake?
    @Published var pointsError: String?
    @Published var lastUpdated = Date()

    private(set) var engine: AnkiEngine?
    private(set) var taxonomyPath = ""
    private(set) var diagnosticPath = ""

    /// Two-way sync on Anki's own protocol (see SyncManager).
    let sync = SyncManager()

    /// The proxy configuration (base URL + low-value app token) + the runtime
    /// teach-on-miss generator. The OpenAI key lives server-side, not here.
    let proxyConfig: ProxyConfigStore
    let ai: AILadderService

    /// Fully-qualified name of the authorless demo deck (seeded on demand so the
    /// AI ladder path is reachable — the bundled bank's cards all ship a ladder).
    static let demoDeckName = "ReadyMCAT::AI Demo"

    init() {
        let store = ProxyConfigStore()
        proxyConfig = store
        ai = AILadderService(config: store)
    }

    func bootstrap() {
        guard engine == nil else { return }
        do {
            let paths = try CollectionStore.prepare()
            taxonomyPath = paths.taxonomy
            diagnosticPath = paths.diagnostic
            let engine = try AnkiEngine()
            try engine.openCollection(
                path: paths.collection,
                mediaFolder: paths.mediaFolder,
                mediaDB: paths.mediaDB
            )
            self.engine = engine
            sync.attach(engine: engine, model: self)
            NSLog("[ReadyMCAT] engine opened; buildhash=\(engine.buildHash)")
            refresh()
            loaded = true

            // Optional: seed the authorless demo deck so the AI ladder path is
            // reachable on the Simulator (READYMCAT_AI_DEMO=1). No-op otherwise,
            // so the shipped bank is untouched for normal launches.
            if ProcessInfo.processInfo.environment["READYMCAT_AI_DEMO"] != nil {
                _ = seedAIDemoDeck()
            }

            // Headless verification path (READYMCAT_SYNC_ACTION); otherwise a
            // normal launch syncs in the background when configured.
            let docs = URL(fileURLWithPath: paths.collection).deletingLastPathComponent()
            if !SyncHarness.runIfRequested(engine: engine, model: self, documentsDir: docs) {
                sync.syncOnActivate()
            }
        } catch {
            errorText = "\(error)"
            NSLog("[ReadyMCAT] bootstrap error: \(error)")
        }
    }

    /// Re-read the deck tree and the points-at-stake payload from the engine.
    /// Called on launch and after every study session so counts + scores stay live.
    func refresh() {
        guard let engine else { return }
        do {
            deckTree = try engine.deckTree()
        } catch {
            NSLog("[ReadyMCAT] deckTree error: \(error)")
        }
        do {
            points = try engine.pointsAtStake(taxonomyPath: taxonomyPath)
            pointsError = nil
        } catch {
            points = nil
            pointsError = "\(error)"
            NSLog("[ReadyMCAT] pointsAtStake error: \(error)")
        }
        lastUpdated = Date()
    }

    func node(for format: Format) -> DeckNode? {
        deckTree?.find(name: format.deckName)
    }

    /// Due/total counts for a format's tile (0 / not-present when absent).
    func counts(for format: Format) -> (present: Bool, due: Int, total: Int) {
        guard let node = node(for: format) else { return (false, 0, 0) }
        return (true, node.due, node.totalInDeck)
    }

    /// The single highest-points format to nudge next ("study next" shortcut):
    /// the due format whose top-ranked topic has the most points at stake.
    var suggestedFormat: Format? {
        Format.allCases
            .filter { counts(for: $0).due > 0 }
            .max { counts(for: $0).due < counts(for: $1).due }
    }

    // MARK: - AI demo deck

    /// Ensure a single authorless demo card exists (in its own deck) so the AI
    /// teach-on-miss path is triggerable. Idempotent: returns the existing deck
    /// if already seeded. The card reuses the Free-Response notetype (8 fields in
    /// build_question_bank order) with an EMPTY `Subquestions` field — i.e. it has
    /// no authored ladder, so a miss falls through to runtime generation. Rich
    /// prompt/model-answer/explanation/source give the generator enough grounded
    /// material to pass the guardrails. Returns the demo deck id, or nil on error.
    @discardableResult
    func seedAIDemoDeck() -> Int64? {
        guard let engine else { return nil }
        // Existence check via the deck tree (GetDeckIdByName throws when missing).
        if let existing = deckTree?.find(name: Self.demoDeckName), existing.deckId != 0 {
            return existing.deckId
        }
        do {
            // Reuse the Free-Response notetype by peeking one FR note (so the demo
            // card parses through the same FR path as the real cards).
            guard let frNode = node(for: .fr) else { return nil }
            try engine.setCurrentDeck(frNode.deckId)
            let (peek, _) = try engine.nextCard()
            guard let peek else { return nil }
            let notetypeId = try engine.noteNotetypeId(noteId: peek.noteId)
            guard notetypeId != 0 else { return nil }

            let deckId = try engine.createDeck(name: Self.demoDeckName)
            guard deckId != 0 else { return nil }
            try engine.addNote(notetypeId: notetypeId, deckId: deckId,
                               fields: Self.demoFRFields, tags: ["ReadyMCAT::AI-Demo"])
            refresh()
            NSLog("[ReadyMCAT] seeded AI demo deck \(deckId)")
            return deckId
        } catch {
            NSLog("[ReadyMCAT] seedAIDemoDeck error: \(error)")
            return nil
        }
    }

    /// Fields for the demo card, in Free-Response notetype order:
    /// Prompt, AcceptedAnswers(JSON), KeyTerms(JSON), ModelAnswer, Explanation,
    /// Subtopic, Source, Subquestions(EMPTY -> no authored ladder).
    private static let demoFRFields: [String] = [
        "A 0.10 M aqueous solution of a weak monoprotic acid HA has a measured pH of 3.0. What is the acid-dissociation constant, Ka, of HA?",
        "[\"1e-5\", \"1.0e-5\", \"1 x 10^-5\", \"0.00001\"]",
        "[\"Ka\", \"weak acid\", \"tolerance: 15%\"]",
        "Ka = [H+][A-] / [HA]. From pH 3.0, [H+] = 1x10^-3 M, and [A-] = [H+] for a weak acid, while [HA] stays about 0.10 M. So Ka = (1x10^-3)(1x10^-3) / 0.10 = 1x10^-5.",
        "pH 3.0 means the hydrogen-ion concentration [H+] equals 10^-3 M. For a weak acid HA that dissociates into H+ and A-, the two ions form in a 1:1 ratio, so [A-] also equals 10^-3 M. Because dissociation is small, the undissociated acid concentration [HA] is approximately its initial 0.10 M. Substituting into Ka = [H+][A-]/[HA] gives (10^-3)(10^-3)/0.10 = 1x10^-5.",
        "Acid-base equilibria",
        "Khan Academy - Weak acid and base equilibria (https://www.khanacademy.org/science/chemistry)",
        "",
    ]
}
