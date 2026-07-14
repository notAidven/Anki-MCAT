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

    /// The single reused filtered deck that isolates one format's cards for a
    /// one-tap study session (see `studyDeckId`). Same name the desktop hub uses
    /// (qt/aqt/readymcat_home.py) so a synced collection shares one launcher deck.
    static let launcherDeckName = "ReadyMCAT Launcher"

    /// The launcher filtered deck id once built/found, so repeat studies reuse it
    /// (and we can empty it) rather than minting duplicates.
    private var launcherDeckId: Int64 = 0

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
    /// These are `DeckTreeNode`'s child-excluding counters, so the MCQ tile
    /// (deck `ReadyMCAT`) reports only its 414 direct MCQ cards and never its
    /// Free Response / Passages / CARS children (and Passages never counts CARS).
    func counts(for format: Format) -> (present: Bool, due: Int, total: Int) {
        guard let node = node(for: format) else { return (false, 0, 0) }
        return (true, node.due, node.totalInDeck)
    }

    /// Search that isolates exactly `format`'s cards, excluding any nested child
    /// deck — or nil when the format's deck is a leaf (a plain deck study is
    /// already isolated). Mirrors readymcat/tools/home_launcher.isolating_search_for:
    /// MCQ (`ReadyMCAT`) and Passages both have children; Free Response and CARS
    /// are leaves. Built from `Format.deckName` so it can't drift from the tiles.
    func isolatingSearch(for format: Format) -> String? {
        switch format {
        case .mcq:
            let d = Format.mcq.deckName
            return "deck:\"\(d)\" -deck:\"\(d)::*\""
        case .passage:
            return "deck:\"\(Format.passage.deckName)\" -deck:\"\(Format.cars.deckName)\""
        case .fr, .cars:
            return nil
        }
    }

    /// The deck id to actually STUDY for `format`. Leaf formats (fr, cars) study
    /// their deck directly; formats whose deck has nested children (mcq, passage)
    /// are routed through the reused launcher filtered deck scoped by
    /// `isolatingSearch`, so the session serves ONLY that format's cards — never
    /// a sibling format nested under the same parent. Falls back to the plain
    /// deck id if the filtered build ever fails, so study is never blocked.
    func studyDeckId(for format: Format) -> Int64? {
        guard let engine else { return node(for: format)?.deckId }
        guard let search = isolatingSearch(for: format) else {
            return node(for: format)?.deckId
        }
        let seed = launcherDeckId != 0
            ? launcherDeckId
            : (deckTree?.find(name: Self.launcherDeckName)?.deckId ?? 0)
        // Try the reused deck first; if that id is stale/not-filtered, mint fresh.
        for candidateSeed in (seed != 0 ? [seed, 0] : [0]) {
            do {
                let did = try engine.rebuildLauncherDeck(
                    seedId: candidateSeed, name: Self.launcherDeckName, search: search)
                launcherDeckId = did
                return did
            } catch {
                NSLog("[ReadyMCAT] launcher build failed (seed \(candidateSeed)) for \(format): \(error)")
            }
        }
        return node(for: format)?.deckId
    }

    /// Empty the launcher filtered deck so any cards it still holds return to
    /// their home decks and the format tiles read honest counts again. A no-op
    /// when nothing is held. Called after a study session closes.
    func returnLauncherCards() {
        guard let engine else { return }
        let id = launcherDeckId != 0
            ? launcherDeckId
            : (deckTree?.find(name: Self.launcherDeckName)?.deckId ?? 0)
        guard id != 0 else { return }
        do {
            try engine.emptyFilteredDeck(id)
            launcherDeckId = id
        } catch {
            NSLog("[ReadyMCAT] returnLauncherCards failed: \(error)")
        }
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
