// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Swift wrapper around the `rsios` C-ABI bridge to Anki's Rust engine (rslib).
// Every ReadyMCAT screen gets its data from here: the native Home reads the deck
// due tree, the native Dashboard reads the PointsAtStakeService, and the native
// reviewers open a deck, fetch queued cards, read the note's fields, and grade
// through the shared scheduler — all over the exact same command-dispatch path
// (`Backend::run_service_method`) the desktop app uses through pylib/rsbridge.
// No scheduling / scoring / grading logic is re-implemented in the engine layer.

import Foundation
import RsiosFFI

/// Grades, matching anki.scheduler.CardAnswer.Rating.
enum Rating: Int {
    case again = 0
    case hard = 1
    case good = 2
    case easy = 3
}

/// The next card to study, plus the opaque scheduling-state blobs we must echo
/// back when grading (we never need to interpret them).
struct ReviewCard {
    let cardId: Int64
    let noteId: Int64
    let currentState: [UInt8]
    let stateAgain: [UInt8]
    let stateHard: [UInt8]
    let stateGood: [UInt8]
    let stateEasy: [UInt8]

    func newState(for rating: Rating) -> [UInt8] {
        switch rating {
        case .again: return stateAgain
        case .hard: return stateHard
        case .good: return stateGood
        case .easy: return stateEasy
        }
    }
}

struct QueueCounts {
    var new = 0
    var learning = 0
    var review = 0
    var total: Int { new + learning + review }
}

enum EngineError: Error, CustomStringConvertible {
    case openFailed(String)
    case backendError(service: UInt32, method: UInt32)
    case notOpen

    var description: String {
        switch self {
        case .openFailed(let m): return "Failed to open backend: \(m)"
        case .backendError(let s, let m): return "Backend error on service \(s) method \(m)"
        case .notOpen: return "Backend not open"
        }
    }
}

final class AnkiEngine {
    // Service / method indices, taken verbatim from the generated
    // out/pylib/anki/_backend_generated.py (the authoritative index source) and
    // verified by the host-side smoke test in tools/sample_deck.
    private enum Svc {
        static let decks: UInt32 = 7
        static let scheduler: UInt32 = 13
        static let notes: UInt32 = 25
        static let cardRendering: UInt32 = 27
        static let collection: UInt32 = 3
        static let tags: UInt32 = 49
        static let pointsAtStake: UInt32 = 45
        static let diagnostic: UInt32 = 29
    }
    private enum Method {
        static let openCollection: UInt32 = 0     // BackendCollectionService
        static let deckTree: UInt32 = 4           // DecksService.DeckTree
        static let setCurrentDeck: UInt32 = 22    // DecksService.SetCurrentDeck
        static let getQueuedCards: UInt32 = 3     // BackendSchedulerService
        static let answerCard: UInt32 = 4         // BackendSchedulerService
        static let getNote: UInt32 = 6            // NotesService.GetNote
        static let renderExistingCard: UInt32 = 6 // CardRenderingService
        static let addNoteTags: UInt32 = 7        // TagsService.AddNoteTags
        static let pointsAtStakeQueue: UInt32 = 0 // PointsAtStakeService
        static let getDiagnosticQuiz: UInt32 = 0  // DiagnosticService
        static let scoreAndSeedDiagnostic: UInt32 = 1 // DiagnosticService
    }

    private var backend: OpaquePointer?

    var buildHash: String {
        guard let c = rsios_buildhash() else { return "" }
        return String(cString: c)
    }

    init() throws {
        var errPtr: UnsafeMutablePointer<UInt8>? = nil
        var errLen = 0
        backend = rsios_open_backend(nil, 0, &errPtr, &errLen)
        if backend == nil {
            var message = "unknown error"
            if let p = errPtr, errLen > 0 {
                message = String(decoding: Data(bytes: p, count: errLen), as: UTF8.self)
                rsios_free_buffer(p, errLen)
            }
            throw EngineError.openFailed(message)
        }
    }

    deinit {
        if let backend { rsios_close_backend(backend) }
    }

    // MARK: - Raw command dispatch

