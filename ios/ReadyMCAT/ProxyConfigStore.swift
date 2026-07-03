// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// On-device configuration for the AI teach-on-miss generator, AFTER the OpenAI
// key was moved off the phone.
//
// The phone no longer stores an OpenAI key. Generation now goes through a
// serverless proxy (a Cloudflare Worker, ios/backend/openai-proxy) that holds
// the OpenAI key as a SERVER-side secret and calls OpenAI on the app's behalf.
// So the only things this store keeps on device are both LOW-VALUE:
//
//   * baseURL  — the proxy's HTTPS URL (e.g. https://<name>.workers.dev). This
//                is NOT a secret; it lives in UserDefaults.
//   * appToken — the proxy's app token, sent as `Authorization: Bearer …`. Its
//                only job is to stop strangers from spending your OpenAI budget;
//                unlike the OpenAI key, leaking it costs nothing but some abuse
//                and it is trivially rotated server-side. It is still kept in the
//                Keychain (with the same UserDefaults fallback for the unsigned
//                `swiftc` Simulator build that `SyncManager` uses), because it is
//                the closest thing to a credential the app now holds.
//   * aiEnabled — the "AI on/off" toggle.
//
// The high-value secret (the OpenAI key) is gone from the device entirely — the
// whole point of this change. Generation is attempted only when the toggle is on
// AND a proxy URL is set; otherwise the app behaves exactly as before the AI
// feature existed (authored ladders only), so the three honest scores and the
// retrieve-before-reveal flow are unaffected with AI off.

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

/// Observable holder for the proxy configuration. The base URL + on/off toggle
/// are non-secret (UserDefaults); the low-value app token is kept in the
/// Keychain (preferred) with a UserDefaults fallback, and mirrored in memory so
/// SwiftUI can bind a `SecureField` to it.
@MainActor
final class ProxyConfigStore: ObservableObject {
    private static let service = "com.readymcat.ios.proxy"
    private static let tokenAccount = "app-token"
    private static let tokenDefaultsKey = "rmcat.proxy.apptoken"
    private static let baseURLDefaultsKey = "rmcat.proxy.baseurl"
    private static let enabledDefaultsKey = "rmcat.proxy.enabled"

    enum Backend: String { case keychain = "Keychain", userDefaults = "UserDefaults (fallback)", none = "none" }

    /// The proxy base URL (non-secret). Empty == not configured → AI off.
    @Published var baseURL: String = ""
    /// The low-value app token sent as a Bearer header (empty == none).
    @Published var appToken: String = ""
    /// The "AI ladder generation on/off" toggle.
    @Published var aiEnabled: Bool = true
    /// True once an app token has been persisted (Keychain or fallback).
    @Published private(set) var tokenStored: Bool = false
    /// Which store the persisted token lives in (for the Settings surface).
    @Published private(set) var tokenBackend: Backend = .none

    init() {
        if let url = UserDefaults.standard.string(forKey: Self.baseURLDefaultsKey) {
            baseURL = url
        }
        if UserDefaults.standard.object(forKey: Self.enabledDefaultsKey) != nil {
            aiEnabled = UserDefaults.standard.bool(forKey: Self.enabledDefaultsKey)
        }
        if let existing = Keychain.get(service: Self.service, account: Self.tokenAccount),
           !existing.isEmpty {
            appToken = existing
            tokenStored = true
            tokenBackend = .keychain
        } else if let fallback = UserDefaults.standard.string(forKey: Self.tokenDefaultsKey),
                  !fallback.isEmpty {
            appToken = fallback
            tokenStored = true
            tokenBackend = .userDefaults
        }
        seedFromLaunchEnvironmentIfDebug()
    }

    var trimmedBaseURL: String { baseURL.trimmingCharacters(in: .whitespacesAndNewlines) }
    var trimmedToken: String { appToken.trimmingCharacters(in: .whitespacesAndNewlines) }

    /// True when generation should be attempted: the toggle is on AND a proxy URL
    /// is set. With no URL the app behaves exactly as before (authored ladders
    /// only) — the same contract the old key-presence check provided.
    var isEnabled: Bool { aiEnabled && !trimmedBaseURL.isEmpty }

    /// Persist the base URL (non-secret) + toggle, and the app token (Keychain
    /// preferred, UserDefaults fallback when the Keychain is unavailable).
    @discardableResult
    func save() -> Bool {
        let url = trimmedBaseURL
        baseURL = url
        UserDefaults.standard.set(url, forKey: Self.baseURLDefaultsKey)
        UserDefaults.standard.set(aiEnabled, forKey: Self.enabledDefaultsKey)

        let token = trimmedToken
        if token.isEmpty {
            Keychain.delete(service: Self.service, account: Self.tokenAccount)
            UserDefaults.standard.removeObject(forKey: Self.tokenDefaultsKey)
            tokenStored = false
            tokenBackend = .none
            return true
        }
        appToken = token
        if Keychain.set(token, service: Self.service, account: Self.tokenAccount) {
            UserDefaults.standard.removeObject(forKey: Self.tokenDefaultsKey)
            tokenStored = true
            tokenBackend = .keychain
            return true
        }
        UserDefaults.standard.set(token, forKey: Self.tokenDefaultsKey)
        tokenStored = true
        tokenBackend = .userDefaults
        NSLog("[ReadyMCAT] Keychain unavailable; stored app token in UserDefaults fallback")
        return true
    }

    /// Flip the on/off toggle and persist it immediately.
    func setEnabled(_ on: Bool) {
        aiEnabled = on
        UserDefaults.standard.set(on, forKey: Self.enabledDefaultsKey)
    }

    /// Forget the proxy URL and app token (leaves the toggle as-is).
    func clear() {
        Keychain.delete(service: Self.service, account: Self.tokenAccount)
        UserDefaults.standard.removeObject(forKey: Self.tokenDefaultsKey)
        UserDefaults.standard.removeObject(forKey: Self.baseURLDefaultsKey)
        baseURL = ""
        appToken = ""
        tokenStored = false
        tokenBackend = .none
    }

    /// DEBUG-only: pre-fill the proxy config from launch env vars so the feature
    /// can be exercised on the Simulator without typing into the UI, e.g.
    ///   SIMCTL_CHILD_READYMCAT_PROXY_URL=http://127.0.0.1:8787 \
    ///   SIMCTL_CHILD_READYMCAT_APP_TOKEN=… xcrun simctl launch …
    /// Never runs in release, and only seeds empty fields so it can't clobber a
    /// real saved config.
    private func seedFromLaunchEnvironmentIfDebug() {
        #if DEBUG
        let env = ProcessInfo.processInfo.environment
        var changed = false
        if trimmedBaseURL.isEmpty,
           let url = env["READYMCAT_PROXY_URL"]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !url.isEmpty {
            baseURL = url
            changed = true
        }
        if trimmedToken.isEmpty,
           let tok = env["READYMCAT_APP_TOKEN"]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !tok.isEmpty {
            appToken = tok
            changed = true
        }
        if changed {
            _ = save()
            NSLog("[ReadyMCAT] seeded proxy config from launch env (DEBUG)")
        }
        #endif
    }
}
