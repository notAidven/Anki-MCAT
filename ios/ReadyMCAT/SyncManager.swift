// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Two-way sync on Anki's OWN collection-sync protocol. There is no custom sync
// here: this drives the identical backend commands the desktop uses
// (SyncLogin → SyncCollection → FullUploadOrDownload, all on service 1) through
// the shared rslib engine, against a self-hosted Anki sync server. Because we
// reuse Anki's protocol, reviews are reconciled by USN + revlog id exactly as
// on the desktop, so nothing is lost or double-counted.
//
// The manager is a small state machine on top of AnkiEngine's sync methods:
//   1. ensureAuth()      — SyncLogin to get an hkey (cached in UserDefaults)
//   2. SyncCollection    — one normal/incremental sync
//   3. if the server asks for a FULL_* sync, FullUploadOrDownload accordingly.

import Foundation
import SwiftUI

@MainActor
final class SyncManager: ObservableObject {
    enum Phase: Equatable {
        case idle
        case syncing
        case success(String)
        case failure(String)
    }

    @Published var endpoint: String
    @Published var username: String
    @Published var password: String
    @Published private(set) var phase: Phase = .idle
    @Published private(set) var lastSyncedAt: Date?
    /// True while a sync is in flight (guards against overlapping syncs on
    /// launch + foreground + manual tap).
    @Published private(set) var busy = false

    /// When a FULL_SYNC (both sides changed) is reported, whether to resolve it
    /// by uploading (true) or downloading (false). The UI can surface a choice;
    /// the default keeps the local collection (upload).
    @Published var fullSyncPrefersUpload = true

    private weak var engine: AnkiEngine?
    private weak var model: AppModel?

    private enum Key {
        static let endpoint = "rmcat.sync.endpoint"
        static let username = "rmcat.sync.username"
        static let password = "rmcat.sync.password"
        static let hkey = "rmcat.sync.hkey"
    }

    init() {
        let d = UserDefaults.standard
        endpoint = d.string(forKey: Key.endpoint) ?? ""
        username = d.string(forKey: Key.username) ?? ""
        password = d.string(forKey: Key.password) ?? ""
    }

    private var hkey: String {
        get { UserDefaults.standard.string(forKey: Key.hkey) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: Key.hkey) }
    }

    var isConfigured: Bool {
        !endpoint.isEmpty && (!hkey.isEmpty || (!username.isEmpty && !password.isEmpty))
    }

    func attach(engine: AnkiEngine, model: AppModel) {
        self.engine = engine
        self.model = model
    }

    /// Persist the current endpoint/credentials (called from the settings form).
    func saveCredentials() {
        let d = UserDefaults.standard
        d.set(endpoint, forKey: Key.endpoint)
        d.set(username, forKey: Key.username)
        d.set(password, forKey: Key.password)
        // A credential change invalidates any cached host key.
        hkey = ""
    }

    // MARK: - Public entry points

    /// Sync if we have enough to do so; used on launch and foreground. Silent
    /// no-op when unconfigured so the app still works fully offline.
    func syncOnActivate() {
        guard isConfigured, !busy else { return }
        Task { await self.sync() }
    }

    /// Explicit user-initiated sync (Sync button).
    func syncNow() {
        guard !busy else { return }
        Task { await self.sync() }
    }

    /// Log in with the current username/password/endpoint and cache the hkey.
    func loginNow() {
        guard !busy else { return }
        Task { await self.login() }
    }

    // MARK: - Core flow

    private func login() async {
        guard let engine else { return }
        saveCredentials()
        busy = true
        phase = .syncing
        let (ep, user, pass) = (endpoint, username, password)
        do {
            let auth = try await runOffMain {
                try engine.syncLogin(username: user, password: pass, endpoint: ep)
            }
            hkey = auth.hkey
            phase = auth.hkey.isEmpty ? .failure("login returned no key") : .success("Logged in")
        } catch {
            phase = .failure("\(error)")
        }
        busy = false
    }

    /// Ensure we have a usable auth (host key). Logs in if needed.
    private func ensureAuth(_ engine: AnkiEngine) async throws -> SyncAuth {
        if !hkey.isEmpty {
            return SyncAuth(hkey: hkey, endpoint: endpoint)
        }
        guard !username.isEmpty, !password.isEmpty else {
            throw EngineError.openFailed("Not logged in and no saved credentials")
        }
        let (ep, user, pass) = (endpoint, username, password)
        let auth = try await runOffMain {
            try engine.syncLogin(username: user, password: pass, endpoint: ep)
        }
        hkey = auth.hkey
        return auth
    }

    @discardableResult
    func sync() async -> Bool {
        guard let engine, isConfigured else { return false }
        busy = true
        phase = .syncing
        let prefersUpload = fullSyncPrefersUpload
        do {
            let auth = try await ensureAuth(engine)
            let summary = try await runOffMain {
                try SyncManager.performSync(engine: engine, auth: auth,
                                            fullSyncPrefersUpload: prefersUpload)
            }
            lastSyncedAt = Date()
            phase = .success(summary)
            model?.refresh()
            busy = false
            return true
        } catch {
            // A stale/expired host key manifests as an auth error; drop it so the
            // next attempt logs in afresh.
            let text = "\(error)"
            if text.localizedCaseInsensitiveContains("auth") || text.contains("403") {
                hkey = ""
            }
            phase = .failure(text)
            busy = false
            return false
        }
    }

    /// The pure sync state machine (no UI), shared by the UI path and the
    /// headless verification harness. Runs one normal sync and, if the server
    /// requires it, a full upload/download. Returns a human-readable summary.
    nonisolated static func performSync(engine: AnkiEngine, auth: SyncAuth,
                                        fullSyncPrefersUpload: Bool) throws -> String {
        let required = try engine.syncCollection(auth: auth, syncMedia: false)
        switch required {
        case .noChanges:
            return "up to date"
        case .normalSync:
            // Incremental sync already applied by the call above.
            return "normal sync"
        case .fullUpload:
            try engine.fullUploadOrDownload(auth: auth, upload: true)
            return "full upload"
        case .fullDownload:
            try engine.fullUploadOrDownload(auth: auth, upload: false)
            return "full download"
        case .fullSync:
            try engine.fullUploadOrDownload(auth: auth, upload: fullSyncPrefersUpload)
            return fullSyncPrefersUpload ? "full sync → upload" : "full sync → download"
        }
    }

    /// Run a blocking engine call off the main actor (sync is network I/O).
    private func runOffMain<T: Sendable>(_ work: @escaping @Sendable () throws -> T) async throws -> T {
        try await withCheckedThrowingContinuation { cont in
            DispatchQueue.global(qos: .userInitiated).async {
                do { cont.resume(returning: try work()) }
                catch { cont.resume(throwing: error) }
            }
        }
    }

    var statusText: String {
        switch phase {
        case .idle: return isConfigured ? "Ready to sync" : "Not configured"
        case .syncing: return "Syncing…"
        case .success(let s): return "Synced: \(s)"
        case .failure(let e): return "Error: \(e)"
        }
    }
}
