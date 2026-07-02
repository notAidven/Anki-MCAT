// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The native multiple-choice reviewer with per-question teach-on-miss, shared by
// the MCQ and Passage/CARS formats (they differ only by an optional passage
// panel). It reproduces the exact PRD flow of ts/reviewer/mcq.ts + passage.ts:
//
//   answer correct first try -> explanation -> Continue        (Good)
//   answer wrong -> walk the note's guiding sub-question ladder
//     each rung: select -> check -> explanation -> next
//     ladder done -> re-ask the MAIN question
//       correct now -> "not mastered, spaced" + explanation    (Again, corrected)
//       wrong again -> full explanation + resource             (Again, struggling)
//
// The sub-question ladder is the note's own `Subquestions` JSON (parsed in
// Content.swift) — pre-authored retrieval scaffolding, not the answer.

import SwiftUI

struct ChoiceReviewer: View {
    let title: String
    let passage: String?
    let question: String
    let options: [String]
    let correctIndex: Int
    let explanation: String
    let source: String
    let subs: [MCQSub]
    let tint: Color
    /// Grounding material + generator for the AI path (both nil-safe): used only
    /// when the card has NO authored `subs`. When `aiLadder` is nil (no key), a
    /// miss falls straight through to the normal reveal — today's behavior.
    var cardContext: CardContext? = nil
    var aiLadder: ((CardContext) async -> [LadderRung]?)? = nil
    let onFinish: (ReviewOutcome) -> Void

    private enum Phase: Hashable { case main, ladder(Int), generating, aiLadder, reattempt }
    @State private var phase: Phase = .main
    @State private var generatedRungs: [LadderRung] = []

    private var mainDemoChoice: Int? {
        guard Demo.active, !options.isEmpty else { return nil }
        return Demo.wantsCorrect ? correctIndex : (correctIndex + 1) % options.count
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ReviewerHeader(title: title, step: stepLabel)
                if let passage {
                    PassageDisclosure(passage: passage, expanded: passageExpanded)
                        .id(phaseKey)   // reset expansion per phase
                }
                stepView
            }
            .padding(16)
        }
    }

    private var phaseKey: String {
        switch phase {
        case .main: return "main"
        case .ladder(let i): return "ladder\(i)"
        case .generating: return "generating"
        case .aiLadder: return "aiLadder"
        case .reattempt: return "reattempt"
        }
    }

    private var passageExpanded: Bool {
        switch phase {
        case .ladder, .generating, .aiLadder: return false
        case .main, .reattempt: return true
        }
    }

    private var stepLabel: String {
        switch phase {
        case .main: return passage == nil ? "Multiple choice" : "Passage · multiple choice"
        case .ladder(let i): return "Guiding question \(i + 1) of \(subs.count)"
        case .generating: return "Generating guiding questions"
        case .aiLadder: return "AI guiding questions"
        case .reattempt: return "Back to the original question"
        }
    }

    /// After a first-try miss: authored ladder if present, else generate one via
    /// the LLM (retrieve-before-reveal), else fall back to a normal reveal.
    private func startAfterMiss() {
        if !subs.isEmpty {
            phase = .ladder(0)
        } else if let aiLadder, let cardContext {
            phase = .generating
            Task { @MainActor in
                let rungs = await aiLadder(cardContext)
                if let rungs, !rungs.isEmpty {
                    generatedRungs = rungs
                    phase = .aiLadder
                } else {
                    phase = .reattempt   // graceful fallback
                }
            }
        } else {
            phase = .reattempt
        }
    }

    @ViewBuilder
    private var stepView: some View {
        switch phase {
        case .main:
            MainChoiceStep(
                stem: question, options: options, correctIndex: correctIndex,
                explanation: explanation, tint: tint, demoChoice: mainDemoChoice,
                onCorrectFirst: { onFinish(.correctFirst) },
                onWrong: { startAfterMiss() }
            )
            .id("main")
        case .ladder(let i):
            LadderChoiceStep(
                sub: subs[i], index: i, total: subs.count, tint: tint,
                onNext: { phase = (i + 1 < subs.count) ? .ladder(i + 1) : .reattempt }
            )
            .id("ladder\(i)")
        case .generating:
            GeneratingLadderView().id("generating")
        case .aiLadder:
            GeneratedLadderView(rungs: generatedRungs, tint: tint,
                                onDone: { phase = .reattempt })
                .id("aiLadder")
        case .reattempt:
            ReattemptChoiceStep(
                stem: question, options: options, correctIndex: correctIndex,
                explanation: explanation, source: source, tint: tint,
                onDone: { correct in onFinish(correct ? .correctAfterLadder : .wrongAfterLadder) }
            )
            .id("reattempt")
        }
    }
}

