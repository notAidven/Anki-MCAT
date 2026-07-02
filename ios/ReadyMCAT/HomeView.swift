// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Native Home hub — the SwiftUI rebuild of ts/routes/readymcat-home/Home.svelte:
// a status strip with the three honest scores, four format tiles showing real
// due counts (from the shared engine's deck due tree), a "study next" shortcut
// and a diagnostic entry point. Every number is a live read off the engine.

import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    let goToStudy: () -> Void
    let goToDashboard: () -> Void

    @State private var active: Format?
    @State private var showDiagnostic = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    statusStrip
                    tiles
                    studyNext
                    diagnosticCard
                    Text("Updated \(model.lastUpdated.formatted(date: .abbreviated, time: .shortened))")
                        .font(.caption2).foregroundStyle(.tertiary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                }
                .padding(16)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("ReadyMCAT")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { model.refresh() } label: { Image(systemName: "arrow.clockwise") }
                }
            }
            .fullScreenCover(item: $active) { fmt in
                ReviewSessionView(format: fmt).environmentObject(model)
            }
            .fullScreenCover(isPresented: $showDiagnostic) {
                DiagnosticView().environmentObject(model)
            }
        }
    }

    // MARK: status strip — the three scores + coverage

    private var statusStrip: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Palette.brand)
                    .frame(width: 30, height: 30)
                Text("Continue studying")
                    .font(.title3.weight(.heavy))
                Spacer()
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    if let p = model.points, model.pointsError == nil {
                        scorePill("Memory", p.meetsDataThreshold
                                  ? "\(pct(p.memory.rangeLow))–\(pct(p.memory.rangeHigh))" : nil)
                        scorePill("Performance", p.performance.meetsDataThreshold
                                  ? "\(pct(p.performance.rangeLow))–\(pct(p.performance.rangeHigh))" : nil)
                        scorePill("Readiness", p.readiness.meetsDataThreshold
                                  ? "\(Int(p.readiness.rangeLow))–\(Int(p.readiness.rangeHigh))" : nil)
                        scorePill("Coverage", pct(p.coverage.fraction),
                                  sub: "\(p.coverage.categoriesCovered)/\(p.coverage.categoriesTotal)")
                    } else {
                        pill(text: "Scores: taxonomy not configured", color: Palette.warn)
                    }
                }
            }
        }
    }

    private func scorePill(_ label: String, _ value: String?, sub: String? = nil) -> some View {
        HStack(spacing: 5) {
            Text(label).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            if let value {
                Text(value).font(.caption.weight(.heavy))
                if let sub { Text(sub).font(.caption2).foregroundStyle(.tertiary) }
            } else {
                Text("not enough data").font(.caption2).foregroundStyle(.tertiary)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 7)
        .background(Color(.secondarySystemGroupedBackground), in: Capsule())
        .overlay(Capsule().stroke(Color(.separator).opacity(0.5)))
    }

    private func pill(text: String, color: Color) -> some View {
        Text(text)
            .font(.caption.weight(.semibold)).foregroundStyle(color)
            .padding(.horizontal, 12).padding(.vertical, 7)
            .background(color.opacity(0.12), in: Capsule())
    }

    // MARK: format tiles

    private var tiles: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 12),
                            GridItem(.flexible(), spacing: 12)], spacing: 12) {
            ForEach(Format.allCases) { fmt in
                let c = model.counts(for: fmt)
                FormatTile(format: fmt, present: c.present, due: c.due, total: c.total) {
                    if c.present { active = fmt }
                }
            }
        }
    }

    // MARK: what to study next

    private var studyNext: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("What to study next").font(.subheadline.weight(.bold))
                Spacer()
                Text("POINTS AT STAKE")
                    .font(.caption2.weight(.heavy)).foregroundStyle(Palette.danger)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Palette.danger.opacity(0.12), in: Capsule())
            }
            .padding(.bottom, 8)

            if let p = model.points, model.pointsError == nil {
                let top = Array(p.studyNext.prefix(4))
                if top.isEmpty {
                    Text("Nothing due right now — every topic is caught up.")
                        .font(.footnote).foregroundStyle(.secondary)
                } else {
                    ForEach(Array(top.enumerated()), id: \.element.id) { i, topic in
                        HStack(spacing: 10) {
                            Text("\(i + 1)")
                                .font(.caption.weight(.heavy))
                                .frame(width: 22, height: 22)
                                .background(i == 0 ? Palette.warn : Color(.tertiarySystemGroupedBackground),
                                            in: RoundedRectangle(cornerRadius: 6))
                                .foregroundStyle(i == 0 ? .black : .secondary)
                            Text(topic.name).font(.footnote.weight(.semibold)).lineLimit(1)
                            Spacer()
                            Text(topic.gradedCards > 0
                                 ? "\(pct(1 - topic.studentWeakness)) recall" : "no data yet")
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 6)
                        if i < top.count - 1 { Divider() }
                    }
                }
                Button(action: goToDashboard) {
                    Text("Ranked by topic weight × your weakness — see full breakdown →")
                        .font(.caption.weight(.semibold)).foregroundStyle(Palette.accent)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.top, 8)
            } else {
                Text("Needs taxonomy.json to rank topics. See the Dashboard for details.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 14))
    }

    // MARK: diagnostic

    private var diagnosticCard: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Diagnostic Quiz").font(.subheadline.weight(.bold))
                Text("Seeds what to study first — never scored")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Button("Take diagnostic") { showDiagnostic = true }
                .font(.caption.weight(.bold))
                .padding(.horizontal, 14).padding(.vertical, 8)
                .background(Palette.accent.opacity(0.14), in: Capsule())
                .foregroundStyle(Palette.accent)
        }
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 14))
    }
}

/// One format launch tile (Multiple Choice / Free Response / Passage / CARS).
struct FormatTile: View {
    let format: Format
    let present: Bool
    let due: Int
    let total: Int
    let action: () -> Void

    private var dueLabel: String {
        if !present { return "NOT LOADED" }
        if due <= 0 { return "UP TO DATE" }
        return "\(due) DUE"
    }

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    Image(systemName: Palette.icon(for: format))
                        .font(.title3)
                    Spacer()
                    Text(dueLabel)
                        .font(.caption2.weight(.heavy))
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(.white.opacity(0.22), in: Capsule())
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(format.title).font(.headline)
                    Text(format.blurb).font(.caption2).opacity(0.9)
                }
                .padding(.top, 12)
                Spacer(minLength: 10)
                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("\(total)").font(.system(size: 26, weight: .black))
                        Text("total \(format.noun)").font(.caption2).opacity(0.8)
                    }
                    Spacer()
                    if present {
                        Image(systemName: "arrow.right")
                            .font(.footnote.weight(.bold))
                            .foregroundStyle(Palette.tint(for: format))
                            .frame(width: 32, height: 32)
                            .background(.white.opacity(0.94), in: Circle())
                    }
                }
            }
            .padding(16)
            .frame(height: 160, alignment: .topLeading)
            .foregroundStyle(.white)
            .background(Palette.gradient(for: format))
            .clipShape(RoundedRectangle(cornerRadius: 18))
            .opacity(present ? 1 : 0.55)
        }
        .buttonStyle(.plain)
        .disabled(!present)
    }
}