    /// Runs one backend command. Returns the response bytes, or throws on a
    /// backend error (status == RSIOS_BACKEND_ERROR) / null pointer.
    @discardableResult
    private func command(_ service: UInt32, _ method: UInt32, _ input: Data) throws -> [UInt8] {
        guard backend != nil else { throw EngineError.notOpen }
        var outPtr: UnsafeMutablePointer<UInt8>? = nil
        var outLen = 0

        let status: Int32 = input.withUnsafeBytes { raw in
            let base = raw.bindMemory(to: UInt8.self).baseAddress
            return rsios_command(backend, service, method, base, input.count, &outPtr, &outLen)
        }

        var out: [UInt8] = []
        if let p = outPtr {
            if outLen > 0 { out = Array(Data(bytes: p, count: outLen)) }
            rsios_free_buffer(p, outLen)
        }

        if status == RSIOS_OK { return out }
        // status == RSIOS_BACKEND_ERROR (out holds an encoded BackendError) or
        // a null-pointer error. Surface the BackendError.message if present.
        let message = Proto.firstString(out, 1) ?? ""
        throw EngineError.backendError(service: service, method: method)
            .annotated(message)
    }

    // MARK: - Collection

    func openCollection(path: String, mediaFolder: String, mediaDB: String) throws {
        var w = ProtoWriter()
        w.stringField(1, path)          // collection_path
        w.stringField(2, mediaFolder)   // media_folder_path
        w.stringField(3, mediaDB)       // media_db_path
        try command(Svc.collection, Method.openCollection, w.data)
    }

    // MARK: - Home hub data

    /// The full deck tree with live due/total counters populated (DeckTree with
    /// a non-zero `now`, which is what asks the backend to fill the counts).
    func deckTree() throws -> DeckNode {
        var w = ProtoWriter()
        w.int64Field(1, Int64(Date().timeIntervalSince1970)) // now (unix secs)
        let bytes = try command(Svc.decks, Method.deckTree, w.data)
        return DeckNode.decode(bytes)
    }

    // MARK: - Dashboard data

    /// The whole honest-scores payload (Memory / Performance / Readiness +
    /// coverage + per-topic mastery) from the shared PointsAtStakeService.
    /// `taxonomyPath` may be "" to let the backend find taxonomy.json next to
    /// the collection.
    func pointsAtStake(taxonomyPath: String, deckId: Int64 = 0, limit: UInt32 = 0) throws -> PointsAtStake {
        var w = ProtoWriter()
        if !taxonomyPath.isEmpty { w.stringField(1, taxonomyPath) } // taxonomy_path
        if deckId != 0 { w.int64Field(2, deckId) }                   // deck_id
        if limit != 0 { w.uint64Field(3, UInt64(limit)) }            // limit
        let bytes = try command(Svc.pointsAtStake, Method.pointsAtStakeQueue, w.data)
        return PointsAtStake.decode(bytes)
    }

    // MARK: - Diagnostic

    /// Serve the first-launch diagnostic quiz (one MCQ per AAMC category in
    /// "short" mode). `quizPath` may be "" to let the backend find
    /// diagnostic_quiz.json next to the collection.
    func diagnosticQuiz(quizPath: String, mode: String = "short") throws -> DiagnosticQuiz {
        var w = ProtoWriter()
        if !quizPath.isEmpty { w.stringField(1, quizPath) } // quiz_path
        w.stringField(2, mode)                              // mode
        let bytes = try command(Svc.diagnostic, Method.getDiagnosticQuiz, w.data)
        return DiagnosticQuiz.decode(bytes)
    }

    /// Score a completed diagnostic into the per-topic prior (ordering only).
    @discardableResult
    func scoreDiagnostic(answers: [DiagnosticAnswer], mode: String = "short") throws -> DiagnosticPriorSummary {
        var w = ProtoWriter()
        for a in answers { w.bytesField(1, a.encoded()) } // responses (repeated)
        w.stringField(2, mode)                            // mode
        let bytes = try command(Svc.diagnostic, Method.scoreAndSeedDiagnostic, w.data)
        return DiagnosticPriorSummary.decode(bytes)
    }

    // MARK: - Review loop

    /// Scope the scheduler queue to a deck and its children.
    func setCurrentDeck(_ deckId: Int64) throws {
        var w = ProtoWriter()
        w.int64Field(1, deckId) // DeckId.did
        try command(Svc.decks, Method.setCurrentDeck, w.data)
    }

