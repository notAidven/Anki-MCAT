// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import SwiftUI

@main
struct ReadyMCATApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

/// Manages the on-device collection: copies the bundled sample `.anki2` into the
/// app's Documents directory on first launch (Anki opens the collection
/// read-write, so it must live in a writable location), and returns the paths
/// the engine needs.
enum CollectionStore {
    struct Paths {
        let collection: String
        let mediaFolder: String
        let mediaDB: String
    }

    static func prepare() throws -> Paths {
        let fm = FileManager.default
        let docs = try fm.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )

        let collectionURL = docs.appendingPathComponent("collection.anki2")
        if !fm.fileExists(atPath: collectionURL.path) {
            guard let bundled = Bundle.main.url(forResource: "sample", withExtension: "anki2") else {
                throw NSError(
                    domain: "ReadyMCAT", code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "Bundled sample.anki2 is missing from the app bundle."]
                )
            }
            try fm.copyItem(at: bundled, to: collectionURL)
            NSLog("[ReadyMCAT] copied bundled collection to \(collectionURL.path)")
        }

        let mediaFolderURL = docs.appendingPathComponent("collection.media", isDirectory: true)
        if !fm.fileExists(atPath: mediaFolderURL.path) {
            try fm.createDirectory(at: mediaFolderURL, withIntermediateDirectories: true)
        }
        let mediaDBURL = docs.appendingPathComponent("collection.media.db")

        return Paths(
            collection: collectionURL.path,
            mediaFolder: mediaFolderURL.path,
            mediaDB: mediaDBURL.path
        )
    }

    /// Writes a small JSON result to Documents so the headless auto-review can
    /// be verified externally via `simctl get_app_container`.
    static func writeResult(reviewed: Int, remaining: Int) {
        guard let docs = try? FileManager.default.url(
            for: .documentDirectory, in: .userDomainMask, appropriateFor: nil, create: true
        ) else { return }
        let url = docs.appendingPathComponent("review_result.json")
        let json = #"{"reviewed": \#(reviewed), "remaining": \#(remaining)}"#
        try? json.data(using: .utf8)?.write(to: url)
    }
}
