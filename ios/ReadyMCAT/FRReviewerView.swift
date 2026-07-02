// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The native free-response (type-in) reviewer with per-question teach-on-miss,
// reproducing ts/reviewer/fr.ts. A typed answer is auto-graded by the shared
// FreeResponseGrader (the Swift port of grade_free_response); on a miss it walks
// the note's guiding type-in ladder, then re-asks the prompt. Grading contract:
// first-try correct -> Good; anything needing the ladder -> Again (+ struggling
// when missed again).

import SwiftUI

struct FRReviewerView: View {
    let item: FRItem
    let tint: Color
    let onFinish: (ReviewOutcome) -> Void

    private enum Phase: Hashable { case main, ladder(Int), reattempt }
    @State private var phase: Phase = .main

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ReviewerHeader(title: item.subtopic.isEmpty ? "MCAT free response" : item.subtopic,
                               step: stepLabel)
                stepView
            }
            .padding(16)
        }
    }

    private var stepLabel: String {
        switch phase {
        case .main: return "Free response"
        case .ladder(let i): return "Guiding question \(i + 1) of \(item.subquestions.count)"
        case .reattempt: return "Back to the original prompt"
        }
    }

    @ViewBuilder
    private var stepView: some View {
        switch phase {
        case .main:
            FRMainStep(item: item, tint: tint, demoText: mainDemoText,
                       onCorrectFirst: { onFinish(.correctFirst) },
                       onWrong: { phase = item.subquestions.isEmpty ? .reattempt : .ladder(0) })
                .id("main")
        case .ladder(let i):
            FRLadderStep(sub: item.subquestions[i], index: i, total: item.subquestions.count,
                         tint: tint,
                         onNext: { phase = (i + 1 < item.subquestions.count) ? .ladder(i + 1) : .reattempt })
                .id("ladder\(i)")
        case .reattempt:
            FRReattemptStep(item: item, tint: tint,
                            onDone: { correct in
                                onFinish(correct ? .correctAfterLadder : .wrongAfterLadder)
                            })
                .id("reattempt")
        }
    }
}

// MARK: - "model answer" + "accepted" helpers (mirror fr.ts showModel / showAccepted)

private struct ModelAnswer: View {
    let text: String
    var body: some View {
        if !text.plainText.isEmpty {
            Text(.init("**Model answer.** \(text.plainText)"))
                .font(.subheadline).fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct AcceptedList: View {
    let accepted: [String]
    private var clean: [String] {
        accepted.filter {
            let low = $0.trimmingCharacters(in: .whitespaces).lowercased()
            return !low.isEmpty && !low.hasPrefix("tolerance") && !low.hasPrefix("unit")
        }
    }
    var body: some View {
        if !clean.isEmpty {
            Text(.init("**Accepted:** \(clean.prefix(6).joined(separator: " · "))"))
                .font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct FRMainStep: View {
    let item: FRItem
    let tint: Color
    let onCorrectFirst: () -> Void
    let onWrong: () -> Void
    @State private var correct: Bool?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            TypeInQuestion(stem: item.prompt, accepted: item.acceptedAnswers, keyTerms: item.keyTerms,
                           submitLabel: "Submit answer", tint: tint) { _, c in correct = c }
            if let correct {
                if correct {
                    ModelAnswer(text: item.modelAnswer)
                    ExplanationBox(label: "Explanation", text: item.explanation, tint: Palette.review)
                    PrimaryButton("Continue", tint: tint) { onCorrectFirst() }
                } else {
                    NoteBox(kind: .spaced,
                            text: "**Not quite.** Rather than just showing the answer, let's rebuild it with a few guiding questions.")
                    PrimaryButton("Start guiding questions", tint: tint) { onWrong() }
                }
            }
        }
    }
}

private struct FRLadderStep: View {
    let sub: FRSub
    let index: Int
    let total: Int
    let tint: Color
    let onNext: () -> Void
    @State private var correct: Bool?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            TypeInQuestion(stem: sub.stem, accepted: sub.acceptedAnswers, keyTerms: sub.keyTerms,
                           submitLabel: "Check", tint: tint) { _, c in correct = c }
            if let correct {
                if !correct { AcceptedList(accepted: sub.acceptedAnswers) }
                ExplanationBox(label: correct ? "Correct" : "Explanation", text: sub.explanation,
                               tint: correct ? Palette.review : tint)
                PrimaryButton(index == total - 1 ? "Back to the prompt" : "Next guiding question",
                              tint: tint) { onNext() }
            }
        }
    }
}

private struct FRReattemptStep: View {
    let item: FRItem
    let tint: Color
    let onDone: (Bool) -> Void
    @State private var correct: Bool?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            TypeInQuestion(stem: item.prompt, accepted: item.acceptedAnswers, keyTerms: item.keyTerms,
                           submitLabel: "Submit answer", tint: tint) { _, c in correct = c }
            if let correct {
                if correct {
                    NoteBox(kind: .spaced,
                            text: "**Not mastered yet.** Getting it right seconds after the scaffold isn't readiness. This card is scheduled for spaced re-retrieval — you'll need to recall it again in a later session for it to count.")
                    ModelAnswer(text: item.modelAnswer)
                    ExplanationBox(label: "Explanation", text: item.explanation, tint: Palette.review)
                } else {
                    NoteBox(kind: .struggle,
                            text: "**Here's the full answer — earned through real retrieval.** This card is flagged as struggling and scheduled for aggressive early re-retrieval; it returns fresh next session.")
                    AcceptedList(accepted: item.acceptedAnswers)
                    ModelAnswer(text: item.modelAnswer)
                    ExplanationBox(label: "Explanation", text: item.explanation)
                    ResourceLink(source: item.source, label: "open the source for this item")
                }
                PrimaryButton("Continue", tint: tint) { onDone(correct) }
            }
        }
    }
}
