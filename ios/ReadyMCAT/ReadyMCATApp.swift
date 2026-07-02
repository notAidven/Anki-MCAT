// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import SwiftUI

@main
struct ReadyMCATApp: App {
    @StateObject private var model = AppModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
                .onAppear { model.bootstrap() }
        }
        .onChange(of: scenePhase) { phase in
            // Sync on foreground so reviews from other devices show up, and any
            // reviews done here get pushed. No-op until the user configures sync.
            if phase == .active, model.loaded {
                model.sync.syncOnActivate()
            }
        }
    }
}

/// Manages the on-device collection: copies the bundled ReadyMCAT bank and its
/// companion JSON (taxonomy / diagnostic / sub-questions) into the app's
/// Documents directory on first launch (Anki opens the collection read-write, and
/// the points-at-stake engine looks for taxonomy.json *next to* the collection),
/// then returns the paths the engine needs.
enum CollectionStore {
    struct Paths {
        let collection: String
        let mediaFolder: String
        let mediaDB: String
        let taxonomy: String
        let diagnostic: String
    }

    static func prepare() throws -> Paths {
        let fm = FileManager.default
        let docs = try fm.url(for: .documentDirectory, in: .userDomainMask,
                              appropriateFor: nil, create: true)

        // Optional SYNTHETIC demo collection (READYMCAT_COLLECTION=demo) used only
        // to preview a populated dashboard; the default is the honest fresh bank.
        // Falls back to the real bank if the demo asset isn't bundled.
        let wantsDemo = ProcessInfo.processInfo.environment["READYMCAT_COLLECTION"] == "demo"
        let hasDemo = wantsDemo && Bundle.main.url(forResource: "collection-demo", withExtension: "anki2") != nil
        let bundledName = hasDemo ? "collection-demo" : "collection"
        let docName = hasDemo ? "collection-demo.anki2" : "collection.anki2"

        let collectionURL = docs.appendingPathComponent(docName)
        if !fm.fileExists(atPath: collectionURL.path) {
            guard let bundled = Bundle.main.url(forResource: bundledName, withExtension: "anki2") else {
                throw NSError(domain: "ReadyMCAT", code: 1, userInfo: [
                    NSLocalizedDescriptionKey: "Bundled \(bundledName).anki2 is missing from the app bundle."
                ])
            }
            try fm.copyItem(at: bundled, to: collectionURL)
            NSLog("[ReadyMCAT] copied bundled collection to \(collectionURL.path)")
        }

        // The points-at-stake engine + diagnostic look for these NEXT TO the
        // collection, so drop them into Documents alongside collection.anki2.
        let taxonomyURL = docs.appendingPathComponent("taxonomy.json")
        copyBundledIfNeeded("taxonomy", "json", to: taxonomyURL, fm: fm)
        let diagnosticURL = docs.appendingPathComponent("diagnostic_quiz.json")
        copyBundledIfNeeded("diagnostic_quiz", "json", to: diagnosticURL, fm: fm)
        copyBundledIfNeeded("subquestions", "json",
                            to: docs.appendingPathComponent("subquestions.json"), fm: fm)

        let mediaFolderURL = docs.appendingPathComponent("collection.media", isDirectory: true)
        if !fm.fileExists(atPath: mediaFolderURL.path) {
            try fm.createDirectory(at: mediaFolderURL, withIntermediateDirectories: true)
        }
        let mediaDBURL = docs.appendingPathComponent("collection.media.db")

        return Paths(
            collection: collectionURL.path,
            mediaFolder: mediaFolderURL.path,
            mediaDB: mediaDBURL.path,
            taxonomy: taxonomyURL.path,
            diagnostic: diagnosticURL.path
        )
    }

    private static func copyBundledIfNeeded(_ name: String, _ ext: String,
                                            to dest: URL, fm: FileManager) {
        guard !fm.fileExists(atPath: dest.path),
              let src = Bundle.main.url(forResource: name, withExtension: ext) else { return }
        try? fm.copyItem(at: src, to: dest)
        NSLog("[ReadyMCAT] copied bundled \(name).\(ext) to \(dest.path)")
    }
}
