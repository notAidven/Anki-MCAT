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

// --- "Study next: <format>" recommender -------------------------------------
//
// Maps the three honest scores + per-topic points-at-stake onto ONE of the four
// ReadyMCAT formats to study next, with a one-line, number-grounded "why". Pure
// and dependency-free so the home hub AND the dashboard can share it (and so it
// is unit-testable without constructing protobuf messages). It reads only
// fields the backend already returns — it invents NO new metric — and abstains
// honestly (the "baseline" state) until the give-up rules clear.
//
// The thresholds are MVP / uncalibrated and deliberately reuse the app's own
// bands: RECALL_WEAK_MAX / RECALL_STRONG_MIN are the Topic-Mastery ring bands
// (< 60% weak, >= 80% strong). APP_GAP_MIN (0.15) sits just past the ~0.14 mean
// recall->application "transfer gap" measured by `just perf-heldout`, so a gap
// beyond it is application-specific rather than the normal transfer drop.

/** Memory (recall) below this is "not built yet" — the ring's weak band. */
export const RECALL_WEAK_MAX = 0.6;
/** Memory (recall) at/above this is "strong" — the ring's strong band. */
export const RECALL_STRONG_MIN = 0.8;
/** memory.mean − performance.mean beyond this is an application-specific gap. */
export const APP_GAP_MIN = 0.15;
/** performance.mean at/above this counts as "application solid". */
export const PERF_STRONG_MIN = 0.7;
/** A top topic worth at least this multiple of the median studied topic's
 * points-at-stake "dominates", and can override the global format message. */
export const TOPIC_DOMINANCE_FACTOR = 1.5;
/** Per-topic first attempts needed before its accuracy is trusted for routing. */
export const TOPIC_ACCURACY_MIN_ATTEMPTS = 10;

/** The four ReadyMCAT format launch keys (mirror the home's DeckLaunchKey). */
export type StudyFormatKey = "mcq" | "fr" | "passage" | "cars";

/** Display titles per format (mirror the home tiles + iOS Content.swift). */
export const STUDY_FORMAT_TITLES: Record<StudyFormatKey, string> = {
    mcq: "Multiple Choice",
    fr: "Free Response",
    passage: "Passage Sets",
    cars: "CARS",
};

/** Per-topic mastery the recommender reads (a superset of RankableTopic). */
export interface RecommendableTopic extends RankableTopic {
    category: string;
    name: string;
    gradedCards: number;
    meanRetrievability: number;
}

/** Per-topic first-attempt accuracy the recommender reads. */
export interface RecommendableTopicPerformance {
    category: string;
    attempts: number;
    accuracy: number;
}

/**
 * The subset of PointsAtStakeResponse the recommender needs. The generated
 * `PointsAtStakeResponse` satisfies this structurally, so UI callers pass it
 * straight through; unit tests pass plain objects.
 */
export interface RecommendPoints {
    meetsDataThreshold?: boolean;
    memory?: { mean: number } | null;
    performance?:
        | {
            mean: number;
            attempts: number;
            meetsDataThreshold: boolean;
            topics?: readonly RecommendableTopicPerformance[];
        }
        | null;
    readiness?: { point: number; meetsDataThreshold: boolean } | null;
    topics?: readonly RecommendableTopic[];
}

/** Optional context the home hub can supply (the dashboard omits it). */
export interface RecommendContext {
    /** Whether the first-launch diagnostic has been taken (drives the R1 CTA). */
    diagnosticTaken?: boolean;
}

/** A "start with <topic>" pointer into the Topic Mastery grid. */
export interface StudyRecommendationTopic {
    category: string;
    name: string;
}

export interface StudyRecommendation {
    /** "recommend" = a confident format pick; "baseline" = an honest abstain. */
    state: "recommend" | "baseline";
    /** Which decision-ladder rule fired (for explainability + tests). */
    rule: "R1" | "R2" | "R3a" | "R3b" | "R4" | "R5" | "R6";
    /** The format to launch (baseline still points at Free Response as the on-ramp). */
    key: StudyFormatKey;
    /** Display title of `key`. */
    title: string;
    /** One-line, number-grounded reason. */
    why: string;
    /** Optional "start with <topic>" pointer into the Topic Mastery viz. */
    topic: StudyRecommendationTopic | null;
    /** Baseline only: steer to the diagnostic (it has not been taken yet). */
    takeDiagnostic: boolean;
}

