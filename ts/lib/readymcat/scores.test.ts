// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { describe, expect, test } from "vitest";

import {
    APP_GAP_MIN,
    MIN_ATTEMPTS,
    MIN_COVERAGE,
    MIN_REVIEWS,
    pct,
    PERF_STRONG_MIN,
    RECALL_STRONG_MIN,
    RECALL_WEAK_MAX,
    type RecommendableTopic,
    type RecommendableTopicPerformance,
    type RecommendPoints,
    recommendStudyFormat,
    SCORE_MAX,
    SCORE_MIN,
    studyNextTopics,
} from "./scores";

describe("readymcat give-up thresholds", () => {
    // These MIRROR the Rust source of truth in rslib/src/points_at_stake/mod.rs.
    // If a threshold changes there, change it here (and this test) too.
    test("match the documented Rust values", () => {
        expect(MIN_REVIEWS).toBe(200);
        expect(MIN_COVERAGE).toBe(0.5);
        expect(MIN_ATTEMPTS).toBe(30);
        expect(SCORE_MIN).toBe(472);
        expect(SCORE_MAX).toBe(528);
    });
});

describe("pct", () => {
    test("formats a 0..1 fraction as a whole-number percentage", () => {
        expect(pct(0)).toBe("0%");
        expect(pct(0.5)).toBe("50%");
        expect(pct(1)).toBe("100%");
        expect(pct(0.126)).toBe("13%");
    });
});

describe("studyNextTopics", () => {
    const topic = (
        category: string,
        topicWeight: number,
        studentWeakness: number,
        totalCards: number,
    ) => ({ category, topicWeight, studentWeakness, totalCards });

    test("ranks by points at stake (weight × weakness), highest first", () => {
        const topics = [
            topic("1A", 0.2, 0.5, 10), // 0.10
            topic("1B", 0.4, 0.5, 10), // 0.20
            topic("1C", 0.3, 0.9, 10), // 0.27
        ];
        const ranked = studyNextTopics(topics, 5);
        expect(ranked.map((t) => t.category)).toStrictEqual(["1C", "1B", "1A"]);
        expect(ranked[0].points).toBeCloseTo(0.27);
    });

    test("drops topics with no cards", () => {
        const topics = [
            topic("1A", 0.9, 0.9, 0), // excluded: no cards
            topic("1B", 0.1, 0.1, 4),
        ];
        expect(studyNextTopics(topics, 5).map((t) => t.category)).toStrictEqual(["1B"]);
    });

    test("caps the result at the requested limit", () => {
        const topics = Array.from({ length: 6 }, (_v, i) => topic(`c${i}`, 0.5, 0.5, 3));
        expect(studyNextTopics(topics, 4)).toHaveLength(4);
    });

    test("keeps the original fields alongside the computed points", () => {
        const [ranked] = studyNextTopics([topic("1A", 0.4, 0.5, 7)], 5);
        expect(ranked.category).toBe("1A");
        expect(ranked.totalCards).toBe(7);
        expect(ranked.points).toBeCloseTo(0.2);
    });
});

