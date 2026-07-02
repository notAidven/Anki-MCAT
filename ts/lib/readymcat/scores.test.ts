// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { describe, expect, test } from "vitest";

import { MIN_ATTEMPTS, MIN_COVERAGE, MIN_REVIEWS, pct, SCORE_MAX, SCORE_MIN, studyNextTopics } from "./scores";

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
