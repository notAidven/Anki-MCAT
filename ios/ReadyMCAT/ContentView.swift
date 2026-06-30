// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import SwiftUI

@MainActor
final class ReviewViewModel: ObservableObject {
    @Published var bodyHTML: String = ""
    @Published var showingAnswer = false
    @Published var counts = QueueCounts()
    @Published var finished = false
    @Published var status: String = "Loading…"
    @Published var errorText: String?
    @Published var reviewedCount = 0

    private var engine: AnkiEngine?
    private var current: ReviewCard?
    private var css = ""
    private var questionHTML = ""
    private var answerHTML = ""
    private var shownAt = Date()

    func bootstrap() {
        do {
            let paths = try CollectionStore.prepare()
            let engine = try AnkiEngine()
            try engine.openCollection(
                path: paths.collection,
                mediaFolder: paths.mediaFolder,
                mediaDB: paths.mediaDB
            )
            self.engine = engine
            NSLog("[ReadyMCAT] engine opened; buildhash=\(engine.buildHash)")
            if ProcessInfo.processInfo.environment["READYMCAT_AUTORUN"] != nil {
                try autoReview()
            } else {
                try loadNext()
            }
        } catch {
            errorText = "\(error)"
            status = "Error"
            NSLog("[ReadyMCAT] bootstrap error: \(error)")
        }
    }

    private func loadNext() throws {
        guard let engine else { return }
        let (card, counts) = try engine.nextCard()
        self.counts = counts
        guard let card else {
            finished = true
            status = "Review complete"
            bodyHTML = ""
            NSLog("[ReadyMCAT] queue empty — review complete after \(reviewedCount) cards")
            return
        }
        let rendered = try engine.render(cardId: card.cardId)
        current = card
        css = rendered.css
        questionHTML = rendered.question
        answerHTML = rendered.answer
        showingAnswer = false
        bodyHTML = HTMLPage.wrap(questionHTML, css: css)
        shownAt = Date()
        status = "New \(counts.new)  •  Learn \(counts.learning)  •  Review \(counts.review)"
        NSLog("[ReadyMCAT] showing card id=\(card.cardId)")
    }

    /// Headless verification path: studies the whole queue automatically
    /// (render + grade "Good") and writes a result file. Triggered by the
    /// READYMCAT_AUTORUN environment variable so a human never has to tap.
    private func autoReview() throws {
        guard let engine else { return }
        var graded = 0
        while true {
            let (card, counts) = try engine.nextCard()
            self.counts = counts
            guard let card else { break }
            let rendered = try engine.render(cardId: card.cardId)
            questionHTML = rendered.question
            answerHTML = rendered.answer
            css = rendered.css
            bodyHTML = HTMLPage.wrap(rendered.answer, css: rendered.css)
            try engine.answer(card: card, rating: .good, millisecondsTaken: 1500)
            graded += 1
            NSLog("[ReadyMCAT][autorun] graded card id=\(card.cardId) (\(graded))")
        }
        reviewedCount = graded
        finished = true
        status = "Auto-review complete"
        CollectionStore.writeResult(reviewed: graded, remaining: counts.total)
        NSLog("[ReadyMCAT][autorun] AUTO REVIEW DONE: \(graded) cards graded, \(counts.total) remaining")
    }

    func showAnswer() {
        showingAnswer = true
        bodyHTML = HTMLPage.wrap(answerHTML, css: css)
    }

    func grade(_ rating: Rating) {
        guard let engine, let card = current else { return }
        do {
            let taken = UInt32(max(0, min(60_000, Int(Date().timeIntervalSince(shownAt) * 1000))))
            try engine.answer(card: card, rating: rating, millisecondsTaken: taken)
            reviewedCount += 1
            NSLog("[ReadyMCAT] graded card id=\(card.cardId) rating=\(rating) (\(reviewedCount) total)")
            try loadNext()
        } catch {
            errorText = "\(error)"
            NSLog("[ReadyMCAT] grade error: \(error)")
        }
    }
}

struct ContentView: View {
    @StateObject private var model = ReviewViewModel()

    var body: some View {
        VStack(spacing: 0) {
            header

            if let errorText = model.errorText {
                ScrollView {
                    Text(errorText)
                        .font(.system(.footnote, design: .monospaced))
                        .foregroundColor(.red)
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else if model.finished {
                completeView
            } else {
                CardWebView(html: model.bodyHTML)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                controls
            }
        }
        .onAppear { model.bootstrap() }
    }

    private var header: some View {
        VStack(spacing: 4) {
            Text("ReadyMCAT")
                .font(.headline)
            Text(model.status)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(Color(.secondarySystemBackground))
    }

    private var completeView: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 56))
                .foregroundColor(.green)
            Text("Review complete")
                .font(.title2).bold()
            Text("You studied \(model.reviewedCount) card\(model.reviewedCount == 1 ? "" : "s") on the shared Anki engine.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Spacer()
        }
    }

    private var controls: some View {
        Group {
            if model.showingAnswer {
                HStack(spacing: 8) {
                    gradeButton("Again", .again, .red)
                    gradeButton("Hard", .hard, .orange)
                    gradeButton("Good", .good, .green)
                    gradeButton("Easy", .easy, .blue)
                }
                .padding()
            } else {
                Button(action: { model.showAnswer() }) {
                    Text("Show Answer")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accentColor)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
                .padding()
            }
        }
    }

    private func gradeButton(_ title: String, _ rating: Rating, _ color: Color) -> some View {
        Button(action: { model.grade(rating) }) {
            Text(title)
                .font(.subheadline).bold()
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(color)
                .foregroundColor(.white)
                .cornerRadius(10)
        }
    }
}

/// Wraps card HTML in a minimal styled document, injecting the note type's CSS
/// inside a `.card` container (the class Anki's templates style against).
enum HTMLPage {
    static func wrap(_ body: String, css: String) -> String {
        """
        <!doctype html>
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
        <style>
        \(css)
        :root { color-scheme: light dark; }
        body { font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 22px;
               margin: 0; padding: 24px; line-height: 1.5; }
        .card { text-align: center; }
        hr#answer { margin: 20px 0; }
        </style>
        </head>
        <body><div class="card">\(body)</div></body>
        </html>
        """
    }
}
