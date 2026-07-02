// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The Study tab: pick a format to study. Each row shows the live due/total count
// from the shared engine's deck due tree and launches the matching native
// reviewer session. The highest-due format is surfaced as a one-tap "study next".

import SwiftUI

struct StudyView: View {
    @EnvironmentObject private var model: AppModel
    @State private var active: Format?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let suggested = model.suggestedFormat {
                        studyNextCard(suggested)
                    }
                    VStack(spacing: 10) {
                        ForEach(Format.allCases) { fmt in
                            row(fmt)
                        }
                    }
                }
                .padding(16)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Study")
            .fullScreenCover(item: $active) { fmt in
                ReviewSessionView(format: fmt).environmentObject(model)
            }
        }
    }

    private func studyNextCard(_ fmt: Format) -> some View {
        let c = model.counts(for: fmt)
        return Button { active = fmt } label: {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("STUDY NEXT").font(.caption2.weight(.heavy)).tracking(0.6).opacity(0.9)
                    Text(fmt.title).font(.title3.weight(.bold))
                    Text("\(c.due) due · \(c.total) total \(fmt.noun)").font(.caption).opacity(0.9)
                }
                Spacer()
                Image(systemName: "play.circle.fill").font(.system(size: 40))
            }
            .padding(18)
            .foregroundStyle(.white)
            .background(Palette.gradient(for: fmt))
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
    }

    private func row(_ fmt: Format) -> some View {
        let c = model.counts(for: fmt)
        return Button { if c.present { active = fmt } } label: {
            HStack(spacing: 14) {
                Image(systemName: Palette.icon(for: fmt))
                    .font(.title3).foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(Palette.gradient(for: fmt), in: RoundedRectangle(cornerRadius: 10))
                VStack(alignment: .leading, spacing: 2) {
                    Text(fmt.title).font(.headline)
                    Text(fmt.blurb).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text(c.present ? "\(c.due)" : "—")
                        .font(.title3.weight(.heavy))
                        .foregroundStyle(c.due > 0 ? Palette.tint(for: fmt) : .secondary)
                    Text("due").font(.caption2).foregroundStyle(.secondary)
                }
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
            }
            .padding(14)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 14))
            .opacity(c.present ? 1 : 0.5)
        }
        .buttonStyle(.plain)
        .disabled(!c.present)
    }
}
