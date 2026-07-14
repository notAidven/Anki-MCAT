// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Shared native building blocks for the three ReadyMCAT reviewers (MCQ, Free
// Response, Passage/CARS). These are the SwiftUI equivalents of the DOM the
// TypeScript reviewers build (ts/reviewer/{mcq,fr,passage}.ts): a selectable
// choice list with correct/incorrect feedback, a type-in field graded by the
// shared free-response grader, explanation / teach-on-miss note callouts, and a
// resource link — all native, no web view.

import SwiftUI
import UIKit

// MARK: - Header

struct ReviewerHeader: View {
    let title: String
    let step: String
    var body: some View {
        HStack(spacing: 8) {
            Text("ReadyMCAT")
                .font(.caption2.weight(.heavy))
                .padding(.horizontal, 8).padding(.vertical, 4)
                .background(Palette.accent, in: Capsule()).foregroundStyle(.white)
            Text(title).font(.subheadline.weight(.semibold)).lineLimit(1)
            Spacer()
            Text(step).font(.caption2).foregroundStyle(.secondary)
        }
    }
}

// MARK: - Multiple-choice question

/// A selectable A–D list with submit. After submit it locks, marks the correct
/// choice green and a wrong pick red, and reports (chosenIndex, correct) once.
struct ChoiceQuestion: View {
    let stem: String
    let options: [String]
    let correctIndex: Int
    let submitLabel: String
    let tint: Color
    /// Screenshot/verification only: auto-pick this option shortly after appear.
    var demoChoice: Int? = nil
    let onSubmit: (_ chosen: Int, _ correct: Bool) -> Void

    @State private var selected: Int?
    @State private var submitted = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(stem.plainText).font(.headline).fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 8) {
                ForEach(options.indices, id: \.self) { i in optionRow(i) }
            }
            if !submitted {
                PrimaryButton(submitLabel, tint: tint, enabled: selected != nil) {
                    guard let sel = selected else { return }
                    submitted = true
                    onSubmit(sel, sel == correctIndex)
                }
            }
        }
        .cardSurface()
        .onAppear {
            guard let demo = demoChoice, options.indices.contains(demo) else { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                guard !submitted else { return }
                selected = demo
                submitted = true
                onSubmit(demo, demo == correctIndex)
            }
        }
    }

    private func optionRow(_ i: Int) -> some View {
        let isCorrect = submitted && i == correctIndex
        let isWrongPick = submitted && i == selected && i != correctIndex
        let isSelected = !submitted && selected == i
        return Button {
            if !submitted { selected = i }
        } label: {
            HStack(alignment: .top, spacing: 10) {
                Text(String(UnicodeScalar(65 + i)!))
                    .font(.subheadline.weight(.heavy)).foregroundStyle(.secondary)
                    .frame(width: 18, alignment: .leading)
                Text(options[i].plainText)
                    .font(.subheadline).foregroundStyle(.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                if isCorrect { Image(systemName: "checkmark.circle.fill").foregroundStyle(Palette.review) }
                if isWrongPick { Image(systemName: "xmark.circle.fill").foregroundStyle(Palette.danger) }
            }
            .padding(12)
            .background(rowBackground(isCorrect: isCorrect, isWrong: isWrongPick, isSelected: isSelected),
                        in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(
                rowBorder(isCorrect: isCorrect, isWrong: isWrongPick, isSelected: isSelected), lineWidth: 1.5))
        }
        .buttonStyle(.plain)
        .disabled(submitted)
    }

    private func rowBackground(isCorrect: Bool, isWrong: Bool, isSelected: Bool) -> Color {
        if isCorrect { return Palette.review.opacity(0.14) }
        if isWrong { return Palette.danger.opacity(0.14) }
        if isSelected { return tint.opacity(0.12) }
        return Color(.tertiarySystemGroupedBackground)
    }

    private func rowBorder(isCorrect: Bool, isWrong: Bool, isSelected: Bool) -> Color {
        if isCorrect { return Palette.review }
        if isWrong { return Palette.danger }
        if isSelected { return tint }
        return .clear
    }
}

// MARK: - Free-response question

/// A type-in field graded by the shared FreeResponseGrader. After submit it
/// locks, shows a Correct / Not quite verdict, and reports (value, correct) once.
struct TypeInQuestion: View {
    let stem: String
    let accepted: [String]
    let keyTerms: [String]
    let submitLabel: String
    let tint: Color
    /// Screenshot/verification only: auto-type this and submit shortly after appear.
    var demoText: String? = nil
    let onSubmit: (_ value: String, _ correct: Bool) -> Void