describe("recommendStudyFormat", () => {
    // A studied topic; studentWeakness mirrors the backend (1 - mean recall).
    const topic = (
        category: string,
        name: string,
        topicWeight: number,
        meanRetrievability: number,
        gradedCards = 10,
    ): RecommendableTopic => ({
        category,
        name,
        topicWeight,
        studentWeakness: 1 - meanRetrievability,
        gradedCards,
        totalCards: 20,
        meanRetrievability,
    });

    const points = (o: {
        memReady?: boolean;
        memMean?: number;
        perfReady?: boolean;
        perfMean?: number;
        attempts?: number;
        readyReady?: boolean;
        readyPoint?: number;
        topics?: RecommendableTopic[];
        perfTopics?: RecommendableTopicPerformance[];
    }): RecommendPoints => ({
        meetsDataThreshold: o.memReady ?? false,
        memory: { mean: o.memMean ?? 0 },
        performance: {
            mean: o.perfMean ?? 0,
            attempts: o.attempts ?? 0,
            meetsDataThreshold: o.perfReady ?? false,
            topics: o.perfTopics ?? [],
        },
        readiness: { point: o.readyPoint ?? 0, meetsDataThreshold: o.readyReady ?? false },
        topics: o.topics ?? [],
    });

    test("thresholds are the documented MVP values", () => {
        expect(RECALL_WEAK_MAX).toBe(0.6);
        expect(RECALL_STRONG_MIN).toBe(0.8);
        expect(APP_GAP_MIN).toBe(0.15);
        expect(PERF_STRONG_MIN).toBe(0.7);
    });

    test("returns null when there is no points payload (nothing to base it on)", () => {
        expect(recommendStudyFormat(null)).toBeNull();
        expect(recommendStudyFormat(undefined)).toBeNull();
    });

    // --- R1: not enough data -> honest baseline ----------------------------
    test("R1: abstains with a baseline and steers to the diagnostic when untaken", () => {
        const rec = recommendStudyFormat(
            points({ memReady: false, perfReady: false }),
            { diagnosticTaken: false },
        );
        expect(rec?.state).toBe("baseline");
        expect(rec?.rule).toBe("R1");
        expect(rec?.takeDiagnostic).toBe(true);
        expect(rec?.key).toBe("fr"); // Free Response is the retrieval on-ramp
        expect(rec?.why).toMatch(/diagnostic/i);
    });

    test("R1: once the diagnostic is taken, baseline drops the diagnostic CTA", () => {
        const rec = recommendStudyFormat(
            points({ memReady: false, perfReady: false }),
            { diagnosticTaken: true },
        );
        expect(rec?.rule).toBe("R1");
        expect(rec?.takeDiagnostic).toBe(false);
    });

    test("R1: with no context (dashboard) it never asserts the diagnostic state", () => {
        const rec = recommendStudyFormat(points({ memReady: false, perfReady: false }));
        expect(rec?.state).toBe("baseline");
        expect(rec?.takeDiagnostic).toBe(false);
    });

    // --- R2: recall not built -> Free Response -----------------------------
    test("R2: weak Memory -> Free Response, with Multiple Choice as the on-ramp", () => {
        const rec = recommendStudyFormat(
            points({ memReady: true, memMean: 0.45, perfReady: true, perfMean: 0.5 }),
        );
        expect(rec?.rule).toBe("R2");
        expect(rec?.key).toBe("fr");
        expect(rec?.why).toMatch(/Free Response/);
        expect(rec?.why).toMatch(/Multiple Choice/);
    });

    test("R2: Memory not ready while Performance is (CARS-heavy start) -> Free Response", () => {
        const rec = recommendStudyFormat(
            points({ memReady: false, perfReady: true, perfMean: 0.7, attempts: 40 }),
        );
        expect(rec?.rule).toBe("R2");
        expect(rec?.key).toBe("fr");
        expect(rec?.why).toMatch(/recall base/);
    });

    test("R2: surfaces a start-with-topic pointer when topics exist", () => {
        const rec = recommendStudyFormat(points({
            memReady: true,
            memMean: 0.4,
            perfReady: true,
            perfMean: 0.4,
            topics: [topic("1A", "Biomolecules", 5, 0.3)],
        }));
        expect(rec?.rule).toBe("R2");
        expect(rec?.topic?.category).toBe("1A");
    });

    // --- R3: recall built, application lagging/unmeasured -> Passage Sets ---
    test("R3a: strong recall but a real application gap -> Passage Sets (the core hypothesis)", () => {
        const rec = recommendStudyFormat(points({
            memReady: true,
            memMean: 0.85,
            perfReady: true,
            perfMean: 0.6, // gap 0.25 >= APP_GAP_MIN
            readyReady: true,
            readyPoint: 505,
        }));
        expect(rec?.rule).toBe("R3a");
        expect(rec?.key).toBe("passage");
        expect(rec?.why).toMatch(/Passage Sets/);
        expect(rec?.why).toMatch(/Readiness near 505/);
    });

    test("R3a: fires right at the APP_GAP_MIN boundary", () => {
        const rec = recommendStudyFormat(points({
            memReady: true,
            memMean: 0.8,
            perfReady: true,
            perfMean: 0.65, // gap ~0.15
            readyReady: true,
        }));
        expect(rec?.rule).toBe("R3a");
    });

    test("R3b: recall solid but application not yet measured -> Passage Sets to gather evidence", () => {
        const rec = recommendStudyFormat(
            points({ memReady: true, memMean: 0.8, perfReady: false, attempts: 12 }),
        );
        expect(rec?.rule).toBe("R3b");
        expect(rec?.key).toBe("passage");
        expect(rec?.why).toMatch(new RegExp(`12/${MIN_ATTEMPTS}`));
    });

    // --- R4: a dominating weak high-yield topic ----------------------------
    test("R4: a dominating topic weak in RECALL -> drill it with Free Response", () => {
        const rec = recommendStudyFormat(points({
            memReady: true,
            memMean: 0.75,
            perfReady: true,
            perfMean: 0.7, // gap 0.05 -> not R3a; perfReady -> not R3b
            readyReady: true,
            readyPoint: 508,
            topics: [
                topic("1A", "Biomolecules", 10, 0.4), // high weight, weak recall -> dominates
                topic("1B", "Cellular", 2, 0.9),
                topic("2A", "Systems", 2, 0.9),
            ],
        }));
        expect(rec?.rule).toBe("R4");
        expect(rec?.key).toBe("fr");
        expect(rec?.topic?.category).toBe("1A");
        expect(rec?.why).toMatch(/Biomolecules/);
    });

    test("R4: a dominating topic weak in APPLICATION (recall fine) -> Passage Sets", () => {
        const rec = recommendStudyFormat(points({
            memReady: true,
            memMean: 0.82,
            perfReady: true,
            perfMean: 0.78, // gap 0.04
            readyReady: true,
            readyPoint: 512,
            topics: [
                topic("1A", "Biomolecules", 10, 0.88), // recall fine, but...
                topic("1B", "Cellular", 2, 0.9),
                topic("2A", "Systems", 2, 0.9),
            ],
            perfTopics: [{ category: "1A", attempts: 20, accuracy: 0.4 }], // ...weak application
        }));
        expect(rec?.rule).toBe("R4");
        expect(rec?.key).toBe("passage");
        expect(rec?.topic?.category).toBe("1A");
    });

    // --- R5: strong across the board -> CARS -------------------------------
    test("R5: strong Memory + Performance -> CARS, no topic pointer", () => {
        const rec = recommendStudyFormat(points({
            memReady: true,
            memMean: 0.9,
            perfReady: true,
            perfMean: 0.8, // gap 0.10 < APP_GAP_MIN; both in strong bands
            readyReady: true,
            readyPoint: 515,
            topics: [topic("1A", "Biomolecules", 5, 0.9), topic("1B", "Cellular", 5, 0.88)],
        }));
        expect(rec?.rule).toBe("R5");
        expect(rec?.key).toBe("cars");
        expect(rec?.topic).toBeNull();
        expect(rec?.why).toMatch(/CARS/);
    });

    // --- R6: building steadily / balanced -> Passage Sets ------------------
    test("R6: solid-but-not-strong, no dominating gap -> balanced Passage Sets", () => {
        const rec = recommendStudyFormat(points({
            memReady: true,
            memMean: 0.7,
            perfReady: true,
            perfMean: 0.65, // gap 0.05; neither in a strong band
            readyReady: true,
            readyPoint: 502,
            topics: [topic("1A", "Biomolecules", 5, 0.7), topic("1B", "Cellular", 5, 0.68)],
        }));
        expect(rec?.rule).toBe("R6");
        expect(rec?.key).toBe("passage");
        expect(rec?.topic?.category).toBeDefined();
    });
});