/**
 * Decide which format to study next from the honest scores. Returns `null` when
 * there is nothing to base a recommendation on (no taxonomy / no `points`), so
 * the caller renders nothing and its existing "needs taxonomy.json" state shows
 * instead.
 *
 * Decision ladder (first match wins):
 *   R1  neither Memory nor Performance ready  -> honest baseline (build/diagnostic)
 *   R2  recall not built (Memory weak, or not ready while Performance is) -> Free Response
 *   R3a recall built + measured application gap >= APP_GAP_MIN            -> Passage Sets
 *   R3b recall built but application not yet measured                    -> Passage Sets
 *   R4  a dominating weak high-yield topic                               -> that topic's format
 *   R5  strong across the board                                         -> CARS
 *   R6  building steadily / balanced                                    -> Passage Sets
 */
export function recommendStudyFormat(
    points: RecommendPoints | null | undefined,
    context?: RecommendContext,
): StudyRecommendation | null {
    if (!points) {
        return null;
    }

    const memReady = points.meetsDataThreshold ?? false;
    const perf = points.performance ?? null;
    const perfReady = perf?.meetsDataThreshold ?? false;
    const memMean = points.memory?.mean ?? 0;
    const perfMean = perf?.mean ?? 0;
    const attempts = perf?.attempts ?? 0;
    const readiness = points.readiness ?? null;
    const readyPoint = readiness?.point ?? 0;
    const readyReady = readiness?.meetsDataThreshold ?? false;

    const topics = points.topics ?? [];
    const ranked = studyNextTopics(topics, topics.length);
    const topTopic = ranked[0] ?? null;
    const topicPointer: StudyRecommendationTopic | null = topTopic
        ? { category: topTopic.category, name: topTopic.name }
        : null;

    // --- R1: not enough data -> honest baseline (no profile claim) ---------
    if (!memReady && !perfReady) {
        const takeDiagnostic = context ? !(context.diagnosticTaken ?? false) : false;
        return {
            state: "baseline",
            rule: "R1",
            key: "fr",
            title: STUDY_FORMAT_TITLES.fr,
            why: takeDiagnostic
                ? "Not enough data yet. Take the ~20-minute diagnostic to seed your plan, then build a baseline with Free Response retrieval practice."
                : `Not enough data yet — your scores unlock as you review. Build a baseline with Free Response retrieval practice (Memory needs ${MIN_REVIEWS} reviews and ${
                    pct(MIN_COVERAGE)
                } coverage; Performance needs ${MIN_ATTEMPTS} attempts).`,
            topic: null,
            takeDiagnostic,
        };
    }

    // --- R2: recall not built -> Free Response (retrieval / generation) ----
    // Either Memory is measurably weak, or it has not cleared its gate yet
    // while Performance has (e.g. a CARS-heavy start). We do NOT claim an
    // application gap here — that requires a trustworthy Memory score.
    if ((memReady && memMean < RECALL_WEAK_MAX) || (!memReady && perfReady)) {
        const why = memReady
            ? `Recall isn't built yet (Memory ~${
                pct(memMean)
            }). Strengthen retrieval with Free Response — or Multiple Choice for a lighter start — before applying it under passage pressure.`
            : `You're still building your recall base (Memory needs ${MIN_REVIEWS} reviews and ${
                pct(MIN_COVERAGE)
            } coverage). Keep strengthening retrieval with Free Response; Multiple Choice is a lighter on-ramp.`;
        return {
            state: "recommend",
            rule: "R2",
            key: "fr",
            title: STUDY_FORMAT_TITLES.fr,
            why,
            topic: topicPointer,
            takeDiagnostic: false,
        };
    }

    // From here Memory has cleared its gate AND memMean >= RECALL_WEAK_MAX.

    // --- R3: recall built, application lagging/unmeasured -> Passage Sets ---
    if (perfReady && memMean - perfMean >= APP_GAP_MIN) {
        const gapPts = Math.round((memMean - perfMean) * 100);
        const tail = readyReady ? ` This is what's holding Readiness near ${Math.round(readyPoint)}.` : "";
        return {
            state: "recommend",
            rule: "R3a",
            key: "passage",
            title: STUDY_FORMAT_TITLES.passage,
            why: `You recall the content (Memory ~${pct(memMean)}) but apply it correctly only ${
                pct(perfMean)
            } of the time — a ${gapPts}-point gap beyond the normal recall-to-application drop. Train application on full Passage Sets.${tail}`,
            topic: topicPointer,
            takeDiagnostic: false,
        };
    }
    if (!perfReady) {
        return {
            state: "recommend",
            rule: "R3b",
            key: "passage",
            title: STUDY_FORMAT_TITLES.passage,
            why: `Your recall looks solid (Memory ~${
                pct(memMean)
            }), but you've logged only ${attempts}/${MIN_ATTEMPTS} exam-style attempts. Do Passage Sets so we can measure whether you can apply it.`,
            topic: topicPointer,
            takeDiagnostic: false,
        };
    }

    // --- R4: a dominating weak high-yield topic -> drill that topic --------
    if (topTopic && ranked.length >= 2) {
        const sortedPoints = ranked.map((t) => t.points).sort((a, b) => a - b);
        const mid = Math.floor(sortedPoints.length / 2);
        const median = sortedPoints.length % 2 === 1
            ? sortedPoints[mid]
            : (sortedPoints[mid - 1] + sortedPoints[mid]) / 2;
        const dominates = median > 0 && topTopic.points >= TOPIC_DOMINANCE_FACTOR * median;
        if (dominates) {
            const topPerf = (perf?.topics ?? []).find((t) => t.category === topTopic.category);
            const weakRecall = topTopic.gradedCards > 0 && topTopic.meanRetrievability < RECALL_WEAK_MAX;
            const weakApplication = !!topPerf
                && topPerf.attempts >= TOPIC_ACCURACY_MIN_ATTEMPTS
                && topPerf.accuracy < RECALL_WEAK_MAX;
            if (weakRecall || weakApplication) {
                const key: StudyFormatKey = weakApplication && !weakRecall ? "passage" : "fr";
                const where = weakApplication && !weakRecall
                    ? `you apply it right only ${pct(topPerf?.accuracy ?? 0)} of the time`
                    : `recall there is ~${pct(topTopic.meanRetrievability)}`;
                return {
                    state: "recommend",
                    rule: "R4",
                    key,
                    title: STUDY_FORMAT_TITLES[key],
                    why: `${topTopic.name} is your highest-value gap — ${
                        topTopic.topicWeight.toFixed(1)
                    }% of the exam and the most points at stake, and ${where}. Drill it with ${
                        STUDY_FORMAT_TITLES[key]
                    }.`,
                    topic: topicPointer,
                    takeDiagnostic: false,
                };
            }
        }
    }

    // --- R5: strong across the board -> CARS + stamina ---------------------
    // (CARS mastery is not directly measured — no content category — so this is
    // "train the least-trained, un-crammable skill", never "you're weak at CARS".)
    if (readyReady && memMean >= RECALL_STRONG_MIN && perfMean >= PERF_STRONG_MIN) {
        return {
            state: "recommend",
            rule: "R5",
            key: "cars",
            title: STUDY_FORMAT_TITLES.cars,
            why: `Content and application are both strong (Memory ~${pct(memMean)}, Performance ~${
                pct(perfMean)
            }, Readiness ~${
                Math.round(readyPoint)
            }). Train the skills section — CARS — and full Passage Sets for reasoning and stamina.`,
            topic: null,
            takeDiagnostic: false,
        };
    }

    // --- R6: building steadily / balanced -> keep applying -----------------
    return {
        state: "recommend",
        rule: "R6",
        key: "passage",
        title: STUDY_FORMAT_TITLES.passage,
        why: `You're building steadily (Memory ~${pct(memMean)}, Performance ~${
            pct(perfMean)
        }). Keep a balanced mix — Passage Sets apply what you already recall.`,
        topic: topicPointer,
        takeDiagnostic: false,
    };
}
