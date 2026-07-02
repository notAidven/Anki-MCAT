// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Where the user's OpenAI API key lives on device.
//
// Key-storage choice: the KEYCHAIN (not UserDefaults). The desktop reads the key
// from the `OPENAI_API_KEY` environment variable; on iOS there is no ambient
// env, so the user types it into Settings and we persist it. Unlike the sync
// server credentials — which `SyncManager` keeps in `UserDefaults` because they
// point at the user's own self-hosted server — an OpenAI key is a billable
// secret, so it belongs in the Keychain (encrypted at rest, not in the app's
// plist, excluded from unencrypted backups via `ThisDeviceOnly`). The mobile
// tradeoff is unavoidable and documented: any client-side key can in principle
// be extracted from a jailbroken/instrumented device, so a production build
// should proxy generation through a server rather than ship a user key at all —
// the Keychain is the right choice for this in-app-key MVP.
//
// Generation is enabled ONLY when a key is present; with no key the app behaves
// exactly as before this feature existed (authored ladders only).
//
// Fallback: the reproducible verification build is compiled with `swiftc` and is
// unsigned, so it has no `application-identifier` entitlement and the Keychain
// returns errSecMissingEntitlement. When (and only when) the Keychain is
// unavailable we fall back to `UserDefaults` — the same store `SyncManager` uses
// for its credentials — so the feature is still exercisable on the Simulator.
// A signed device/Xcode build uses the Keychain.

import Foundation
import Security
import SwiftUI

/// Minimal Keychain wrapper for a single generic-password item.
enum Keychain {
    static func set(_ value: String, service: String, account: String) -> Bool {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        // Try update first; if the item doesn't exist, add it.
        let attrs: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        ]
        let updateStatus = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
        if updateStatus == errSecSuccess { return true }
        if updateStatus == errSecItemNotFound {
            var addQuery = query
            addQuery[kSecValueData as String] = data
            addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            return SecItemAdd(addQuery as CFDictionary, nil) == errSecSuccess
        }
        return false
    }

    static func get(service: String, account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let value = String(data: data, encoding: .utf8)
        else { return nil }
        return value
    }

    @discardableResult
    static func delete(service: String, account: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}

/// Observable holder for the OpenAI key. Backed by the Keychain (preferred),
/// with a UserDefaults fallback, and an in-memory mirror so SwiftUI can bind a
/// `SecureField` to it.
@MainActor
final class APIKeyStore: ObservableObject {
    private static let service = "com.readymcat.ios.openai"
    private static let account = "api-key"
    private static let defaultsKey = "rmcat.openai.apikey"

    enum Backend: String { case keychain = "Keychain", userDefaults = "UserDefaults (fallback)", none = "none" }

    /// The current key (empty == none). The Settings screen binds to this and
    /// calls `save()`; nothing is persisted until save.
    @Published var key: String = ""
    /// True once a key has been persisted (Keychain or fallback).
    @Published private(set) var stored: Bool = false
    /// Which store the persisted key lives in (for the Settings surface / docs).
    @Published private(set) var backend: Backend = .none

    init() {
        if let existing = Keychain.get(service: Self.service, account: Self.account),
           !existing.isEmpty {
            key = existing
            stored = true
            backend = .keychain
        } else if let fallback = UserDefaults.standard.string(forKey: Self.defaultsKey),
                  !fallback.isEmpty {
            key = fallback
            stored = true
            backend = .userDefaults
        }
        seedFromLaunchEnvironmentIfDebug()
    }

    /// True when generation should be attempted (a non-empty key is present).
    /// Mirrors `readymcat_ladder_gen.is_enabled`'s "requires an OPENAI_API_KEY".
    var isEnabled: Bool { !trimmedKey.isEmpty }

    var trimmedKey: String { key.trimmingCharacters(in: .whitespacesAndNewlines) }

    /// Persist the current key, preferring the Keychain and falling back to
    /// UserDefaults if the Keychain is unavailable (unsigned Simulator build).
    @discardableResult
    func save() -> Bool {
        let value = trimmedKey
        if value.isEmpty {
            clear()
            return true
        }
        key = value
        if Keychain.set(value, service: Self.service, account: Self.account) {
            UserDefaults.standard.removeObject(forKey: Self.defaultsKey)
            stored = true
            backend = .keychain
            return true
        }
        UserDefaults.standard.set(value, forKey: Self.defaultsKey)
        stored = true
        backend = .userDefaults
        NSLog("[ReadyMCAT] Keychain unavailable; stored OpenAI key in UserDefaults fallback")
        return true
    }

    func clear() {
        Keychain.delete(service: Self.service, account: Self.account)
        UserDefaults.standard.removeObject(forKey: Self.defaultsKey)
        key = ""
        stored = false
        backend = .none
    }

    /// DEBUG-only: pre-fill the key store from a launch env var so the feature
    /// can be exercised on the Simulator without typing into the UI, e.g.
    ///   SIMCTL_CHILD_OPENAI_API_KEY=sk-… xcrun simctl launch …
    /// (the child process sees it as OPENAI_API_KEY). Never runs in release, and
    /// only seeds when the store is empty so it can't clobber a real saved key.
    private func seedFromLaunchEnvironmentIfDebug() {
        #if DEBUG
        guard !stored else { return }
        let env = ProcessInfo.processInfo.environment
        guard let injected = env["OPENAI_API_KEY"]?.trimmingCharacters(in: .whitespacesAndNewlines),
              !injected.isEmpty
        else { return }
        key = injected
        _ = save()
        NSLog("[ReadyMCAT] seeded OpenAI key from launch env (DEBUG) into \(backend.rawValue)")
        #endif
    }
}
