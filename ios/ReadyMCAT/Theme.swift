// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// The ReadyMCAT visual language, ported natively from the Svelte design
// (ts/routes/readymcat-home + readymcat-dashboard) so the SwiftUI app reads as
// the same product: the same four format hues, the same accent/confidence
// colours, and the same brand gradient — no web view.

import SwiftUI

enum Palette {
    static let accent = Color(hex: 0x2D6CDF)      // --accent-card
    static let danger = Color(hex: 0xC62828)      // --accent-danger
    static let review = Color(hex: 0x2E7D32)      // --state-review (green)
    static let warn = Color(hex: 0xD9822B)        // --flag2 (amber)
    static let streak = Color(hex: 0xEA580C)

    static let brand = LinearGradient(
        colors: [Color(hex: 0x3B82F6), Color(hex: 0x8B5CF6)],
        startPoint: .topLeading, endPoint: .bottomTrailing)

    static func gradient(for format: Format) -> LinearGradient {
        let stops: [Color]
        switch format {
        case .mcq: stops = [Color(hex: 0x3B82F6), Color(hex: 0x2563EB)]
        case .fr: stops = [Color(hex: 0x8B5CF6), Color(hex: 0x7C3AED)]
        case .passage: stops = [Color(hex: 0x10B981), Color(hex: 0x059669)]
        case .cars: stops = [Color(hex: 0xF97316), Color(hex: 0xEA580C)]
        }
        return LinearGradient(colors: stops, startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    static func tint(for format: Format) -> Color {
        switch format {
        case .mcq: return Color(hex: 0x2563EB)
        case .fr: return Color(hex: 0x7C3AED)
        case .passage: return Color(hex: 0x059669)
        case .cars: return Color(hex: 0xEA580C)
        }
    }

    static func icon(for format: Format) -> String {
        switch format {
        case .mcq: return "circle.grid.2x2.fill"
        case .fr: return "square.and.pencil"
        case .passage: return "book.fill"
        case .cars: return "text.book.closed.fill"
        }
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: 1
        )
    }
}

/// Confidence level derived from an interval width (mirrors the dashboard's
/// fracLevel / scoreLevel thresholds).
enum Confidence {
    case high, moderate, low

    static func fromFraction(marginPoints: Double) -> Confidence {
        if marginPoints <= 2.5 { return .high }
        if marginPoints <= 6 { return .moderate }
        return .low
    }

    static func fromScore(marginPoints: Double) -> Confidence {
        if marginPoints <= 3 { return .high }
        if marginPoints <= 8 { return .moderate }
        return .low
    }

    var label: String {
        switch self {
        case .high: return "High confidence"
        case .moderate: return "Moderate confidence"
        case .low: return "Low confidence"
        }
    }

    var color: Color {
        switch self {
        case .high: return Palette.review
        case .moderate: return Palette.warn
        case .low: return Palette.danger
        }
    }
}

extension String {
    /// Decode the handful of HTML entities Anki may store in a field and drop any
    /// stray tags, so the (plain-text) ReadyMCAT content renders cleanly in a
    /// native SwiftUI Text. The bank is authored as plain text, so this is a
    /// light safety net rather than a real HTML renderer.
    var plainText: String {
        var s = self
        let entities = ["&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"",
                        "&#39;": "'", "&nbsp;": " "]
        for (k, v) in entities { s = s.replacingOccurrences(of: k, with: v) }
        // strip simple tags like <sup>/<b> while keeping their text content
        s = s.replacingOccurrences(of: "<[^>]+>", with: "",
                                   options: .regularExpression)
        return s.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// Percent helper matching the design's `pct` (rounded whole percent).
func pct(_ x: Double) -> String { "\(Int((x * 100).rounded()))%" }

/// Screenshot/verification-only auto-answer, driven by the READYMCAT_DEMO env var
/// ("correct" or "wrong"). Has no effect in normal use.
enum Demo {
    static var mode: String? { ProcessInfo.processInfo.environment["READYMCAT_DEMO"] }
    static var wantsCorrect: Bool { mode == "correct" }
    static var active: Bool { mode == "correct" || mode == "wrong" }
}
