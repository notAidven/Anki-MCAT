// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Swift value types + a hand-rolled protobuf decoder for the engine's
// `anki.points_at_stake.PointsAtStakeResponse` (proto/anki/points_at_stake.proto).
//
// This is the single message that backs the whole ReadyMCAT dashboard: the three
// honest scores (Memory / Performance / Readiness), the AAMC outline coverage,
// and the per-topic mastery/weakness aggregation used for "what to study next".
// It is computed by the shared Rust `PointsAtStakeService` and reaches Swift as
// raw protobuf bytes over the same `rsios_command` dispatch the desktop uses.

import Foundation

struct MemoryReport {
    var mean = 0.0
    var rangeLow = 0.0
    var rangeHigh = 0.0
    var gradedReviews = 0
    var gradedCards = 0
}

struct CoverageReport {
    var categoriesTotal = 0
    var categoriesCovered = 0
    var fraction = 0.0
    var weightedFraction = 0.0
}

struct TopicPerformance: Identifiable {
    let category: String
    let name: String
    let topicWeight: Double
    let attempts: Int
    let hits: Int
    let accuracy: Double
    var id: String { category }
}

struct PerformanceReport {
    var mean = 0.0
    var rangeLow = 0.0
    var rangeHigh = 0.0
    var attempts = 0
    var hits = 0
    var meetsDataThreshold = false
    var topics: [TopicPerformance] = []
}

struct ReadinessReport {
    var point = 0.0
    var rangeLow = 0.0
    var rangeHigh = 0.0
    var ability = 0.0
    var meetsDataThreshold = false
    var heuristic = true
}

struct TopicMastery: Identifiable {
    let category: String
    let name: String
    let topicWeight: Double
    let gradedCards: Int
    let totalCards: Int
    let meanRetrievability: Double
    let studentWeakness: Double
    var id: String { category }
    /// The ranking used by "what to study next": weight × your weakness.
    var points: Double { topicWeight * studentWeakness }
}

struct PointsAtStake {
    var topics: [TopicMastery] = []
    var memory = MemoryReport()
    var coverage = CoverageReport()
    var performance = PerformanceReport()
    var readiness = ReadinessReport()
    /// Memory give-up flag (>= 200 graded reviews AND >= 50% coverage).
    var meetsDataThreshold = false
    var rankedCardCount = 0

    /// The topics with the most points at stake (weight × weakness), highest
    /// first — mirrors the Svelte hub/dashboard "study next" ordering.
    var studyNext: [TopicMastery] {
        topics
            .filter { $0.totalCards > 0 }
            .sorted { $0.points > $1.points }
    }

    // PointsAtStakeResponse field numbers (points_at_stake.proto).
    //   1 ranked_cards (repeated) · 2 topics (repeated) · 3 memory ·
    //   4 coverage · 5 meets_data_threshold · 6 performance · 7 readiness
    static func decode(_ bytes: [UInt8]) -> PointsAtStake {
        var out = PointsAtStake()
        out.rankedCardCount = Proto.allBytes(bytes, 1).count
        out.topics = Proto.allBytes(bytes, 2).map(decodeTopic)
        if let mem = Proto.firstBytes(bytes, 3) { out.memory = decodeMemory(mem) }
        if let cov = Proto.firstBytes(bytes, 4) { out.coverage = decodeCoverage(cov) }
        out.meetsDataThreshold = Proto.bool(bytes, 5)
        if let perf = Proto.firstBytes(bytes, 6) { out.performance = decodePerformance(perf) }
        if let rdy = Proto.firstBytes(bytes, 7) { out.readiness = decodeReadiness(rdy) }
        return out
    }

    // TopicMastery: 1 category · 2 name · 3 topic_weight · 4 graded_cards ·
    //   5 total_cards · 6 mean_retrievability · 7 student_weakness
    private static func decodeTopic(_ b: [UInt8]) -> TopicMastery {
        TopicMastery(
            category: Proto.string(b, 1),
            name: Proto.string(b, 2),
            topicWeight: Proto.double(b, 3),
            gradedCards: Proto.uint(b, 4),
            totalCards: Proto.uint(b, 5),
            meanRetrievability: Proto.double(b, 6),
            studentWeakness: Proto.double(b, 7)
        )
    }

    // MemoryReport: 1 mean · 2 range_low · 3 range_high · 4 graded_reviews ·
    //   5 graded_cards
    private static func decodeMemory(_ b: [UInt8]) -> MemoryReport {
        MemoryReport(
            mean: Proto.double(b, 1),
            rangeLow: Proto.double(b, 2),
            rangeHigh: Proto.double(b, 3),
            gradedReviews: Proto.uint(b, 4),
            gradedCards: Proto.uint(b, 5)
        )
    }

    // CoverageReport: 1 categories_total · 2 categories_covered · 3 fraction ·
    //   4 weighted_fraction
    private static func decodeCoverage(_ b: [UInt8]) -> CoverageReport {
        CoverageReport(
            categoriesTotal: Proto.uint(b, 1),
            categoriesCovered: Proto.uint(b, 2),
            fraction: Proto.double(b, 3),
            weightedFraction: Proto.double(b, 4)
        )
    }

    // PerformanceReport: 1 mean · 2 range_low · 3 range_high · 4 attempts ·
    //   5 hits · 6 meets_data_threshold · 7 topics (repeated)
    private static func decodePerformance(_ b: [UInt8]) -> PerformanceReport {
        PerformanceReport(
            mean: Proto.double(b, 1),
            rangeLow: Proto.double(b, 2),
            rangeHigh: Proto.double(b, 3),
            attempts: Proto.uint(b, 4),
            hits: Proto.uint(b, 5),
            meetsDataThreshold: Proto.bool(b, 6),
            topics: Proto.allBytes(b, 7).map(decodeTopicPerformance)
        )
    }

    // TopicPerformance: 1 category · 2 name · 3 topic_weight · 4 attempts ·
    //   5 hits · 6 accuracy
    private static func decodeTopicPerformance(_ b: [UInt8]) -> TopicPerformance {
        TopicPerformance(
            category: Proto.string(b, 1),
            name: Proto.string(b, 2),
            topicWeight: Proto.double(b, 3),
            attempts: Proto.uint(b, 4),
            hits: Proto.uint(b, 5),
            accuracy: Proto.double(b, 6)
        )
    }

    // ReadinessReport: 1 point · 2 range_low · 3 range_high · 4 ability ·
    //   5 meets_data_threshold · 6 heuristic
    private static func decodeReadiness(_ b: [UInt8]) -> ReadinessReport {
        ReadinessReport(
            point: Proto.double(b, 1),
            rangeLow: Proto.double(b, 2),
            rangeHigh: Proto.double(b, 3),
            ability: Proto.double(b, 4),
            meetsDataThreshold: Proto.bool(b, 5),
            heuristic: Proto.bool(b, 6)
        )
    }
}
