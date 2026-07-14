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

/// Credentials/handle for a sync session, matching anki.sync.SyncAuth.
/// `hkey` is the host key returned by SyncLogin; `endpoint` is the base URL of
/// the (self-hosted) sync server, e.g. "http://127.0.0.1:8080/".
struct SyncAuth {
    var hkey: String
    var endpoint: String

    /// Encode as an anki.sync.SyncAuth message (hkey=1, endpoint=2).
    func encoded() -> [UInt8] {
        var w = ProtoWriter()
        w.stringField(1, hkey)
        if !endpoint.isEmpty { w.stringField(2, endpoint) }
        return [UInt8](w.data)
    }
}

/// anki.sync.SyncCollectionResponse.ChangesRequired (and the matching
/// SyncStatusResponse.Required values 0–2). After a `sync_collection` call this
/// tells us whether the normal sync completed or a full up/down is needed.
enum SyncRequired: Int {
    case noChanges = 0
    case normalSync = 1
    case fullSync = 2       // both sides changed — ambiguous, user must choose
    case fullDownload = 3   // local has no cards; only download is possible
    case fullUpload = 4     // remote has no cards; only upload is possible
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
        static let sync: UInt32 = 1               // BackendSyncService
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
        static let closeCollection: UInt32 = 1    // BackendCollectionService
        static let newDeck: UInt32 = 0            // DecksService.NewDeck
        static let addDeck: UInt32 = 1            // DecksService.AddDeck
        static let deckTree: UInt32 = 4           // DecksService.DeckTree
        static let getOrCreateFilteredDeck: UInt32 = 19 // DecksService.GetOrCreateFilteredDeck
        static let addOrUpdateFilteredDeck: UInt32 = 20 // DecksService.AddOrUpdateFilteredDeck
        static let setCurrentDeck: UInt32 = 22    // DecksService.SetCurrentDeck
        static let emptyFilteredDeck: UInt32 = 15 // BackendSchedulerService.EmptyFilteredDeck
        static let rebuildFilteredDeck: UInt32 = 16 // BackendSchedulerService.RebuildFilteredDeck
        static let getQueuedCards: UInt32 = 3     // BackendSchedulerService
        static let answerCard: UInt32 = 4         // BackendSchedulerService
        static let addNote: UInt32 = 1            // NotesService.AddNote
        static let getNote: UInt32 = 6            // NotesService.GetNote
        static let renderExistingCard: UInt32 = 6 // CardRenderingService
        static let addNoteTags: UInt32 = 7        // TagsService.AddNoteTags
        static let pointsAtStakeQueue: UInt32 = 0 // PointsAtStakeService
        static let getDiagnosticQuiz: UInt32 = 0  // DiagnosticService
        static let scoreAndSeedDiagnostic: UInt32 = 1 // DiagnosticService
        // BackendSyncService (service 1), indices from _backend_generated.py.
        static let syncMedia: UInt32 = 0
        static let mediaSyncStatus: UInt32 = 2
        static let syncLogin: UInt32 = 3
        static let syncStatus: UInt32 = 4
        static let syncCollection: UInt32 = 5
        static let fullUploadOrDownload: UInt32 = 6
        static let abortSync: UInt32 = 7
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

