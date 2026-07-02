// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The native app shell: a three-tab structure (Home · Study · Dashboard) that
// mirrors the desktop's Home / Study / Dashboard direction. Every tab is native
// SwiftUI backed by the shared Rust engine — there is no embedded web page.

import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel
    @State private var tab = 0
    @State private var autoFormat: Format?
    @State private var autoDiagnostic = false

    var body: some View {
        if let error = model.errorText {
            engineError(error)
        } else if !model.loaded {
            ProgressView("Opening the ReadyMCAT engine…")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            TabView(selection: $tab) {
                HomeView(goToStudy: { tab = 1 }, goToDashboard: { tab = 2 })
                    .tabItem { Label("Home", systemImage: "house.fill") }
                    .tag(0)

                StudyView()
                    .tabItem { Label("Study", systemImage: "square.stack.3d.up.fill") }
                    .tag(1)

                DashboardView()
                    .tabItem { Label("Dashboard", systemImage: "chart.bar.fill") }
                    .tag(2)

                SyncView()
                    .tabItem { Label("Sync", systemImage: "arrow.triangle.2.circlepath") }
                    .tag(3)
            }
            .tint(Palette.accent)
            // Deterministic launch routing for screenshots/verification, e.g.
            // SIMCTL_CHILD_READYMCAT_TAB=dashboard or READYMCAT_REVIEW=mcq.
            .fullScreenCover(item: $autoFormat) { fmt in
                ReviewSessionView(format: fmt).environmentObject(model)
            }
            .fullScreenCover(isPresented: $autoDiagnostic) {
                DiagnosticView().environmentObject(model)
            }
            .onAppear(perform: applyLaunchRouting)
        }
    }

    private func applyLaunchRouting() {
        let env = ProcessInfo.processInfo.environment
        switch env["READYMCAT_TAB"] {
        case "study": tab = 1
        case "dashboard": tab = 2
        default: break
        }
        if let raw = env["READYMCAT_REVIEW"], let fmt = Format(rawValue: raw) {
            autoFormat = fmt
        }
        if env["READYMCAT_DIAGNOSTIC"] != nil { autoDiagnostic = true }
    }

    private func engineError(_ text: String) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Label("Couldn't open the engine", systemImage: "exclamationmark.triangle.fill")
                    .font(.headline).foregroundStyle(Palette.danger)
                Text(text)
                    .font(.system(.footnote, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
