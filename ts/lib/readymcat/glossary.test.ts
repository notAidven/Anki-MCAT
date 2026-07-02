// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { describe, expect, test } from "vitest";

import type { GlossaryKey } from "./glossary";
import { glossary } from "./glossary";

// The glossary is the single source of truth shared by the dashboard and the
// home hub, so guard that every term the UI references stays present and filled
// in. If a screen starts referencing a new key, add it here too.
const REQUIRED_KEYS: GlossaryKey[] = [
    "memory",
    "performance",
    "readiness",
    "fsrs",
    "coverage",
    "pointsAtStake",
    "confidence",
    "giveUp",
];

describe("readymcat glossary", () => {
    test("defines every term the UI relies on", () => {
        for (const key of REQUIRED_KEYS) {
            expect(glossary[key], key).toBeDefined();
        }
    });

    test("each entry has a non-empty title and explanation", () => {
        for (const key of REQUIRED_KEYS) {
            const entry = glossary[key];
            expect(entry.title.trim().length, `${key} title`).toBeGreaterThan(0);
            expect(entry.what.trim().length, `${key} what`).toBeGreaterThan(0);
        }
    });

    test("the three headline stats spell out their give-up rule", () => {
        for (const key of ["memory", "performance", "readiness"] as const) {
            expect(glossary[key].note, `${key} note`).toBeTruthy();
        }
    });
});
