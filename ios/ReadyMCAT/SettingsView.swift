// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The Settings tab: point the app at the ReadyMCAT proxy (a Cloudflare Worker)
// to turn on runtime AI generation of teach-on-miss ladders for cards that have
// no authored one. The OpenAI key is NOT entered here — it lives server-side in
// the Worker. On device we keep only a non-secret Proxy Base URL and an optional
// LOW-VALUE app token (see ProxyConfigStore). With AI off or no URL, generation
// stays off and the app behaves exactly as before — authored ladders only.
//
// A "Run AI ladder demo" button seeds a single authorless demo card and opens it
// so the AI path is reachable in-app on the Simulator.

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View { SettingsForm(config: model.proxyConfig, ai: model.ai) }
}

private struct SettingsForm: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var config: ProxyConfigStore
    @ObservedObject var ai: AILadderService

    @State private var demoDeck: DeckRef?
    @State private var seedFailed = false

    private var enabledBinding: Binding<Bool> {
        Binding(get: { config.aiEnabled }, set: { config.setEnabled($0) })
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle("Generate ladders with AI", isOn: enabledBinding)

                    TextField("https://your-worker.workers.dev", text: $config.baseURL)
                        .textContentType(.URL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    SecureField("App token (optional)", text: $config.appToken)
                        .textContentType(.password)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    HStack {
                        Button {
                            _ = config.save()
                        } label: {
                            Label("Save", systemImage: "checkmark.circle.fill")
                        }
                        Spacer()
                        if !config.trimmedBaseURL.isEmpty || config.tokenStored {
                            Button(role: .destructive) { config.clear() } label: {
                                Label("Remove", systemImage: "trash")
                            }
                        }
                    }
                } header: {
                    Text("AI ladder proxy")
                } footer: {
                    Text("The app calls YOUR proxy (a Cloudflare Worker) over HTTPS — never OpenAI directly. The proxy holds the OpenAI key as a server-side secret and generates the ladder (model \(LadderGen.defaultModel)). The Base URL is not secret; the App Token is a low-value key that just gates who may call your proxy. For local testing point this at your `wrangler dev` URL, e.g. http://127.0.0.1:8787.")
                }

                Section("Status") {
                    HStack(spacing: 10) {
                        Image(systemName: ai.isEnabled ? "sparkles" : "sparkles.slash")
                            .foregroundStyle(ai.isEnabled ? Palette.review : .secondary)
                        Text(ai.isEnabled
                             ? "AI ladder generation is ON"
                             : "AI ladder generation is OFF")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    if !config.trimmedBaseURL.isEmpty {
                        Label("Proxy: \(config.trimmedBaseURL)", systemImage: "network")
                            .font(.caption).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
                    }
                    if config.tokenStored {
                        Label("App token stored in \(config.tokenBackend.rawValue)", systemImage: "checkmark.circle.fill")
                            .font(.caption).foregroundStyle(Palette.review)
                    }
                    if let summary = ai.lastSummary {
                        Text("Last generation — \(summary)")
                            .font(.caption.monospaced()).foregroundStyle(.secondary)
                    }
                }

                Section {
                    Button {
                        if let id = model.seedAIDemoDeck() {
                            demoDeck = DeckRef(id: id)
                        } else {
                            seedFailed = true
                        }
                    } label: {
                        Label("Run AI ladder demo", systemImage: "play.circle.fill")
                    }
                    .disabled(!ai.isEnabled)
                    if seedFailed {
                        Text("Couldn't seed the demo card.")
                            .font(.caption).foregroundStyle(Palette.danger)
                    }
                } header: {
                    Text("Try it")
                } footer: {
                    Text("Seeds one authorless card (no ladder) in its own deck and opens it. Answer it wrong to see a guiding ladder generated live, before the answer is revealed.")
                }

                Section {
                    Text("No OpenAI key on this phone. Moving the key to a server-side proxy removes the mobile tradeoff of the earlier build (any key shipped in an app can be extracted from a jailbroken/instrumented device). The high-value OpenAI key now lives only in the Worker; the phone holds just a non-secret URL and a low-value, easily-rotated app token. Harden the proxy further with rate-limiting, Cloudflare Access, or App Attest — see the proxy README.")
                        .font(.footnote).foregroundStyle(.secondary)
                } header: {
                    Text("About the proxy")
                }
            }
            .navigationTitle("Settings")
            .fullScreenCover(item: $demoDeck) { ref in
                ReviewSessionView(format: .fr, deckIdOverride: ref.id, titleOverride: "AI Demo")
                    .environmentObject(model)
            }
        }
    }
}
