// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The native renderer for an AI-GENERATED teach-on-miss ladder — the SwiftUI
// equivalent of the desktop's ts/reviewer/teach_on_miss.ts flow for a runtime
// `{q,a}` ladder. Unlike the authored MCQ/type-in rungs (which are graded), a
// generated rung is a retrieve-BEFORE-reveal flashcard step, mirroring the
// desktop:
//
//   show guiding question  ->  "Reveal sub-answer"  ->  sub-answer + self-mark
//   (Got it / Missed it)   ->  next rung  ->  … -> back to the original question
//
// Retrieve-first is the whole point (ReadyMCAT SPOV 1): the answer is hidden
// until the student has tried. When the ladder finishes, the reviewer re-asks
// the ORIGINAL card and grades it (Again + struggling on a second miss), exactly
// like the authored path.

import SwiftUI

/// Walks a generated `[{q,a}]` ladder one rung at a time, then calls `onDone`.
struct GeneratedLadderView: View {
    let rungs: [LadderRung]
    let tint: Color
    let onDone: () -> Void

    @State private var index = 0
    @State private var revealed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            AIBadgeHeader(step: "Guiding question \(index + 1) of \(rungs.count)")
            if rungs.indices.contains(index) {
                rungCard(rungs[index])
            }
        }
    }

    @ViewBuilder
    private func rungCard(_ rung: LadderRung) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text("TRY TO ANSWER THIS FIRST")
                    .font(.caption2.weight(.bold)).tracking(0.5).foregroundStyle(.secondary)
                Text(rung.q.plainText).font(.headline).fixedSize(horizontal: false, vertical: true)
            }
            .cardSurface()

            if revealed {
                ExplanationBox(label: "Sub-answer", text: rung.a, tint: Palette.review)
                Text("Did you retrieve this correctly?")
                    .font(.footnote).foregroundStyle(.secondary)
                HStack(spacing: 10) {
                    SelfMarkButton(title: "Got it", color: Palette.review) { advance() }
                    SelfMarkButton(title: "Missed it", color: Palette.danger) { advance() }
                }
            } else {
                Text("Retrieve it yourself, then reveal the answer.")
                    .font(.footnote).foregroundStyle(.secondary)
                PrimaryButton("Reveal sub-answer", tint: tint) { revealed = true }
            }
        }
    }

    private func advance() {
        if index + 1 < rungs.count {
            index += 1
            revealed = false
        } else {
            onDone()
        }
    }
}

/// Shown while a ladder is being generated for a card with no authored ladder.
struct GeneratingLadderView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            AIBadgeHeader(step: "Generating")
            VStack(spacing: 12) {
                ProgressView()
                Text("Building your guiding questions…")
                    .font(.headline)
                Text("Generating a short retrieval ladder from this card.")
                    .font(.footnote).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            .cardSurface()
        }
    }
}

/// Distinct header so it's unmistakable in-app (and in screenshots) that this
/// ladder was generated at runtime rather than authored.
private struct AIBadgeHeader: View {
    let step: String
    var body: some View {
        HStack(spacing: 8) {
            Label("AI teach-on-miss", systemImage: "sparkles")
                .font(.caption2.weight(.heavy))
                .padding(.horizontal, 8).padding(.vertical, 4)
                .background(Palette.brand, in: Capsule()).foregroundStyle(.white)
            Text("Generated for this card")
                .font(.caption2).foregroundStyle(.secondary).lineLimit(1)
            Spacer()
            Text(step).font(.caption2).foregroundStyle(.secondary)
        }
    }
}

private struct SelfMarkButton: View {
    let title: String
    let color: Color
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(title).font(.subheadline.weight(.bold))
                .frame(maxWidth: .infinity).padding(.vertical, 12)
                .background(color, in: RoundedRectangle(cornerRadius: 10))
                .foregroundStyle(.white)
        }
    }
}
