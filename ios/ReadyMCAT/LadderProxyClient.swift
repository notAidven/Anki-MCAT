// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The one bit of IO for AI generation, AFTER the OpenAI key moved off device.
//
// Instead of calling api.openai.com directly with an on-device key (the old
// `LadderGen.openAIChat`), the phone now POSTs a STRUCTURED card payload to the
// ReadyMCAT proxy (a Cloudflare Worker — ios/backend/openai-proxy). The Worker
// holds the OpenAI key server-side, BUILDS the exact same prompt itself (so a
// leaked app token can't drive arbitrary prompts), calls OpenAI, and returns the
// raw completion text as `{ "content": "…" }`.
//
// Crucially this returns the SAME `String` the desktop's `openai_chat` (and the
// old `openAIChat`) returned — the raw assistant completion — so LadderGen's
// tolerant `[{q,a}]` parser and the three deterministic guardrails (schema /
// answer-leak / grounding) run byte-for-byte unchanged on top of it. The prompt
// now lives server-side; the parser + guardrails + retrieve-before-reveal flow
// stay on device.
//
// Foundation-only (no SwiftUI/app types), so it composes with the injectable
// `ChatFn` and stays unit-testable in isolation, exactly like the core it feeds.

import Foundation

enum LadderProxyClient {
    static let ladderPath = "/v1/ladder"

    /// POST the structured card context to the proxy and return the raw
    /// completion text (the `content` field). Throws `LadderGenError` on any
    /// transport/HTTP/shape problem so `generateLadder` falls back gracefully —
    /// identical error contract to the old direct-OpenAI path.
    static func generate(
        context: CardContext,
        baseURL: String,
        token: String,
        timeout: Int = LadderGen.defaultTimeoutSecs,
        session: URLSession = .shared
    ) async throws -> String {
        let base = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !base.isEmpty else { throw LadderGenError("proxy base URL is not set") }
        let root = base.hasSuffix("/") ? String(base.dropLast()) : base
        guard let url = URL(string: root + ladderPath) else {
            throw LadderGenError("bad proxy URL: \(base)")
        }

        // Structured payload — NOT a raw OpenAI body, NEVER a key. The Worker
        // builds the prompt from these fields (question/answer/source), matching
        // LadderGen.buildMessages / ladder_gen.build_messages server-side.
        let payload: [String: Any] = [
            "question": context.question,
            "answer": context.answer,
            "source": context.source,
        ]
        guard let body = try? JSONSerialization.data(withJSONObject: payload) else {
            throw LadderGenError("could not encode request body")
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = TimeInterval(timeout)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let bearer = token.trimmingCharacters(in: .whitespacesAndNewlines)
        if !bearer.isEmpty {
            request.setValue("Bearer \(bearer)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = body

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw LadderGenError("proxy request failed: \(error.localizedDescription)")
        }
        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            let detail = String(decoding: data.prefix(300), as: UTF8.self)
            throw LadderGenError("proxy HTTP \(http.statusCode): \(detail)")
        }
        guard
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let content = json["content"] as? String
        else {
            throw LadderGenError("unexpected proxy response shape")
        }
        return content
    }
}
