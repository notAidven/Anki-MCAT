// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Native Dashboard — the SwiftUI rebuild of
// ts/routes/readymcat-dashboard/Dashboard.svelte. Three co-equal honest scores
// (Memory / Performance / Readiness), each a range with a confidence chip and an
// honest give-up state, plus outline coverage, "what to study next", and a
// per-topic breakdown. All values are decoded from the shared engine's
// PointsAtStakeResponse (see PointsAtStake.swift) — nothing is invented here.

import SwiftUI

private let MIN_REVIEWS = 200.0
private let MIN_COVERAGE = 0.5
private let MIN_ATTEMPTS = 30.0
private let SCORE_MIN = 472.0
private let SCORE_MAX = 528.0

private func scorePos(_ s: Double) -> Double {
    max(0, min(1, (s - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)))
}

struct DashboardView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        NavigationStack {
            ScrollView {
                if let p = model.points, model.pointsError == nil {
                    VStack(alignment: .leading, spacing: 12) {
                        header
                        memoryCard(p)
                        performanceCard(p)
                        readinessCard(p)
                        coverageCard(p)
                        studyNextCard(p)
                        topicBreakdown(p)
                    }
                    .padding(16)
                } else {
                    notConfigured
                }
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Honest Scores")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { model.refresh() } label: { Image(systemName: "arrow.clockwise") }
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Three separate, honest scores")
                .font(.title3.weight(.bold))
            Text("Memory, Performance and Readiness — each a range with a confidence level, each hidden until there's enough evidence to back it up.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var notConfigured: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Taxonomy not configured", systemImage: "exclamationmark.triangle")
                .font(.headline).foregroundStyle(Palette.warn)
            Text("The dashboard needs taxonomy.json mapping the deck's tags to the AAMC outline, placed next to the collection.")
                .font(.footnote).foregroundStyle(.secondary)
            if let e = model.pointsError {
                Text(e).font(.caption.monospaced()).foregroundStyle(.tertiary)
            }
        }
        .padding(16)
    }

    // MARK: - Memory

    private func memoryCard(_ p: PointsAtStake) -> some View {
        let m = p.memory
        let ready = p.meetsDataThreshold
        let margin = (m.rangeHigh - m.rangeLow) / 2 * 100
        return StatCard(eyebrow: "Memory", tag: "recall right now", giveUp: !ready) {
            if ready {
                Text("\(pct(m.rangeLow))–\(pct(m.rangeHigh))")
                    .font(.system(size: 34, weight: .heavy)).foregroundStyle(Palette.accent)
                ConfidenceChip(Confidence.fromFraction(marginPoints: margin),
                               detail: "±\(String(format: "%.1f", margin))%")
                Text("Point ≈ \(pct(m.mean)) · FSRS recall across \(m.gradedCards) cards.")
                    .font(.caption).foregroundStyle(.secondary)
                GaugeBar(low: m.rangeLow, high: m.rangeHigh, mean: m.mean, tint: Palette.accent,
                         labels: ("0%", "50%", "100%"))
            } else {
                GiveUp(note: "Hidden until \(Int(MIN_REVIEWS)) graded reviews and \(pct(MIN_COVERAGE)) coverage.") {
                    Meter(title: "Reviews", value: "\(m.gradedReviews) / \(Int(MIN_REVIEWS))",
                          progress: min(1, Double(m.gradedReviews) / MIN_REVIEWS), tint: Palette.accent)
                    Meter(title: "Coverage", value: "\(pct(p.coverage.fraction)) / \(pct(MIN_COVERAGE))",
                          progress: min(1, p.coverage.fraction / MIN_COVERAGE), tint: Palette.accent)
                }
            }
        }
    }

    // MARK: - Performance

    private func performanceCard(_ p: PointsAtStake) -> some View {
        let perf = p.performance
        let margin = (perf.rangeHigh - perf.rangeLow) / 2 * 100
        return StatCard(eyebrow: "Performance", tag: "practice-question accuracy",
                        giveUp: !perf.meetsDataThreshold) {
            if perf.meetsDataThreshold {
                Text("\(pct(perf.rangeLow))–\(pct(perf.rangeHigh))")
                    .font(.system(size: 34, weight: .heavy)).foregroundStyle(Palette.accent)
                ConfidenceChip(Confidence.fromFraction(marginPoints: margin),
                               detail: "±\(String(format: "%.1f", margin))%")
                Text("Point ≈ \(pct(perf.mean)) · \(perf.hits)/\(perf.attempts) first tries correct on practice questions.")
                    .font(.caption).foregroundStyle(.secondary)
                GaugeBar(low: perf.rangeLow, high: perf.rangeHigh, mean: perf.mean, tint: Palette.review,
                         labels: ("0%", "50%", "100%"))
            } else {
                GiveUp(note: "First-attempt accuracy on MCQ / free-response / passage cards, hidden until \(Int(MIN_ATTEMPTS)) attempts.") {
                    Meter(title: "Attempts", value: "\(perf.attempts) / \(Int(MIN_ATTEMPTS))",
                          progress: min(1, Double(perf.attempts) / MIN_ATTEMPTS), tint: Palette.review)
                }
            }
        }
    }

    // MARK: - Readiness

    private func readinessCard(_ p: PointsAtStake) -> some View {
        let r = p.readiness
        let margin = (r.rangeHigh - r.rangeLow) / 2
        return StatCard(eyebrow: "Readiness", tag: "heuristic · 472–528",
                        giveUp: !r.meetsDataThreshold, accent: true) {
            if r.meetsDataThreshold {
                Text("\(Int(r.rangeLow))–\(Int(r.rangeHigh))")
                    .font(.system(size: 34, weight: .heavy)).foregroundStyle(Palette.accent)
                ConfidenceChip(Confidence.fromScore(marginPoints: margin),
                               detail: "±\(Int(margin))")
                Text("Projected ≈ \(Int(r.point)) on the 472–528 scale.")
                    .font(.caption).foregroundStyle(.secondary)
                GaugeBar(low: scorePos(r.rangeLow), high: scorePos(r.rangeHigh),
                         mean: scorePos(r.point), tint: Palette.warn,
                         labels: ("472", "500", "528"))
                caveat("Heuristic projection from Performance + Memory — uncalibrated, not a real MCAT score.")
            } else {
                GiveUp(note: "Projected only once both Memory and Performance have enough evidence.") {
                    caveat("When shown it is a heuristic, uncalibrated projection — never a real MCAT score.")
                }
            }
        }
    }

    private func caveat(_ text: String) -> some View {
        Text(text).font(.caption2).foregroundStyle(Palette.warn)
            .padding(.top, 6)
    }

    // MARK: - Coverage

    private func coverageCard(_ p: PointsAtStake) -> some View {
        let c = p.coverage
        return Card {
            VStack(alignment: .leading, spacing: 8) {
                Eyebrow("Outline coverage")
                Text("\(c.categoriesCovered) / \(c.categoriesTotal) AAMC categories")
                    .font(.subheadline.weight(.semibold))
                Text("\(pct(c.fraction)) of the outline · \(pct(c.weightedFraction)) by exam weight")
                    .font(.caption).foregroundStyle(.secondary)
                Bar(progress: c.fraction, tint: Palette.accent)
            }
        }
    }

    // MARK: - What to study next

    private func studyNextCard(_ p: PointsAtStake) -> some View {
        Card {
            VStack(alignment: .leading, spacing: 8) {
                Eyebrow("What to study next")
                Text("Ordering only — not a score. Highest points at stake = topic weight × your weakness (\(p.rankedCardCount) due cards ranked).")
                    .font(.caption).foregroundStyle(.secondary)
                ForEach(Array(p.studyNext.prefix(5))) { t in
                    HStack(spacing: 10) {
                        Text(t.category).font(.footnote.weight(.bold))
                            .foregroundStyle(Palette.accent).frame(width: 34, alignment: .leading)
                        Text(t.name).font(.footnote).lineLimit(1)
                        Spacer()
                        Text(String(format: "%.1f", t.points)).font(.footnote.weight(.bold))
                    }
                    .padding(.vertical, 4)
                    Divider()
                }
            }
        }
    }

    // MARK: - Per-topic breakdown

    private func topicBreakdown(_ p: PointsAtStake) -> some View {
        let byWeight = p.topics.sorted { $0.topicWeight > $1.topicWeight }
        let withData = p.topics.filter { $0.gradedCards > 0 }.count
        let accByCat = Dictionary(uniqueKeysWithValues: p.performance.topics.map { ($0.category, $0) })
        return Card {
            DisclosureGroup {
                VStack(spacing: 0) {
                    ForEach(byWeight) { t in
                        HStack(spacing: 8) {
                            Text(t.category).font(.caption.weight(.bold)).foregroundStyle(Palette.accent)
                                .frame(width: 30, alignment: .leading)
                            Text(t.name).font(.caption).lineLimit(1)
                            Spacer()
                            Text("\(t.gradedCards)/\(t.totalCards)")
                                .font(.caption2).foregroundStyle(.secondary)
                            if let a = accByCat[t.category], a.attempts > 0 {
                                Text(pct(a.accuracy)).font(.caption2.monospaced())
                                    .frame(width: 40, alignment: .trailing)
                            } else {
                                Text("—").font(.caption2).foregroundStyle(.tertiary)
                                    .frame(width: 40, alignment: .trailing)
                            }
                        }
                        .padding(.vertical, 5)
                        Divider()
                    }
                }
                .padding(.top, 8)
            } label: {
                Eyebrow("Per-topic breakdown")
                Text("\(withData) with data · \(p.topics.count - withData) no data · \(p.topics.count) AAMC categories")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Reusable dashboard components

struct Card<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(Color(.secondarySystemGroupedBackground),
                        in: RoundedRectangle(cornerRadius: 14))
    }
}

struct Eyebrow: View {
    let text: String
    init(_ text: String) { self.text = text }
    var body: some View {
        Text(text.uppercased())
            .font(.caption2.weight(.bold)).tracking(0.6)
            .foregroundStyle(.secondary)
    }
}

struct StatCard<Content: View>: View {
    let eyebrow: String
    let tag: String
    var giveUp: Bool = false
    var accent: Bool = false
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Eyebrow(eyebrow)
                Spacer()
                Text(tag).font(.caption2).foregroundStyle(.tertiary)
            }
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground),
                    in: RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: giveUp ? [5] : []))
                .foregroundStyle(accent ? Palette.accent.opacity(0.35) : Color(.separator).opacity(0.4))
        )
    }
}

