// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Single source of truth for the plain-language explanations shown behind the
// info tooltips on the ReadyMCAT desktop UI. Keeping every definition here (and
// nowhere else) means the honest-scores dashboard and the home hub always agree
// about what a term means and how it is measured.
//
// The wording is deliberately faithful to docs/ReadyMCAT-PRD.md — specifically
// the "HONEST SCORES: MEMORY, PERFORMANCE, READINESS" and "TOPICS, THE DECK,
// AND COVERAGE" sections — so the UI never overstates what a number can back up.

export interface GlossaryEntry {
    /** Popover heading (usually the term itself). */
    title: string;
    /** One line: what the term/statistic actually is. */
    what: string;
    /** Optional: how it is computed or measured. */
    how?: string;
    /** Optional: an honest caveat or the give-up rule that guards it. */
    note?: string;
}

export type GlossaryKey =
    | "memory"
    | "performance"
    | "readiness"
    | "fsrs"
    | "coverage"
    | "pointsAtStake"
    | "confidence"
    | "giveUp"
    | "studyNext";

export const glossary: Record<GlossaryKey, GlossaryEntry> = {
    memory: {
        title: "Memory",
        what: "The chance you'd recall a card correctly right now.",
        how: "Taken from FSRS's per-card recall probability, aggregated across each AAMC topic. Always shown as a 95% range with a confidence level — never a bare number.",
        note: "Give-up rule: hidden until you have at least 200 graded reviews and 50% outline coverage.",
    },
    performance: {
        title: "Performance",
        what: "Your accuracy on exam-style questions — the first-attempt correct rate on the practice questions.",
        how: "Read straight from the review log (first try correct = hit; anything that needed the teach-on-miss ladder = miss) and shown as a Wilson 95% range.",
        note: "Give-up rule: hidden until you have at least 30 first attempts.",
    },
    readiness: {
        title: "Readiness",
        what: "A projected score on the real MCAT 472–528 scale — a directional estimate of where you'd land.",
        how: "A heuristic blend of Performance and Memory (weighted 0.6 / 0.4) mapped onto 472–528, with the range widened for exam weight your bank doesn't cover yet.",
        note:
            "Heuristic and uncalibrated — explicitly NOT a real or calibrated MCAT score. Shown only once both Memory and Performance have enough data.",
    },
    fsrs: {
        title: "FSRS recall",
        what:
            "FSRS (Free Spaced Repetition Scheduler) is the algorithm that models how likely you are to remember each card at a given moment.",
        how: "\u201CRecall\u201D is that per-card probability; Memory averages it across a topic's cards.",
    },
    coverage: {
        title: "Coverage",
        what: "The percent of the 31 official AAMC content categories your question bank has cards for.",
        how: "CARS has no AAMC category, so it's excluded. Coverage also gates the Memory score's give-up rule.",
    },
    pointsAtStake: {
        title: "Points at stake",
        what: "How much studying a topic is worth right now: its exam weight \u00D7 how weak you are in it.",
        how: "This is the ordering behind \u201Cwhat to study next\u201D — high-yield, weak topics rank first. It's an order, not a score.",
    },
    confidence: {
        title: "Confidence & range",
        what: "Every score is a range, not a single number; confidence is how wide that 95% interval is.",
        how: "More evidence narrows the range (higher confidence); less evidence widens it (lower confidence).",
    },
    giveUp: {
        title: "Not enough data yet",
        what:
            "Each score stays hidden until there's enough evidence to back it up — the app won't show a number it can't stand behind.",
        how: "Memory needs \u2265200 graded reviews and \u226550% coverage; Performance needs \u226530 first attempts; Readiness needs both.",
    },
    studyNext: {
        title: "Study next",
        what: "One suggested format to study next, read straight from your honest scores.",
        how: "Weak recall \u2192 Free Response to build retrieval; recall built but application lagging \u2192 Passage Sets; strong across the board \u2192 CARS. It also points you at your highest points-at-stake topic. It's a nudge, not a score.",
        note:
            "Until Memory and Performance have enough data it won't guess \u2014 it steers you to build a baseline (or take the diagnostic).",
    },
};
