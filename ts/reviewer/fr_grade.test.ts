// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { expect, test } from "vitest";

import { gradeFreeResponse, normalizeAnswer, toleranceFromKeyTerms, toNumber } from "./fr_grade";

/* eslint
@typescript-eslint/no-explicit-any: "off",
 */

// These mirror pylib/tests/test_readymcat_free_response.py so the browser-side
// grader and the canonical Python grader stay in lockstep.

test("normalizes case, punctuation and whitespace", () => {
    expect(normalizeAnswer("  Peptide-BOND!! ")).toBe("peptide bond");
    expect(normalizeAnswer(null as any)).toBe("");
});

test("extracts leading numeric value", () => {
    expect(toNumber("30 m/s")).toBe(30);
    expect(toNumber("v = 30 m/s")).toBe(30);
    expect(toNumber("zero")).toBe(null);
    expect(toNumber("1,000")).toBe(1000);
});

test("accepts exact and normalized variants", () => {
    const accepted = ["Peptide bond", "amide bond", "peptide (amide) bond"];
    const keyTerms = ["peptide"];
    expect(gradeFreeResponse("peptide bond", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("  PEPTIDE  BOND ", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("amide-bond", accepted, keyTerms)).toBe(true);
    // prose containing the key term still counts
    expect(gradeFreeResponse("it is a peptide linkage", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("glycosidic bond", accepted, keyTerms)).toBe(false);
});

test("numeric tolerance (absolute) from key terms", () => {
    const accepted = ["30 m/s", "30 m s^-1", "v = 30 m/s", "30"];
    const keyTerms = ["unit: m/s", "tolerance: ±0.5 m/s", "v = g t"];
    expect(gradeFreeResponse("30 m s^-1", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("30.4", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("29.6 m/s", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("30.9", accepted, keyTerms)).toBe(false);
    expect(gradeFreeResponse("45 m/s", accepted, keyTerms)).toBe(false);
});

test("numeric tolerance (percent) from key terms", () => {
    const accepted = ["100 kPa", "100"];
    const keyTerms = ["tolerance: ±5%"];
    expect(gradeFreeResponse("103 kPa", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("95", accepted, keyTerms)).toBe(true);
    expect(gradeFreeResponse("120", accepted, keyTerms)).toBe(false);
});

test("without a tolerance, numbers must (near-)match exactly", () => {
    const accepted = ["0", "0 m/s", "zero"];
    expect(gradeFreeResponse("0", accepted, [])).toBe(true);
    expect(gradeFreeResponse("zero", accepted, [])).toBe(true);
    expect(gradeFreeResponse("0.4", accepted, [])).toBe(false);
});

test("rejects empty / blank answers", () => {
    expect(gradeFreeResponse("", ["glycine"], ["glycine"])).toBe(false);
    expect(gradeFreeResponse("   ", ["glycine"], ["glycine"])).toBe(false);
});

test("parses tolerance directives", () => {
    expect(toleranceFromKeyTerms(["tolerance: ±0.5 m/s"])).toEqual({
        magnitude: 0.5,
        isPercent: false,
    });
    expect(toleranceFromKeyTerms(["tolerance: ±5%"])).toEqual({
        magnitude: 5,
        isPercent: true,
    });
    expect(toleranceFromKeyTerms(["unit: m/s", "v = g t"])).toBe(null);
});
