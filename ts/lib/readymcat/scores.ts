// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Shared honest-score helpers for the ReadyMCAT desktop surfaces — the honest
// dashboard (ts/routes/readymcat-dashboard) and the home hub
// (ts/routes/readymcat-home). Keeping the give-up thresholds, the percentage
// formatter and the "what to study next" ranking here — and nowhere else —
// means the two screens can never quietly disagree about when a score has
// enough evidence, or about how the study-next list is ordered.
//
// The thresholds and score scale below MIRROR the Rust source of truth in
// rslib/src/points_at_stake/mod.rs (GIVE_UP_MIN_REVIEWS, GIVE_UP_MIN_COVERAGE,
// PERFORMANCE_GIVE_UP_MIN_ATTEMPTS, MCAT_SCORE_MIN / MCAT_SCORE_MAX). The
// backend still OWNS the actual give-up decision — each report carries its own
// meets_data_threshold — so these copies only drive the progress meters and the
// "needs N more" copy. They must be kept in lockstep with the Rust values; the
// unit test alongside this file pins them so drift is caught.

/** Memory give-up rule: graded reviews needed before a Memory score is shown. */
export const MIN_REVIEWS = 200;
/** Memory give-up rule: fraction of the AAMC outline that must be covered. */
export const MIN_COVERAGE = 0.5;
/** Performance give-up rule: first attempts needed before a score is shown. */
export const MIN_ATTEMPTS = 30;

/** The real MCAT total-score scale that Readiness projects onto. */
export const SCORE_MIN = 472;
export const SCORE_MAX = 528;

/** Format a 0..1 fraction as a whole-number percentage, e.g. 0.5 -> "50%". */
export const pct = (x: number): string => `${Math.round(x * 100)}%`;

/** The per-topic fields the study-next ranking needs (a subset of TopicMastery). */
export interface RankableTopic {
    topicWeight: number;
    studentWeakness: number;
    totalCards: number;
}

/**
 * "What to study next": the topics with the most points at stake (exam weight ×
 * weakness), highest first, capped at `limit`. Topics with no cards are dropped.
 * Each returned topic keeps its original fields plus the computed `points`, so
 * callers can still render its category/name alongside the ranking.
 */
export function studyNextTopics<T extends RankableTopic>(
    topics: readonly T[],
    limit: number,
): Array<T & { points: number }> {
    return topics
        .filter((t) => t.totalCards > 0)
        .map((t) => ({ ...t, points: t.topicWeight * t.studentWeakness }))
        .sort((a, b) => b.points - a.points)
        .slice(0, limit);
}
