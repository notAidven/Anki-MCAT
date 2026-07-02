// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The minimal Sync tab: point the app at a (self-hosted) Anki sync server, log
// in, and sync. Everything here just drives SyncManager, which uses Anki's own
// collection-sync protocol under the hood.

import SwiftUI

struct SyncView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View { SyncForm(sync: model.sync) }
}

private struct SyncForm: View {
    @ObservedObject var sync: SyncManager

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    LabeledField(label: "Server URL", systemImage: "network") {
                        TextField("http://127.0.0.1:8080/", text: $sync.endpoint)
                            .textContentType(.URL)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }
                    LabeledField(label: "Username", systemImage: "person") {
                        TextField("username", text: $sync.username)
                            .textContentType(.username)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }
                    LabeledField(label: "Password", systemImage: "lock") {
                        SecureField("password", text: $sync.password)
                            .textContentType(.password)
                    }
                } header: {
                    Text("Sync server")
                } footer: {
                    Text("Point at your own Anki sync server. Reviews sync both ways using Anki's own protocol, so nothing is lost or double-counted.")
                }

                Section {
                    Toggle("Keep this device's cards on conflict", isOn: $sync.fullSyncPrefersUpload)
                } footer: {
                    Text("If both sides changed independently, upload this device's collection (on) or replace it with the server's (off).")
                }

                Section {
                    Button {
                        sync.loginNow()
                    } label: {
                        Label("Log in", systemImage: "key.fill")
                    }
                    .disabled(sync.busy || sync.endpoint.isEmpty || sync.username.isEmpty)

                    Button {
                        sync.syncNow()
                    } label: {
                        HStack {
                            Label("Sync now", systemImage: "arrow.triangle.2.circlepath")
                            if sync.busy { Spacer(); ProgressView() }
                        }
                    }
                    .disabled(sync.busy || !sync.isConfigured)
                }

                Section("Status") {
                    HStack(spacing: 10) {
                        statusIcon
                        Text(sync.statusText)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    if let at = sync.lastSyncedAt {
                        Text("Last synced \(at.formatted(date: .abbreviated, time: .standard))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Sync")
        }
    }

    @ViewBuilder
    private var statusIcon: some View {
        switch sync.phase {
        case .idle:
            Image(systemName: "cloud").foregroundStyle(.secondary)
        case .syncing:
            ProgressView()
        case .success:
            Image(systemName: "checkmark.circle.fill").foregroundStyle(Palette.review)
        case .failure:
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Palette.danger)
        }
    }
}

/// A left-aligned label + trailing field row, so the Form reads cleanly.
private struct LabeledField<Content: View>: View {
    let label: String
    let systemImage: String
    @ViewBuilder var content: Content

    var body: some View {
        HStack {
            Label(label, systemImage: systemImage)
                .foregroundStyle(.secondary)
                .frame(width: 120, alignment: .leading)
            content
                .multilineTextAlignment(.trailing)
                .frame(maxWidth: .infinity, alignment: .trailing)
        }
    }
}
