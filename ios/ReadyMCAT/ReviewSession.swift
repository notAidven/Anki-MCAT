// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Drives one native study session on the shared engine. It scopes the scheduler
// to the tapped format's deck, pulls the next queued card, reads the note's
// fields, hands the typed item to the matching native reviewer, and grades the
// outcome back through the shared scheduler (AnswerCard) with the ReadyMCAT
// contract — first-try correct → Good, otherwise Again — flagging a
// missed-again teach-on-miss card ReadyMCAT::struggling exactly like the desktop.

import Foundation
import SwiftUI

/// The three teach-on-miss outcomes, mirroring qt/aqt/reviewer.py +
/// build_question_bank.ease_for_mcq_outcome / outcome_is_struggling.
enum ReviewOutcome {
    case correctFirst        // no ladder needed -> Good, no tag
    case correctAfterLadder  // scaffolded then correct -> Again, "corrected"
    case wrongAfterLadder    // missed again -> Again, "struggling"

    var rating: Rating { self == .correctFirst ? .good : .again }

    /// The tag the desktop's _flag_concept applies after the ladder (nil on a
    /// clean first-try, which never runs the ladder).
    var tag: String? {
        switch self {
        case .correctFirst: return nil
        case .correctAfterLadder: return "ReadyMCAT::corrected"
        case .wrongAfterLadder: return "ReadyMCAT::struggling"
        }
    }
}

@MainActor
final class ReviewSession: ObservableObject {
    @Published var item: ReviewItem?
    @Published var counts = QueueCounts()
    @Published var finished = false
    @Published var reviewed = 0
    @Published var errorText: String?
    /// Changes for every card so the reviewer view resets its internal state.
    @Published var cardToken = UUID()

    let format: Format
    private var engine: AnkiEngine?
    private var deckId: Int64 = 0
    private var current: ReviewCard?
    private var shownAt = Date()
    private var started = false

    init(format: Format) { self.format = format }

    func begin(engine: AnkiEngine, deckId: Int64) {
        guard !started else { return }
        started = true
        self.engine = engine
        self.deckId = deckId
        do {
            try engine.setCurrentDeck(deckId)
            loadNext()
        } catch {
            errorText = "\(error)"
            NSLog("[ReadyMCAT] session begin error: \(error)")
        }
    }

    private func loadNext() {
        guard let engine else { return }
        do {
            let (card, counts) = try engine.nextCard()
            self.counts = counts
            guard let card else {
                finished = true
                item = nil
                return
            }
            let fields = try engine.noteFields(noteId: card.noteId)
            current = card
            item = ContentParser.item(format: format, fields: fields)
            cardToken = UUID()
            shownAt = Date()
        } catch {
            errorText = "\(error)"
            NSLog("[ReadyMCAT] loadNext error: \(error)")
        }
    }

    /// Grade the just-completed card and advance. Mirrors the desktop: first-try
    /// correct grades Good; anything that needed the ladder grades Again, and a
    /// card missed again is tagged struggling so points-at-stake resurfaces it.
    func finish(_ outcome: ReviewOutcome) {
        guard let engine, let card = current else { return }
        do {
            let taken = UInt32(max(0, min(60_000, Int(Date().timeIntervalSince(shownAt) * 1000))))
            try engine.answer(card: card, rating: outcome.rating, millisecondsTaken: taken)
            if let tag = outcome.tag {
                try? engine.addTag(noteId: card.noteId, tag: tag)
            }
            reviewed += 1
            NSLog("[ReadyMCAT] graded card=\(card.cardId) outcome=\(outcome) rating=\(outcome.rating)")
            loadNext()
        } catch {
            errorText = "\(error)"
            NSLog("[ReadyMCAT] grade error: \(error)")
        }
    }
}

struct ReviewSessionView: View {
    let format: Format
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @StateObject private var session: ReviewSession

    init(format: Format) {
        self.format = format
        _session = StateObject(wrappedValue: ReviewSession(format: format))
    }

    var body: some View {
        NavigationStack {
            Group {
                if let error = session.errorText {
                    errorView(error)
                } else if session.finished {
                    completeView
                } else if let item = session.item {
                    reviewer(for: item)
                        .id(session.cardToken)
                } else {
                    ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle(format.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") { close() }
                }
                ToolbarItem(placement: .principal) {
                    Text(remainingLabel).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .onAppear {
            guard let engine = model.engine, let node = model.node(for: format) else {
                session.errorText = "Deck '\(format.deckName)' not found."
                return
            }
            session.begin(engine: engine, deckId: node.deckId)
        }
    }

    @ViewBuilder
    private func reviewer(for item: ReviewItem) -> some View {
        switch item {
        case .mcq(let m):
            MCQReviewerView(item: m, tint: Palette.tint(for: format)) { session.finish($0) }
        case .passage(let p):
            PassageReviewerView(item: p, tint: Palette.tint(for: format)) { session.finish($0) }
        case .fr(let f):
            FRReviewerView(item: f, tint: Palette.tint(for: format)) { session.finish($0) }
        }
    }

    private var remainingLabel: String {
        let c = session.counts
        return "New \(c.new) · Learn \(c.learning) · Review \(c.review)"
    }

    private var completeView: some View {
        VStack(spacing: 14) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 56)).foregroundStyle(Palette.review)
            Text("Session complete").font(.title2.weight(.bold))
            Text("You studied \(session.reviewed) \(format.title) card\(session.reviewed == 1 ? "" : "s") on the shared Anki engine.")
                .font(.subheadline).foregroundStyle(.secondary)
                .multilineTextAlignment(.center).padding(.horizontal)
            Button("Done") { close() }
                .font(.headline).padding(.horizontal, 28).padding(.vertical, 12)
                .background(Palette.accent, in: Capsule()).foregroundStyle(.white)
                .padding(.top, 8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func errorView(_ text: String) -> some View {
        VStack(spacing: 12) {
            Label("Session error", systemImage: "exclamationmark.triangle.fill")
                .font(.headline).foregroundStyle(Palette.danger)
            Text(text).font(.footnote.monospaced()).foregroundStyle(.secondary)
                .padding().multilineTextAlignment(.center)
            Button("Done") { close() }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func close() {
        model.refresh()   // reflect the new grades in Home tiles + Dashboard
        dismiss()
    }
}
