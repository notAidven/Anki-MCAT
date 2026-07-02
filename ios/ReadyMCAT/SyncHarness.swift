// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Headless driver for the sync round-trip proof. It is inert unless launched
// with READYMCAT_SYNC_ACTION set (the run-sim.sh harness / verify script pass it
// via SIMCTL_CHILD_*). It performs a deterministic sequence of engine calls —
// login, optionally review N cards, then sync — and writes the outcome to
// Documents/sync_result.json so the host verifier can assert on it. Reviews use
// the shared scheduler; sync uses Anki's own protocol, so this exercises exactly
// the same code paths the interactive app does.

import Foundation

enum SyncHarness {
    struct Result: Codable {
        var ok: Bool
        var action: String
        var steps: [String]
        var reviewed: Int
        var error: String?
        var buildhash: String
    }

    /// Returns true if a headless action was requested (and performed on a
    /// background thread). The app UI keeps running regardless.
    static func runIfRequested(engine: AnkiEngine, model: AppModel, documentsDir: URL) -> Bool {
        let env = ProcessInfo.processInfo.environment
        guard let action = env["READYMCAT_SYNC_ACTION"], !action.isEmpty else { return false }

        let endpoint = env["READYMCAT_SYNC_ENDPOINT"] ?? ""
        let user = env["READYMCAT_SYNC_USER"] ?? ""
        let pass = env["READYMCAT_SYNC_PASS"] ?? ""
        let reviewN = Int(env["READYMCAT_SYNC_REVIEW"] ?? "") ?? 0
        let prefersUpload = (env["READYMCAT_SYNC_FULL"] ?? "upload").lowercased() != "download"
        let resultURL = documentsDir.appendingPathComponent("sync_result.json")

        DispatchQueue.global(qos: .userInitiated).async {
            var steps: [String] = []
            var reviewed = 0
            var ok = true
            var errText: String? = nil
            NSLog("[ReadyMCAT][sync-harness] action=\(action) endpoint=\(endpoint) reviewN=\(reviewN)")
            do {
                var auth: SyncAuth? = nil
                func authed() throws -> SyncAuth {
                    if let auth { return auth }
                    let a = try engine.syncLogin(username: user, password: pass, endpoint: endpoint)
                    guard !a.hkey.isEmpty else { throw EngineError.openFailed("login returned no host key") }
                    steps.append("login ok")
                    auth = a
                    return a
                }

                switch action {
                case "review":
                    reviewed = try engine.autoReview(target: reviewN)
                    steps.append("reviewed \(reviewed)")
                case "sync":
                    let s = try SyncManager.performSync(engine: engine, auth: try authed(),
                                                        fullSyncPrefersUpload: prefersUpload)
                    steps.append("sync: \(s)")
                case "full_upload":
                    try engine.fullUploadOrDownload(auth: try authed(), upload: true)
                    steps.append("full upload")
                case "full_download":
                    try engine.fullUploadOrDownload(auth: try authed(), upload: false)
                    steps.append("full download")
                case "review_sync":
                    // Pull latest, review, then push the new reviews up.
                    let down = try SyncManager.performSync(engine: engine, auth: try authed(),
                                                           fullSyncPrefersUpload: prefersUpload)
                    steps.append("pre-sync: \(down)")
                    reviewed = try engine.autoReview(target: reviewN)
                    steps.append("reviewed \(reviewed)")
                    let up = try SyncManager.performSync(engine: engine, auth: try authed(),
                                                         fullSyncPrefersUpload: prefersUpload)
                    steps.append("post-sync: \(up)")
                default:
                    ok = false
                    errText = "unknown action \(action)"
                }
            } catch {
                ok = false
                errText = "\(error)"
                NSLog("[ReadyMCAT][sync-harness] error: \(error)")
            }

            // Checkpoint SQLite so the host reads a consistent .anki2.
            try? engine.closeCollection(downgrade: false)

            let result = Result(ok: ok, action: action, steps: steps, reviewed: reviewed,
                                error: errText, buildhash: engine.buildHash)
            if let data = try? JSONEncoder().encode(result) {
                try? data.write(to: resultURL)
            }
            NSLog("[ReadyMCAT][sync-harness] done ok=\(ok) steps=\(steps) reviewed=\(reviewed) error=\(errText ?? "nil")")
        }
        return true
    }
}
