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
}
