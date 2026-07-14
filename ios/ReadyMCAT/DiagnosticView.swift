// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The native first-launch diagnostic. It serves one MCQ per AAMC category from
// the shared DiagnosticService, administers them natively (select -> just-in-time
// rationale), and on completion scores the responses into a per-topic PRIOR that
// seeds points-at-stake ordering. HONESTY: the diagnostic is a prior, never a
// score — it is never surfaced to the student as a number.

import SwiftUI

@MainActor
final class DiagnosticModel: ObservableObject {
    @Published var quiz: DiagnosticQuiz?
    @Published var index = 0
    @Published var chosen: String?
    @Published var finished = false
    @Published var errorText: String?
    @Published var seededCategories = 0

    private var answers: [DiagnosticAnswer] = []
    private var engine: AnkiEngine?
    private var quizPath = ""

    func load(engine: AnkiEngine, quizPath: String) {
        guard quiz == nil, errorText == nil else { return }
        self.engine = engine
        self.quizPath = quizPath
        do {
            let q = try engine.diagnosticQuiz(quizPath: quizPath, mode: "short")
            if !q.present || q.items.isEmpty {
                errorText = "No diagnostic bank could be located."
            } else {
                quiz = q
            }
        } catch {
            errorText = "\(error)"
        }
    }

    var current: DiagnosticItem? {
        guard let quiz, index < quiz.items.count else { return nil }
        return quiz.items[index]
    }

    var progress: String {
        guard let quiz else { return "" }
        return "Question \(min(index + 1, quiz.items.count)) of \(quiz.items.count)"
    }

    func choose(_ key: String) {
        guard chosen == nil, let item = current else { return }
        chosen = key
        answers.append(DiagnosticAnswer(
            itemId: item.id, category: item.category, chosen: key,
            answered: true, correct: key == item.answer, difficulty: item.difficulty))
    }

    func skip() {
        guard let item = current else { return }
        if chosen == nil {
            answers.append(DiagnosticAnswer(
                itemId: item.id, category: item.category, chosen: "",
                answered: false, correct: false, difficulty: item.difficulty))
        }
        advance()
    }

    func advance() {
        guard let quiz else { return }
        chosen = nil
        if index + 1 < quiz.items.count {
            index += 1
        } else {
            score()
        }
    }

    private func score() {
        guard let engine else { return }
        do {
            let prior = try engine.scoreDiagnostic(answers: answers, mode: "short")
            seededCategories = prior.categoryCount
            finished = true
        } catch {
            errorText = "\(error)"
        }
    }
}

struct DiagnosticView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @StateObject private var dx = DiagnosticModel()

    var body: some View {
        NavigationStack {
            Group {
                if let error = dx.errorText {
                    message(icon: "exclamationmark.triangle.fill", color: Palette.warn,
                            title: "Diagnostic unavailable", body: error)
                } else if dx.finished {
                    message(icon: "checkmark.seal.fill", color: Palette.review,
                            title: "Diagnostic complete",
                            body: "Seeded what to study first across \(dx.seededCategories) categories. This orders your queue — it is never shown as a score.")
                } else if let item = dx.current {
                    quizBody(item)
                } else {
                    ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Diagnostic")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) { Button("Close") { close() } }
                if dx.current != nil && !dx.finished {
                    ToolbarItem(placement: .principal) {
                        Text(dx.progress).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .onAppear {
            if let engine = model.engine { dx.load(engine: engine, quizPath: model.diagnosticPath) }
        }
    }

    private func quizBody(_ item: DiagnosticItem) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 8) {
                    Text(item.category).font(.caption2.weight(.heavy))
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(Palette.accent, in: Capsule()).foregroundStyle(.white)
                    Text(item.categoryName).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                }
                Text(item.stem.plainText).font(.headline).fixedSize(horizontal: false, vertical: true)

                VStack(spacing: 8) {
                    ForEach(item.options) { opt in optionRow(item, opt) }
                }

                if dx.chosen != nil {
                    if !item.rationale.plainText.isEmpty {
                        ExplanationBox(label: dx.chosen == item.answer ? "Correct" : "Rationale",
                                       text: item.rationale,
                                       tint: dx.chosen == item.answer ? Palette.review : Palette.accent)
                    }
                    PrimaryButton("Next", tint: Palette.accent) { dx.advance() }
                } else {
                    Button("Skip this question") { dx.skip() }
                        .font(.footnote).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(16)
        }
    }

    private func optionRow(_ item: DiagnosticItem, _ opt: DiagnosticOption) -> some View {
        let answered = dx.chosen != nil
        let isCorrect = answered && opt.key == item.answer
        let isWrongPick = answered && opt.key == dx.chosen && opt.key != item.answer
        return Button { dx.choose(opt.key) } label: {
            HStack(alignment: .top, spacing: 10) {
                Text(opt.key.uppercased()).font(.subheadline.weight(.heavy))
                    .foregroundStyle(.secondary).frame(width: 20, alignment: .leading)
                Text(opt.text.plainText).font(.subheadline)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                if isCorrect { Image(systemName: "checkmark.circle.fill").foregroundStyle(Palette.review) }
                if isWrongPick { Image(systemName: "xmark.circle.fill").foregroundStyle(Palette.danger) }
            }
            .padding(12)
            .background(bg(isCorrect: isCorrect, isWrong: isWrongPick), in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(
                isCorrect ? Palette.review : (isWrongPick ? Palette.danger : .clear), lineWidth: 1.5))
        }
        .buttonStyle(.plain)
        .disabled(answered)
    }

    private func bg(isCorrect: Bool, isWrong: Bool) -> Color {
        if isCorrect { return Palette.review.opacity(0.14) }
        if isWrong { return Palette.danger.opacity(0.14) }
        return Color(.secondarySystemGroupedBackground)
    }

    private func message(icon: String, color: Color, title: String, body: String) -> some View {
        VStack(spacing: 14) {
            Image(systemName: icon).font(.system(size: 52)).foregroundStyle(color)
            Text(title).font(.title2.weight(.bold))
            Text(body).font(.subheadline).foregroundStyle(.secondary)
                .multilineTextAlignment(.center).padding(.horizontal)
            Button("Done") { close() }
                .font(.headline).padding(.horizontal, 28).padding(.vertical, 12)
                .background(Palette.accent, in: Capsule()).foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func close() {
        model.refresh()
        dismiss()
    }
}