private struct MainChoiceStep: View {
    let stem: String
    let options: [String]
    let correctIndex: Int
    let explanation: String
    let tint: Color
    var demoChoice: Int? = nil
    let onCorrectFirst: () -> Void
    let onWrong: () -> Void
    @State private var correct: Bool?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChoiceQuestion(stem: stem, options: options, correctIndex: correctIndex,
                           submitLabel: "Submit answer", tint: tint,
                           demoChoice: demoChoice) { _, c in correct = c }
            if let correct {
                if correct {
                    ExplanationBox(label: "Correct", text: explanation, tint: Palette.review)
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

private struct LadderChoiceStep: View {
    let sub: MCQSub
    let index: Int
    let total: Int
    let tint: Color
    let onNext: () -> Void
    @State private var correct: Bool?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChoiceQuestion(stem: sub.stem, options: sub.options, correctIndex: sub.correctIndex,
                           submitLabel: "Check", tint: tint) { _, c in correct = c }
            if let correct {
                ExplanationBox(label: correct ? "Correct" : "Explanation", text: sub.explanation,
                               tint: correct ? Palette.review : tint)
                PrimaryButton(index == total - 1 ? "Back to the question" : "Next guiding question",
                              tint: tint) { onNext() }
            }
        }
    }
}

private struct ReattemptChoiceStep: View {
    let stem: String
    let options: [String]
    let correctIndex: Int
    let explanation: String
    let source: String
    let tint: Color
    let onDone: (Bool) -> Void
    @State private var correct: Bool?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChoiceQuestion(stem: stem, options: options, correctIndex: correctIndex,
                           submitLabel: "Submit answer", tint: tint) { _, c in correct = c }
            if let correct {
                if correct {
                    NoteBox(kind: .spaced,
                            text: "**Not mastered yet.** Getting it right seconds after the scaffold isn't readiness. This card is scheduled for spaced re-retrieval — you'll need to recall it again in a later session for it to count.")
                    ExplanationBox(label: "Correct", text: explanation, tint: Palette.review)
                } else {
                    NoteBox(kind: .struggle,
                            text: "**Here's the full explanation — earned through real retrieval.** This card is flagged as struggling and scheduled for aggressive early re-retrieval; it returns fresh next session.")
                    ExplanationBox(label: "Explanation", text: explanation)
                    ResourceLink(source: source, label: "open the source for this question")
                }
                PrimaryButton("Continue", tint: tint) { onDone(correct) }
            }
        }
    }
}

// MARK: - Format wrappers

struct MCQReviewerView: View {
    let item: MCQItem
    let tint: Color
    var aiLadder: ((CardContext) async -> [LadderRung]?)? = nil
    let onFinish: (ReviewOutcome) -> Void
    var body: some View {
        ChoiceReviewer(
            title: item.subtopic.isEmpty ? "MCAT question" : item.subtopic,
            passage: nil, question: item.question, options: item.options,
            correctIndex: item.correctIndex, explanation: item.explanation,
            source: item.source, subs: item.subquestions, tint: tint,
            cardContext: item.ladderContext, aiLadder: aiLadder, onFinish: onFinish
        )
    }
}

struct PassageReviewerView: View {
    let item: PassageItem
    let tint: Color
    var aiLadder: ((CardContext) async -> [LadderRung]?)? = nil
    let onFinish: (ReviewOutcome) -> Void
    var body: some View {
        ChoiceReviewer(
            title: item.subtopic.isEmpty ? "Passage question" : item.subtopic,
            passage: item.passage, question: item.question, options: item.options,
            correctIndex: item.correctIndex, explanation: item.explanation,
            source: item.source, subs: item.subquestions, tint: tint,
            cardContext: item.ladderContext, aiLadder: aiLadder, onFinish: onFinish
        )
    }
}