    /// Close the open collection, checkpointing SQLite so the .anki2 file on disk
    /// is fully consistent (used by the headless harness before the host reads
    /// the revlog). `downgrade` should stay false to preserve the modern schema.
    func closeCollection(downgrade: Bool = false) throws {
        var w = ProtoWriter()
        w.boolField(1, downgrade)       // CloseCollectionRequest.downgrade_to_schema11
        try command(Svc.collection, Method.closeCollection, w.data)
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

    // MARK: - Filtered deck (one-tap study isolation)

    /// (Re)build a single reused "launcher" filtered deck holding exactly the
    /// cards matching `search`, and return its deck id. This is how a format
    /// whose deck has nested children (MCQ's `ReadyMCAT` parents Free Response /
    /// Passages / CARS; Passages parents CARS) is studied WITHOUT the scheduler
    /// pulling those children in — Anki's per-deck review always includes a
    /// deck's descendants, so the isolating search + a filtered deck is the only
    /// honest way to serve exactly one format. Mirrors the desktop hub's
    /// `_rebuild_launcher_deck` (qt/aqt/readymcat_home.py): GetOrCreateFilteredDeck
    /// → set name + one DUE-ordered search term + reschedule → AddOrUpdateFilteredDeck
    /// → RebuildFilteredDeck. `seedId` reuses an existing launcher deck (0 mints a
    /// fresh one) so we never litter the deck list.
    func rebuildLauncherDeck(seedId: Int64, name: String, search: String) throws -> Int64 {
        // 1. GetOrCreateFilteredDeck(DeckId{did=seedId}) -> FilteredDeckForUpdate{id=1}
        var g = ProtoWriter()
        g.int64Field(1, seedId)
        let fetched = try command(Svc.decks, Method.getOrCreateFilteredDeck, g.data)
        let fetchedId = Int64(bitPattern: Proto.firstVarint(fetched, 1) ?? 0)

        // 2. AddOrUpdateFilteredDeck(FilteredDeckForUpdate{id=1, name=2, config=3})
        //    config = Deck.Filtered{ reschedule=1, search_terms=2 (repeated) }
        //    search_terms[0] = SearchTerm{ search=1, limit=2, order=3 (DUE=6) }
        var term = ProtoWriter()
        term.stringField(1, search)
        term.uint64Field(2, 9999)   // limit
        term.uint64Field(3, 6)      // Order.DUE
        var config = ProtoWriter()
        config.boolField(1, true)                       // reschedule (real reviews)
        config.bytesField(2, [UInt8](term.data))        // search_terms (one)
        var upd = ProtoWriter()
        upd.int64Field(1, fetchedId)                    // id (0 => create)
        upd.stringField(2, name)                        // name
        upd.bytesField(3, [UInt8](config.data))         // config
        let res = try command(Svc.decks, Method.addOrUpdateFilteredDeck, upd.data)
        let newId = Int64(bitPattern: Proto.firstVarint(res, 2) ?? 0) // OpChangesWithId.id
        let deckId = newId != 0 ? newId : fetchedId

        // 3. RebuildFilteredDeck(DeckId{did}) — pull the matching cards in.
        var rb = ProtoWriter()
        rb.int64Field(1, deckId)
        try command(Svc.scheduler, Method.rebuildFilteredDeck, rb.data)
        return deckId
    }

    /// Empty a filtered deck, returning every card it holds to its home deck
    /// (preserving each card's updated scheduling from the session). Used to
    /// return the launcher deck's cards so the format tiles read honest counts
    /// again — mirrors the desktop's `_return_launcher_cards`.
    func emptyFilteredDeck(_ deckId: Int64) throws {
        var w = ProtoWriter()
        w.int64Field(1, deckId) // DeckId.did
        try command(Svc.scheduler, Method.emptyFilteredDeck, w.data)
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

    // MARK: - Demo seeding (an authorless card so the AI ladder path is reachable)

    /// Create a normal deck by name and return its id. NewDeck hands back a Deck
    /// with the engine's defaults (id 0, normal kind, default config); we echo
    /// those bytes back to AddDeck with the name appended (proto3 singular
    /// fields are last-wins), so the engine owns every invariant. AddDeck also
    /// auto-creates any missing parent (e.g. "ReadyMCAT").
    func createDeck(name: String) throws -> Int64 {
        let base = try command(Svc.decks, Method.newDeck, Data())   // Deck defaults
        var w = ProtoWriter()
        w.raw(base)
        w.stringField(2, name)   // Deck.name
        let bytes = try command(Svc.decks, Method.addDeck, w.data)  // OpChangesWithId{id=2}
        return Int64(bitPattern: Proto.firstVarint(bytes, 2) ?? 0)
    }

    /// The notetype id backing a note (Note.notetype_id, field 3). Used to reuse
    /// an existing ReadyMCAT notetype when seeding the demo card, so the demo is
    /// parsed by the same Content.swift path as the real cards.
    func noteNotetypeId(noteId: Int64) throws -> Int64 {
        var w = ProtoWriter()
        w.int64Field(1, noteId)
        let bytes = try command(Svc.notes, Method.getNote, w.data)
        return Int64(bitPattern: Proto.firstVarint(bytes, 3) ?? 0)
    }

    /// Add a note (with its generated cards) to a deck. Returns the new note id.
    /// (NotesService.AddNote; Note{notetype_id=3, tags=6*, fields=7*} inside
    /// AddNoteRequest{note=1, deck_id=2}; AddNoteResponse{note_id=2}.)
    @discardableResult
    func addNote(notetypeId: Int64, deckId: Int64, fields: [String], tags: [String] = []) throws -> Int64 {
        var note = ProtoWriter()
        note.int64Field(3, notetypeId)
        for t in tags { note.stringField(6, t) }
        for f in fields { note.stringField(7, f) }
        var w = ProtoWriter()
        w.bytesField(1, [UInt8](note.data)) // note
        w.int64Field(2, deckId)             // deck_id
        let bytes = try command(Svc.notes, Method.addNote, w.data)
        return Int64(bitPattern: Proto.firstVarint(bytes, 2) ?? 0)
    }

    // MARK: - Sync (Anki's own collection-sync protocol)

    /// Authenticate against the sync server and obtain a host key. Mirrors the
    /// desktop's `Collection.sync_login`; the returned auth is what every other
    /// sync call needs. `endpoint` is the server base URL (http is fine for a
    /// localhost/self-hosted server — reqwest talks raw sockets, so iOS ATS does
    /// not apply, and no TLS backend is required).
    func syncLogin(username: String, password: String, endpoint: String) throws -> SyncAuth {
        var w = ProtoWriter()
        w.stringField(1, username)          // SyncLoginRequest.username
        w.stringField(2, password)          // SyncLoginRequest.password
        if !endpoint.isEmpty { w.stringField(3, endpoint) } // .endpoint
        let bytes = try command(Svc.sync, Method.syncLogin, w.data)
        // Response: SyncAuth { hkey=1, endpoint=2 }. The backend echoes the
        // endpoint we sent, but fall back to it explicitly to be safe.
        let hkey = Proto.string(bytes, 1)
        let ep = Proto.firstString(bytes, 2) ?? endpoint
        return SyncAuth(hkey: hkey, endpoint: ep)
    }

    /// Run one normal (incremental) collection sync. Returns what the server
    /// says is required next. On a NORMAL_SYNC/NO_CHANGES result the incremental
    /// sync has already been applied; a FULL_* result means the caller must run
    /// `fullUploadOrDownload`. Identical dispatch to `Collection.sync_collection`.
    @discardableResult
    func syncCollection(auth: SyncAuth, syncMedia: Bool = false) throws -> SyncRequired {
        var w = ProtoWriter()
        w.bytesField(1, auth.encoded())     // SyncCollectionRequest.auth
        w.boolField(2, syncMedia)           // .sync_media
        let bytes = try command(Svc.sync, Method.syncCollection, w.data)
        let raw = Int(Proto.firstVarint(bytes, 3) ?? 0) // .required (enum)
        return SyncRequired(rawValue: raw) ?? .noChanges
    }

    /// Force a full upload (send the whole local collection, replacing the
    /// server's) or full download (replace the local collection with the
    /// server's). Mirrors `Collection.full_upload_or_download`.
    func fullUploadOrDownload(auth: SyncAuth, upload: Bool, serverUsn: Int32? = nil) throws {
        var w = ProtoWriter()
        w.bytesField(1, auth.encoded())     // FullUploadOrDownloadRequest.auth
        w.boolField(2, upload)              // .upload
        if let usn = serverUsn { w.int64Field(3, Int64(usn)) } // .server_usn (int32)
        try command(Svc.sync, Method.fullUploadOrDownload, w.data)
    }

    /// Cheap check (mostly offline) of whether a sync is needed. Input is a bare
    /// SyncAuth; returns SyncStatusResponse.required.
    func syncStatus(auth: SyncAuth) throws -> SyncRequired {
        var w = ProtoWriter()
        w.stringField(1, auth.hkey)
        if !auth.endpoint.isEmpty { w.stringField(2, auth.endpoint) }
        let bytes = try command(Svc.sync, Method.syncStatus, w.data)
        let raw = Int(Proto.firstVarint(bytes, 1) ?? 0)
        return SyncRequired(rawValue: raw) ?? .noChanges
    }

    /// Kick off a media sync in the background (fire-and-forget; the backend runs
    /// it on its own thread). Input is a bare SyncAuth.
    func syncMedia(auth: SyncAuth) throws {
        var w = ProtoWriter()
        w.stringField(1, auth.hkey)
        if !auth.endpoint.isEmpty { w.stringField(2, auth.endpoint) }
        try command(Svc.sync, Method.syncMedia, w.data)
    }

    // MARK: - Headless review helper (verification)

    /// Grade up to `target` due cards Good across every deck that has cards,
    /// returning how many were graded. Used only by the headless sync-round-trip
    /// harness (READYMCAT_SYNC_*), it reuses the exact scheduler path the native
    /// reviewers use (SetCurrentDeck → GetQueuedCards → AnswerCard).
    @discardableResult
    func autoReview(target: Int) throws -> Int {
        guard target > 0 else { return 0 }
        var graded = 0
        let tree = try deckTree()
        var decks: [Int64] = []
        collectDeckIds(tree, into: &decks)
        for did in decks {
            if graded >= target { break }
            try setCurrentDeck(did)
            while graded < target {
                let (card, _) = try nextCard()
                guard let card else { break }
                try answer(card: card, rating: .good, millisecondsTaken: 2000)
                graded += 1
            }
        }
        return graded
    }

    private func collectDeckIds(_ node: DeckNode, into out: inout [Int64]) {
        if node.deckId != 0, node.totalInDeck > 0 { out.append(node.deckId) }
        for child in node.children { collectDeckIds(child, into: &out) }
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
