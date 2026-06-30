// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Swift wrapper around the `rsios` C-ABI bridge to Anki's Rust engine (rslib).
// It drives a real review session over the SHARED engine: open the collection,
// fetch the next queued card, render its HTML, and grade it — the exact same
// command-dispatch path the desktop app uses through pylib/rsbridge.

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
        static let collection: UInt32 = 3
        static let scheduler: UInt32 = 13
        static let cardRendering: UInt32 = 27
    }
    private enum Method {
        static let openCollection: UInt32 = 0   // BackendCollectionService
        static let getQueuedCards: UInt32 = 3   // BackendSchedulerService
        static let answerCard: UInt32 = 4       // BackendSchedulerService
        static let renderExistingCard: UInt32 = 6 // CardRenderingService
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

    // MARK: - Review loop

    func openCollection(path: String, mediaFolder: String, mediaDB: String) throws {
        var w = ProtoWriter()
        w.stringField(1, path)          // collection_path
        w.stringField(2, mediaFolder)   // media_folder_path
        w.stringField(3, mediaDB)       // media_db_path
        try command(Svc.collection, Method.openCollection, w.data)
    }

    /// Fetch the next queued card (and the queue counts). Returns nil when the
    /// queue is empty (review finished).
    func nextCard() throws -> (ReviewCard?, QueueCounts) {
        var w = ProtoWriter()
        w.uint64Field(1, 10)            // fetch_limit
        let bytes = try command(Svc.scheduler, Method.getQueuedCards, w.data)

        var counts = QueueCounts()
        counts.new = Int(Proto.firstVarint(bytes, 2) ?? 0)       // new_count
        counts.learning = Int(Proto.firstVarint(bytes, 3) ?? 0)  // learning_count
        counts.review = Int(Proto.firstVarint(bytes, 4) ?? 0)    // review_count

        // QueuedCards.cards (field 1, repeated) -> take the first.
        guard let queuedCard = Proto.firstBytes(bytes, 1) else {
            return (nil, counts)
        }
        // QueuedCard.card (field 1) -> Card.id (field 1)
        let cardMsg = Proto.firstBytes(queuedCard, 1) ?? []
        let cardId = Int64(bitPattern: Proto.firstVarint(cardMsg, 1) ?? 0)
        // QueuedCard.states (field 3) -> SchedulingStates {current=1, again=2, hard=3, good=4, easy=5}
        let states = Proto.firstBytes(queuedCard, 3) ?? []
        let card = ReviewCard(
            cardId: cardId,
            currentState: Proto.firstBytes(states, 1) ?? [],
            stateAgain: Proto.firstBytes(states, 2) ?? [],
            stateHard: Proto.firstBytes(states, 3) ?? [],
            stateGood: Proto.firstBytes(states, 4) ?? [],
            stateEasy: Proto.firstBytes(states, 5) ?? []
        )
        return (card, counts)
    }

    /// Render a card to (questionHTML, answerHTML, css).
    func render(cardId: Int64) throws -> (question: String, answer: String, css: String) {
        var w = ProtoWriter()
        w.int64Field(1, cardId)         // card_id
        // browser=false, partial_render=false -> omitted (proto3 defaults)
        let bytes = try command(Svc.cardRendering, Method.renderExistingCard, w.data)

        // RenderCardResponse { question_nodes=1, answer_nodes=2, css=3 }
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
