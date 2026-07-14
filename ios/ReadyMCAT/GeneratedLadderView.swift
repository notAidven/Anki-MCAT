// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The native renderer for an AI-GENERATED teach-on-miss ladder — the SwiftUI
// equivalent of the desktop's ts/reviewer/teach_on_miss.ts flow for a runtime
// MCQ ladder. Each generated rung is an interactive multiple-choice question the
// student WORKS OUT by choosing, mirroring the desktop (and reusing the same
// `ChoiceQuestion` component as the authored MCQ/passage reviewers):
//
//   show guiding MCQ  ->  select an option  ->  Check  ->  correct/incorrect
//   feedback + one-line explanation  ->  next rung  ->  … -> back to the card
//
// Retrieve-first is the whole point (ReadyMCAT SPOV 1): the card's real answer
// stays hidden until the student has worked through the ladder. When it
// finishes, the reviewer re-asks the ORIGINAL card and grades it (Again +
// struggling on a second miss), exactly like the authored path.

import SwiftUI

/// Walks a generated MCQ ladder one rung at a time, then calls `onDone`.
struct GeneratedLadderView: View {
    let rungs: [LadderRung]
    let tint: Color
    let onDone: () -> Void

    @State private var index = 0
    @State private var correct: Bool?

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
            ChoiceQuestion(
                stem: rung.question, options: rung.options,
                correctIndex: rung.correctIndex, submitLabel: "Check", tint: tint
            ) { _, isCorrect in correct = isCorrect }
                .id(index)   // reset the choice's internal state per rung
            if let correct {
                ExplanationBox(label: correct ? "Correct" : "Explanation",
                               text: rung.explanation,
                               tint: correct ? Palette.review : tint)
                PrimaryButton(index == rungs.count - 1 ? "Back to the question" : "Next guiding question",
                              tint: tint) { advance() }
            }
        }
    }

    private func advance() {
        if index + 1 < rungs.count {
            index += 1
            correct = nil
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