struct ConfidenceChip: View {
    let level: Confidence
    let detail: String
    init(_ level: Confidence, detail: String) { self.level = level; self.detail = detail }
    var body: some View {
        Text("\(level.label) · \(detail)")
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 10).padding(.vertical, 4)
            .foregroundStyle(level.color)
            .background(level.color.opacity(0.12), in: Capsule())
            .overlay(Capsule().stroke(level.color.opacity(0.4)))
    }
}

struct GiveUp<Content: View>: View {
    let note: String
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Not enough data").font(.title3.weight(.bold)).foregroundStyle(.secondary)
            Text("Needs evidence")
                .font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
                .padding(.horizontal, 10).padding(.vertical, 4)
                .overlay(Capsule().stroke(style: StrokeStyle(lineWidth: 1, dash: [4]))
                    .foregroundStyle(Color(.separator)))
            Text(note).font(.caption).foregroundStyle(.secondary)
            content
        }
    }
}

struct Meter: View {
    let title: String
    let value: String
    let progress: Double
    let tint: Color
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(title).font(.caption)
                Spacer()
                Text(value).font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            Bar(progress: progress, tint: progress >= 1 ? Palette.review : tint)
        }
    }
}

struct Bar: View {
    let progress: Double
    let tint: Color
    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Color(.tertiarySystemGroupedBackground))
                Capsule().fill(tint)
                    .frame(width: max(0, min(1, progress)) * geo.size.width)
            }
        }
        .frame(height: 8)
    }
}

/// Interval gauge: a shaded band shows the range, a tick marks the point estimate.
struct GaugeBar: View {
    let low: Double
    let high: Double
    let mean: Double
    let tint: Color
    let labels: (String, String, String)

    var body: some View {
        VStack(spacing: 4) {
            GeometryReader { geo in
                let w = geo.size.width
                ZStack(alignment: .leading) {
                    Capsule().fill(Color(.tertiarySystemGroupedBackground)).frame(height: 12)
                    Capsule().fill(tint.opacity(0.45))
                        .frame(width: max(6, (high - low) * w), height: 12)
                        .offset(x: low * w)
                    RoundedRectangle(cornerRadius: 2).fill(tint)
                        .frame(width: 3, height: 18)
                        .offset(x: mean * w - 1.5)
                }
                .frame(height: 18)
            }
            .frame(height: 18)
            HStack {
                Text(labels.0); Spacer(); Text(labels.1); Spacer(); Text(labels.2)
            }
            .font(.caption2).foregroundStyle(.tertiary)
        }
        .padding(.top, 4)
    }
}