    @State private var text = ""
    @State private var submitted = false
    @State private var correct = false
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(stem.plainText).font(.headline).fixedSize(horizontal: false, vertical: true)
            TextField("Type your answer, then submit", text: $text)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .focused($focused)
                .padding(12)
                .background(Color(.tertiarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(
                    submitted ? (correct ? Palette.review : Palette.danger) : tint.opacity(0.5),
                    lineWidth: 1.5))
                .disabled(submitted)
                .onSubmit(submit)
            if submitted {
                Text(correct ? "Correct" : "Not quite")
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(correct ? Palette.review : Palette.danger)
            } else {
                PrimaryButton(submitLabel, tint: tint, enabled: !text.trimmingCharacters(in: .whitespaces).isEmpty, action: submit)
            }
        }
        .cardSurface()
        .onAppear {
            guard let demo = demoText else { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                guard !submitted else { return }
                text = demo
                submit()
            }
        }
    }

    private func submit() {
        guard !submitted else { return }
        correct = FreeResponseGrader.grade(text, accepted: accepted, keyTerms: keyTerms)
        submitted = true
        onSubmit(text, correct)
    }
}

// MARK: - Callouts

struct ExplanationBox: View {
    let label: String
    let text: String
    var tint: Color = Palette.accent
    var body: some View {
        if !text.plainText.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text(label.uppercased()).font(.caption2.weight(.bold)).tracking(0.5)
                    .foregroundStyle(.secondary)
                Text(text.plainText).font(.subheadline).fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 10))
            .overlay(HStack { Rectangle().fill(tint).frame(width: 4); Spacer() }
                .clipShape(RoundedRectangle(cornerRadius: 10)))
        }
    }
}

struct NoteBox: View {
    enum Kind { case spaced, struggle }
    let kind: Kind
    let text: String
    private var color: Color { kind == .spaced ? Palette.review : Palette.danger }
    var body: some View {
        Text(.init(text))     // markdown for the **bold** lead-in
            .font(.subheadline).fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(color.opacity(0.10), in: RoundedRectangle(cornerRadius: 10))
            .overlay(HStack { Rectangle().fill(color).frame(width: 4); Spacer() }
                .clipShape(RoundedRectangle(cornerRadius: 10)))
    }
}

/// "Needs content review" link, extracting the first URL from a Source string
/// exactly like the TS reviewers' firstUrl().
struct ResourceLink: View {
    let source: String
    let label: String
    private var url: URL? {
        guard let match = source.range(of: "https?://[^\\s\"'<>)]+", options: .regularExpression)
        else { return nil }
        return URL(string: String(source[match]))
    }
    var body: some View {
        if let url {
            Link(destination: url) {
                Text("→ Needs content review: \(label)")
                    .font(.footnote.weight(.semibold)).foregroundStyle(Palette.accent)
            }
        }
    }
}

struct PassageDisclosure: View {
    let passage: String
    @State private var expanded: Bool

    init(passage: String, expanded: Bool) {
        self.passage = passage
        _expanded = State(initialValue: expanded)
    }

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            Text(passage.plainText).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 6)
        } label: {
            Text("Passage").font(.caption.weight(.bold)).tracking(0.5).foregroundStyle(.secondary)
        }
        .tint(Palette.accent)
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 10))
        .overlay(HStack { Rectangle().fill(Palette.accent).frame(width: 3); Spacer() }
            .clipShape(RoundedRectangle(cornerRadius: 10)))
    }
}

// MARK: - Buttons + surface

struct PrimaryButton: View {
    let title: String
    let tint: Color
    var enabled: Bool = true
    let action: () -> Void
    init(_ title: String, tint: Color, enabled: Bool = true, action: @escaping () -> Void) {
        self.title = title; self.tint = tint; self.enabled = enabled; self.action = action
    }
    var body: some View {
        Button(action: action) {
            Text(title).font(.subheadline.weight(.bold))
                .frame(maxWidth: .infinity).padding(.vertical, 12)
                .background(enabled ? tint : Color.gray.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
                .foregroundStyle(.white)
        }
        .disabled(!enabled)
    }
}

private struct CardSurface: ViewModifier {
    func body(content: Content) -> some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 14))
    }
}

extension View {
    func cardSurface() -> some View { modifier(CardSurface()) }
}
