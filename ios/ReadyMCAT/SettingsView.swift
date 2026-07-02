// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The Settings tab: enter an OpenAI API key to turn on runtime AI generation of
// teach-on-miss ladders for cards that have no authored one. The key is stored
// in the Keychain (see APIKeyStore). With no key, generation stays off and the
// app behaves exactly as before — authored ladders only.
//
// A "Run AI ladder demo" button seeds a single authorless demo card and opens it
// so the AI path is reachable in-app on the Simulator without any launch env.

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View { SettingsForm(keyStore: model.keyStore, ai: model.ai) }
}

private struct SettingsForm: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var keyStore: APIKeyStore
    @ObservedObject var ai: AILadderService

    @State private var demoDeck: DeckRef?
    @State private var seedFailed = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SecureField("sk-…", text: $keyStore.key)
                        .textContentType(.password)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    HStack {
                        Button {
                            _ = keyStore.save()
                        } label: {
                            Label("Save key", systemImage: "key.fill")
                        }
                        .disabled(keyStore.trimmedKey.isEmpty)
                        Spacer()
                        if keyStore.stored {
                            Button(role: .destructive) { keyStore.clear() } label: {
                                Label("Remove", systemImage: "trash")
                            }
                        }
                    }
                } header: {
                    Text("OpenAI API key")
                } footer: {
                    Text("Stored in the device Keychain. Used only to generate a short guiding-question ladder when you miss a card that has no authored one — model \(LadderGen.defaultModel), calling api.openai.com directly. Your key never leaves the device except in that request.")
                }

                Section("Status") {
                    HStack(spacing: 10) {
                        Image(systemName: ai.isEnabled ? "sparkles" : "sparkles.slash")
                            .foregroundStyle(ai.isEnabled ? Palette.review : .secondary)
                        Text(ai.isEnabled
                             ? "AI ladder generation is ON"
                             : "AI ladder generation is OFF (no key)")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    if keyStore.stored {
                        Label("Key stored in \(keyStore.backend.rawValue)", systemImage: "checkmark.circle.fill")
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
                    Text("Security tradeoff: any API key shipped inside a mobile app can, in principle, be extracted from a jailbroken or instrumented device. This in-app key is fine for personal use and this MVP (Keychain-encrypted, this-device-only); a production build should proxy generation through a server so the key never lives on the phone.")
                        .font(.footnote).foregroundStyle(.secondary)
                } header: {
                    Text("About the mobile key")
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