    /// Fetch the next queued card (and the queue counts). Returns nil when the
    /// queue is empty (session finished).
    func nextCard() throws -> (ReviewCard?, QueueCounts) {
        var w = ProtoWriter()
        w.uint64Field(1, 50)            // fetch_limit
        let bytes = try command(Svc.scheduler, Method.getQueuedCards, w.data)

        var counts = QueueCounts()
        counts.new = Int(Proto.firstVarint(bytes, 2) ?? 0)       // new_count
        counts.learning = Int(Proto.firstVarint(bytes, 3) ?? 0)  // learning_count
        counts.review = Int(Proto.firstVarint(bytes, 4) ?? 0)    // review_count

        // QueuedCards.cards (field 1, repeated) -> take the first.
        guard let queuedCard = Proto.firstBytes(bytes, 1) else {
            return (nil, counts)
        }
        // QueuedCard.card (field 1) -> Card.id (field 1), Card.note_id (field 2)
        let cardMsg = Proto.firstBytes(queuedCard, 1) ?? []
        let cardId = Int64(bitPattern: Proto.firstVarint(cardMsg, 1) ?? 0)
        let noteId = Int64(bitPattern: Proto.firstVarint(cardMsg, 2) ?? 0)
        // QueuedCard.states (field 3) -> SchedulingStates {current=1, again=2, hard=3, good=4, easy=5}
        let states = Proto.firstBytes(queuedCard, 3) ?? []
        let card = ReviewCard(
            cardId: cardId,
            noteId: noteId,
            currentState: Proto.firstBytes(states, 1) ?? [],
            stateAgain: Proto.firstBytes(states, 2) ?? [],
            stateHard: Proto.firstBytes(states, 3) ?? [],
            stateGood: Proto.firstBytes(states, 4) ?? [],
            stateEasy: Proto.firstBytes(states, 5) ?? []
        )
        return (card, counts)
    }

    /// A note's ordered field values (NotesService.GetNote -> Note.fields).
    func noteFields(noteId: Int64) throws -> [String] {
        var w = ProtoWriter()
        w.int64Field(1, noteId) // NoteId.nid
        let bytes = try command(Svc.notes, Method.getNote, w.data)
        return Proto.allStrings(bytes, 7) // Note.fields (repeated string)
    }

    /// Render a card to (questionHTML, answerHTML, css).
    func render(cardId: Int64) throws -> (question: String, answer: String, css: String) {
        var w = ProtoWriter()
        w.int64Field(1, cardId)         // card_id
        let bytes = try command(Svc.cardRendering, Method.renderExistingCard, w.data)
        let question = assemble(Proto.allBytes(bytes, 1))
        let answer = assemble(Proto.allBytes(bytes, 2))
        let css = Proto.firstString(bytes, 3) ?? ""
        return (question, answer, css)
    }

    /// Grade a card. current_state / new_state are the opaque blobs from nextCard.
    func answer(card: ReviewCard, rating: Rating, millisecondsTaken: UInt32) throws {
        var w = ProtoWriter()
        w.int64Field(1, card.cardId)                                    // card_id
        w.bytesField(2, card.currentState)                             // current_state
        w.bytesField(3, card.newState(for: rating))                   // new_state
        w.uint64Field(4, UInt64(rating.rawValue))                     // rating
        w.int64Field(5, Int64(Date().timeIntervalSince1970 * 1000))  // answered_at_millis
        w.uint64Field(6, UInt64(millisecondsTaken))                  // milliseconds_taken
        try command(Svc.scheduler, Method.answerCard, w.data)
    }

    /// Tag a note (used to flag a teach-on-miss card that was missed again as
    /// `ReadyMCAT::struggling`, mirroring the desktop reviewer so points-at-stake
    /// boosts the corrected concept back to the top of the queue).
    func addTag(noteId: Int64, tag: String) throws {
        var w = ProtoWriter()
        w.int64Field(1, noteId) // note_ids (repeated int64; single unpacked element)
        w.stringField(2, tag)   // tags
        try command(Svc.tags, Method.addNoteTags, w.data)
    }

    // MARK: - Helpers

    /// Flatten RenderedTemplateNode list into HTML. Each node is either a text
    /// node (field 1, string) or a replacement (field 2 -> current_text field 2).
    private func assemble(_ nodes: [[UInt8]]) -> String {
        var html = ""
        for node in nodes {
            if let text = Proto.firstString(node, 1) {
                html += text
            } else if let replacement = Proto.firstBytes(node, 2) {
                html += Proto.firstString(replacement, 2) ?? ""
            }
        }
        return html
    }
}

private extension EngineError {
    /// Attach a backend message for nicer logging without changing the case.
    func annotated(_ message: String) -> EngineError {
        if case let .backendError(s, m) = self, !message.isEmpty {
            NSLog("[ReadyMCAT] backend error (svc \(s) method \(m)): \(message)")
        }
        return self
    }
}
