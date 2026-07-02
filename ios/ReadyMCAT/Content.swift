// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The ReadyMCAT content model on the Swift side. A card's note FIELDS come back
// from the shared engine (NotesService.GetNote) as an ordered [String]; this file
// parses those fields — in the exact field order defined by
// readymcat/tools/build_question_bank.py — into the typed payloads the native
// reviewers render, including the pre-authored teach-on-miss sub-question ladder
// stored as JSON in each note's `Subquestions` field.

import Foundation

/// The four pre-loaded content formats, each in its own deck.
enum Format: String, CaseIterable, Identifiable {
    case mcq, fr, passage, cars
    var id: String { rawValue }

    /// Fully-qualified deck name in the bundled collection (see
    /// ios/scripts/build-collection.sh, which lays the bank out this way).
    var deckName: String {
        switch self {
        case .mcq: return "ReadyMCAT::Multiple Choice"
        case .fr: return "ReadyMCAT::Free Response"
        case .passage: return "ReadyMCAT::Passages"
        case .cars: return "ReadyMCAT::CARS"
        }
    }

    var title: String {
        switch self {
        case .mcq: return "Multiple Choice"
        case .fr: return "Free Response"
        case .passage: return "Passage Sets"
        case .cars: return "CARS"
        }
    }

    var blurb: String {
        switch self {
        case .mcq: return "Discrete exam-style questions"
        case .fr: return "Type-in recall, the core loop"
        case .passage: return "Full AAMC-style passages"
        case .cars: return "Critical analysis & reasoning"
        }
    }

    var noun: String {
        switch self {
        case .mcq, .passage, .cars: return "questions"
        case .fr: return "cards"
        }
    }
}

/// A guiding multiple-choice sub-question (MCQ + passage ladders).
struct MCQSub: Identifiable {
    let id = UUID()
    let stem: String
    let options: [String]
    let correctIndex: Int
    let explanation: String
}

/// A guiding type-in sub-question (free-response ladder).
struct FRSub: Identifiable {
    let id = UUID()
    let stem: String
    let acceptedAnswers: [String]
    let keyTerms: [String]
    let explanation: String
}

/// One studyable item, discriminated by format. Rendered by the native reviewer.
enum ReviewItem {
    case mcq(MCQItem)
    case fr(FRItem)
    case passage(PassageItem)
}

struct MCQItem {
    let question: String
    let options: [String]
    let correctIndex: Int
    let explanation: String
    let subtopic: String
    let source: String
    let subquestions: [MCQSub]
}

struct FRItem {
    let prompt: String
    let acceptedAnswers: [String]
    let keyTerms: [String]
    let modelAnswer: String
    let explanation: String
    let subtopic: String
    let source: String
    let subquestions: [FRSub]
}

struct PassageItem {
    let passage: String
    let passageId: String
    let question: String
    let options: [String]
    let correctIndex: Int
    let explanation: String
    let subtopic: String
    let source: String
    let subquestions: [MCQSub]
}

enum ContentParser {
    private static func field(_ fields: [String], _ i: Int) -> String {
        i < fields.count ? fields[i] : ""
    }

    private static func clampIndex(_ s: String) -> Int {
        max(0, min(3, Int(s.trimmingCharacters(in: .whitespaces)) ?? 0))
    }

    private static func jsonArray(_ raw: String) -> [[String: Any]] {
        guard let data = raw.data(using: .utf8),
              let arr = try? JSONSerialization.jsonObject(with: data) as? [Any]
        else { return [] }
        return arr.compactMap { $0 as? [String: Any] }
    }

    private static func stringList(_ any: Any?) -> [String] {
        (any as? [Any])?.map { "\($0)" } ?? []
    }

    private static func mcqSubs(_ raw: String) -> [MCQSub] {
        jsonArray(raw).map { obj in
            MCQSub(
                stem: obj["stem"] as? String ?? "",
                options: stringList(obj["options"]),
                correctIndex: max(0, min(3, obj["correct_index"] as? Int ?? 0)),
                explanation: obj["explanation"] as? String ?? ""
            )
        }
    }

    private static func frSubs(_ raw: String) -> [FRSub] {
        jsonArray(raw).map { obj in
            FRSub(
                stem: obj["stem"] as? String ?? "",
                acceptedAnswers: stringList(obj["accepted_answers"]),
                keyTerms: stringList(obj["key_terms"]),
                explanation: obj["explanation"] as? String ?? ""
            )
        }
    }

    /// Build a review item for the KNOWN format of the deck the session is
    /// scoped to. (Every ReadyMCAT deck is single-format, so the format is
    /// unambiguous; `cars` reuses the passage note type.)
    static func item(format: Format, fields: [String]) -> ReviewItem {
        switch format {
        case .mcq:
            // MCQ_FIELDS: Question, OptionA..D, CorrectIndex, Explanation,
            // Subtopic, Source, Subquestions
            return .mcq(MCQItem(
                question: field(fields, 0),
                options: [field(fields, 1), field(fields, 2), field(fields, 3), field(fields, 4)],
                correctIndex: clampIndex(field(fields, 5)),
                explanation: field(fields, 6),
                subtopic: field(fields, 7),
                source: field(fields, 8),
                subquestions: mcqSubs(field(fields, 9))
            ))
        case .fr:
            // FR_FIELDS: Prompt, AcceptedAnswers, KeyTerms, ModelAnswer,
            // Explanation, Subtopic, Source, Subquestions
            return .fr(FRItem(
                prompt: field(fields, 0),
                acceptedAnswers: stringList(try? JSONSerialization.jsonObject(
                    with: Data(field(fields, 1).utf8))),
                keyTerms: stringList(try? JSONSerialization.jsonObject(
                    with: Data(field(fields, 2).utf8))),
                modelAnswer: field(fields, 3),
                explanation: field(fields, 4),
                subtopic: field(fields, 5),
                source: field(fields, 6),
                subquestions: frSubs(field(fields, 7))
            ))
        case .passage, .cars:
            // PASSAGE_FIELDS: Passage, PassageId, Question, OptionA..D,
            // CorrectIndex, Explanation, Subtopic, Source, Subquestions
            return .passage(PassageItem(
                passage: field(fields, 0),
                passageId: field(fields, 1),
                question: field(fields, 2),
                options: [field(fields, 3), field(fields, 4), field(fields, 5), field(fields, 6)],
                correctIndex: clampIndex(field(fields, 7)),
                explanation: field(fields, 8),
                subtopic: field(fields, 9),
                source: field(fields, 10),
                subquestions: mcqSubs(field(fields, 11))
            ))
        }
    }
}
