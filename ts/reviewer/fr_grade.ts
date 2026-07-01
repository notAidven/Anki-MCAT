// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// ReadyMCAT free-response auto-grader (pure, testable).
//
// This is the browser-side mirror of the canonical Python grader in
// readymcat/tools/build_question_bank.py (grade_free_response). The two MUST
// stay in lockstep: the reviewer grades a typed answer here for immediate
// feedback, and Python only records the outcome the reviewer reports. Both are
// covered by unit tests (ts/reviewer/fr_grade.test.ts and
// pylib/tests/test_readymcat_free_response.py) to catch any drift.
//
// An answer is correct when ANY of these hold:
//  * it parses to a number matching an accepted numeric answer (within the
//    tolerance parsed from key_terms when provided, else effectively exactly);
//  * its normalised (or squashed) form equals an accepted answer;
//  * every non-directive key term appears in it (so prose / derivations that
//    contain the essential terms still count).

const NUMBER_RE = /[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?/;
const TOLERANCE_RE =
    /tolerance\s*[:=]?\s*[±+\-]?\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(%?)/i;

/** Lowercase, strip punctuation, and collapse whitespace for comparison. */
export function normalizeAnswer(text: string): string {
    const lowered = (text ?? "").toString().trim().toLowerCase();
    // strip anything that is not a letter, number, underscore or whitespace
    const depunct = lowered.replace(/[^\p{L}\p{N}_\s]/gu, " ");
    return depunct.replace(/\s+/g, " ").trim();
}

/** Normalise then drop all non-alphanumerics (loose match for equations). */
export function squash(text: string): string {
    return normalizeAnswer(text).replace(/[^a-z0-9]/g, "");
}

/** Best-effort leading numeric value in a string ("30 m/s" -> 30). */
export function toNumber(text: string): number | null {
    const match = (text ?? "").toString().replace(/,/g, "").match(NUMBER_RE);
    if (!match) {
        return null;
    }
    const value = parseFloat(match[0]);
    return Number.isNaN(value) ? null : value;
}

interface Tolerance {
    magnitude: number;
    isPercent: boolean;
}

/** Extract a numeric tolerance from a "tolerance: ±0.5 m/s" key term. */
export function toleranceFromKeyTerms(keyTerms: string[]): Tolerance | null {
    for (const term of keyTerms ?? []) {
        if (term.toLowerCase().includes("tolerance")) {
            const match = term.match(TOLERANCE_RE);
            if (match) {
                return {
                    magnitude: Math.abs(parseFloat(match[1])),
                    isPercent: match[2] === "%",
                };
            }
        }
    }
    return null;
}

function nonDirectiveKeyTerms(keyTerms: string[]): string[] {
    return (keyTerms ?? []).filter((term) => {
        const low = term.trim().toLowerCase();
        return !low.startsWith("tolerance") && !low.startsWith("unit");
    });
}

/** Auto-grade a typed answer against accepted answers / key terms. */
export function gradeFreeResponse(
    userAnswer: string,
    acceptedAnswers: string[],
    keyTerms: string[] = [],
): boolean {
    acceptedAnswers = acceptedAnswers ?? [];
    keyTerms = keyTerms ?? [];
    const userNorm = normalizeAnswer(userAnswer);
    if (!userNorm) {
        return false;
    }
    const userSquash = squash(userAnswer);
    const userNum = toNumber(userAnswer);
    const tolerance = toleranceFromKeyTerms(keyTerms);

    // 1. numeric match (respecting a provided tolerance)
    if (userNum !== null) {
        for (const accepted of acceptedAnswers) {
            const acceptedNum = toNumber(accepted);
            if (acceptedNum === null) {
                continue;
            }
            if (tolerance) {
                const bound = tolerance.isPercent
                    ? (tolerance.magnitude / 100) * Math.abs(acceptedNum)
                    : tolerance.magnitude;
                if (Math.abs(userNum - acceptedNum) <= bound + 1e-9) {
                    return true;
                }
            } else if (Math.abs(userNum - acceptedNum) <= 1e-9) {
                return true;
            }
        }
    }

    // 2. normalised / squashed string match
    for (const accepted of acceptedAnswers) {
        if (!accepted || !accepted.toString().trim()) {
            continue;
        }
        const acceptedSquash = squash(accepted);
        if (
            normalizeAnswer(accepted) === userNorm
            || (acceptedSquash && acceptedSquash === userSquash)
        ) {
            return true;
        }
    }

    // 3. every non-directive key term present in the answer
    const terms = nonDirectiveKeyTerms(keyTerms)
        .map(squash)
        .filter((term) => term.length >= 3);
    if (terms.length > 0 && terms.every((term) => userSquash.includes(term))) {
        return true;
    }

    return false;
}
