// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Free-response auto-grader — a faithful Swift port of the canonical grader in
// readymcat/tools/build_question_bank.py (grade_free_response) and its browser
// mirror ts/reviewer/fr_grade.ts. All three MUST stay in lockstep.
//
// An answer is correct when ANY of these hold:
//  * it parses to a number matching an accepted numeric answer (within the
//    tolerance parsed from key_terms when provided, else effectively exactly);
//  * its normalised (or squashed) form equals an accepted answer;
//  * every non-directive key term appears in it (so prose / derivations that
//    contain the essential terms still count).

import Foundation

enum FreeResponseGrader {
    private static let numberRE = try! NSRegularExpression(
        pattern: "[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?")
    private static let toleranceRE = try! NSRegularExpression(
        pattern: "tolerance\\s*[:=]?\\s*[±+\\-]?\\s*([-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?)\\s*(%?)",
        options: [.caseInsensitive])
    private static let punctRE = try! NSRegularExpression(pattern: "[^\\p{L}\\p{N}_\\s]",
                                                          options: [])
    private static let wsRE = try! NSRegularExpression(pattern: "\\s+")
    private static let nonAlnumRE = try! NSRegularExpression(pattern: "[^a-z0-9]")

    private static func replace(_ re: NSRegularExpression, in s: String,
                                with repl: String) -> String {
        let range = NSRange(s.startIndex..., in: s)
        return re.stringByReplacingMatches(in: s, range: range, withTemplate: repl)
    }

    /// Lowercase, strip punctuation, and collapse whitespace for comparison.
    static func normalize(_ text: String) -> String {
        let lowered = text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let depunct = replace(punctRE, in: lowered, with: " ")
        return replace(wsRE, in: depunct, with: " ").trimmingCharacters(in: .whitespaces)
    }

    /// Normalise then drop all non-alphanumerics (loose match for equations).
    static func squash(_ text: String) -> String {
        replace(nonAlnumRE, in: normalize(text), with: "")
    }

    /// Best-effort leading numeric value in a string ("30 m/s" -> 30).
    static func number(_ text: String) -> Double? {
        let cleaned = text.replacingOccurrences(of: ",", with: "")
        let range = NSRange(cleaned.startIndex..., in: cleaned)
        guard let m = numberRE.firstMatch(in: cleaned, range: range),
              let r = Range(m.range, in: cleaned) else { return nil }
        return Double(cleaned[r])
    }

    private struct Tolerance { let magnitude: Double; let isPercent: Bool }

    private static func tolerance(from keyTerms: [String]) -> Tolerance? {
        for term in keyTerms where term.lowercased().contains("tolerance") {
            let range = NSRange(term.startIndex..., in: term)
            if let m = toleranceRE.firstMatch(in: term, range: range),
               let magR = Range(m.range(at: 1), in: term),
               let mag = Double(term[magR]) {
                let isPercent: Bool
                if let pctR = Range(m.range(at: 2), in: term) {
                    isPercent = term[pctR] == "%"
                } else {
                    isPercent = false
                }
                return Tolerance(magnitude: abs(mag), isPercent: isPercent)
            }
        }
        return nil
    }

    private static func nonDirectiveKeyTerms(_ keyTerms: [String]) -> [String] {
        keyTerms.filter {
            let low = $0.trimmingCharacters(in: .whitespaces).lowercased()
            return !low.hasPrefix("tolerance") && !low.hasPrefix("unit")
        }
    }

    /// Auto-grade a typed answer against accepted answers / key terms.
    static func grade(_ userAnswer: String, accepted: [String], keyTerms: [String] = []) -> Bool {
        let userNorm = normalize(userAnswer)
        if userNorm.isEmpty { return false }
        let userSquash = squash(userAnswer)
        let userNum = number(userAnswer)
        let tol = tolerance(from: keyTerms)

        // 1. numeric match (respecting a provided tolerance)
        if let userNum {
            for a in accepted {
                guard let acceptedNum = number(a) else { continue }
                if let tol {
                    let bound = tol.isPercent
                        ? (tol.magnitude / 100.0) * abs(acceptedNum)
                        : tol.magnitude
                    if abs(userNum - acceptedNum) <= bound + 1e-9 { return true }
                } else if abs(userNum - acceptedNum) <= 1e-9 {
                    return true
                }
            }
        }

        // 2. normalised / squashed string match
        for a in accepted {
            if a.trimmingCharacters(in: .whitespaces).isEmpty { continue }
            let acceptedSquash = squash(a)
            if normalize(a) == userNorm || (!acceptedSquash.isEmpty && acceptedSquash == userSquash) {
                return true
            }
        }

        // 3. every non-directive key term present in the answer
        let terms = nonDirectiveKeyTerms(keyTerms).map(squash).filter { $0.count >= 3 }
        if !terms.isEmpty && terms.allSatisfy({ userSquash.contains($0) }) {
            return true
        }
        return false
    }
}
