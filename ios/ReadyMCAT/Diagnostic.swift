// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Swift value types + codec for the engine's DiagnosticService messages
// (proto/anki/diagnostic.proto). The first-launch diagnostic serves one MCQ per
// AAMC category, and — on completion — the responses are scored by the shared
// engine into a per-topic PRIOR that seeds points-at-stake ORDERING only (never a
// dashboard score). Both the quiz and the scoring go over the shared FFI dispatch.

import Foundation

struct DiagnosticOption: Identifiable {
    let key: String
    let text: String
    var id: String { key }
}

struct DiagnosticItem: Identifiable {
    let id: String
    let category: String
    let categoryName: String
    let difficulty: String
    let stem: String
    let options: [DiagnosticOption]
    let answer: String       // correct option key
    let rationale: String
    let sourceURL: String
}

struct DiagnosticQuiz {
    let quizId: String
    let title: String
    let description: String
    let mode: String
    let items: [DiagnosticItem]
    let present: Bool

    // DiagnosticQuiz: 1 quiz_id · 2 title · 3 description · 4 mode ·
    //   5 items (repeated) · 6 present
    static func decode(_ b: [UInt8]) -> DiagnosticQuiz {
        DiagnosticQuiz(
            quizId: Proto.string(b, 1),
            title: Proto.string(b, 2),
            description: Proto.string(b, 3),
            mode: Proto.string(b, 4),
            items: Proto.allBytes(b, 5).map(decodeItem),
            present: Proto.bool(b, 6)
        )
    }

    // DiagnosticItem: 1 id · 2 category · 3 category_name · 7 difficulty ·
    //   8 stem · 9 options (repeated) · 10 answer · 11 rationale · 12 source_url
    private static func decodeItem(_ b: [UInt8]) -> DiagnosticItem {
        DiagnosticItem(
            id: Proto.string(b, 1),
            category: Proto.string(b, 2),
            categoryName: Proto.string(b, 3),
            difficulty: Proto.string(b, 7),
            stem: Proto.string(b, 8),
            options: Proto.allBytes(b, 9).map {
                DiagnosticOption(key: Proto.string($0, 1), text: Proto.string($0, 2))
            },
            answer: Proto.string(b, 10),
            rationale: Proto.string(b, 11),
            sourceURL: Proto.string(b, 12)
        )
    }
}

/// One recorded answer, encoded into a DiagnosticResponse sub-message.
struct DiagnosticAnswer {
    let itemId: String
    let category: String
    let chosen: String
    let answered: Bool
    let correct: Bool
    let difficulty: String

    // DiagnosticResponse: 1 item_id · 2 category · 3 chosen · 4 answered ·
    //   5 correct · 6 difficulty
    func encoded() -> [UInt8] {
        var w = ProtoWriter()
        w.stringField(1, itemId)
        w.stringField(2, category)
        w.stringField(3, chosen)
        w.boolField(4, answered)
        w.boolField(5, correct)
        w.stringField(6, difficulty)
        return [UInt8](w.data)
    }
}

/// Small per-category summary decoded from the returned DiagnosticPrior, used to
/// confirm the seed took (ordering only — never shown as a score).
struct DiagnosticPriorSummary {
    let present: Bool
    let categoryCount: Int

    // DiagnosticPrior: 1 present · 5 categories (repeated)
    static func decode(_ b: [UInt8]) -> DiagnosticPriorSummary {
        DiagnosticPriorSummary(present: Proto.bool(b, 1),
                               categoryCount: Proto.allBytes(b, 5).count)
    }
}
