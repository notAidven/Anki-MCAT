// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Regression coverage for the ReadyMCAT "Study Now does not show questions"
// bug: launching study for any of the four pre-loaded decks — via BOTH the
// deck browser's native Study Now and the home-hub category tiles — must land
// on an interactive, answerable question rather than a blank reviewer, and a
// wrong answer must still trigger teach-on-miss (guiding ladder + struggling
// flag).
//
// The interactive reviewer renders into the desktop Qt webview (mw.web), which
// the Playwright harness (its own Chromium, talking HTTP to mediasrv) cannot
// load directly. So this suite drives the real launch flows and reads back what
// the reviewer actually painted through the dev-only `readymcatStudyProbe`
// mediasrv endpoint (qt/aqt/mediasrv.py -> readymcat_home.study_probe), gated
// behind dev_mode/ANKIDEV which the e2e launcher sets.

import type { APIResponse, Page } from "@playwright/test";

import { expect, test } from "./fixtures";

const DECK_KEYS = ["mcq", "fr", "passage", "cars"] as const;
type DeckKey = (typeof DECK_KEYS)[number];

// The interactive reviewer state each deck's first card drives. CARS reuses the
// passage note type / reviewer, so it also reports "passage".
const EXPECTED_STATE: Record<DeckKey, string> = {
    mcq: "mcq",
    fr: "fr",
    passage: "passage",
    cars: "passage",
};

interface ProbeResult {
    ok: boolean;
    state?: string;
    card?: boolean;
    qa?: string;
    qaLen?: number;
    interactive?: boolean;
    struggling?: boolean;
    error?: string;
}

// mediasrv only accepts application/binary POSTs (it ignores the declared type
// and reads the raw body). Go through page.request so this runs in Node against
// the configured baseURL.
async function postAnki(
    page: Page,
    path: string,
    body: string,
): Promise<APIResponse> {
    return page.request.post(`/_anki/${path}`, {
        headers: { "Content-Type": "application/binary" },
        data: body,
    });
}

async function probe(
    page: Page,
    options: Record<string, unknown>,
): Promise<ProbeResult> {
    const res = await postAnki(page, "readymcatStudyProbe", JSON.stringify(options));
    expect(res.ok(), `probe HTTP ${res.status()} for ${JSON.stringify(options)}`)
        .toBeTruthy();
    return res.json() as Promise<ProbeResult>;
}

// First-launch provisioning runs deferred on the main thread; wait until every
// format's deck exists before probing (mirrors readymcat_home_shot.test.ts).
async function waitForProvision(page: Page): Promise<void> {
    for (let i = 0; i < 60; i++) {
        const res = await postAnki(page, "readymcatHomeStatus", "");
        if (res.ok()) {
            const status = await res.json();
            const decks = status?.decks ?? {};
            // Key off presence only: a prior probe's reused launcher filtered
            // deck may be holding a deck's cards (dropping its `total` toward 0)
            // without the deck being un-provisioned.
            if (DECK_KEYS.every((k) => decks[k]?.present)) {
                return;
            }
        }
        await page.waitForTimeout(1500);
    }
    throw new Error("ReadyMCAT decks were not provisioned in time");
}

test.setTimeout(180_000);

test.beforeEach(async ({ page }) => {
    await waitForProvision(page);
});

test("home-hub tiles open an interactive question for all four decks", async ({ page }) => {
    for (const key of DECK_KEYS) {
        const result = await probe(page, { key });
        expect(result.ok, `tile ${key}: ${result.error ?? ""}`).toBeTruthy();
        expect(result.card, `tile ${key}: no card loaded`).toBeTruthy();
        // The bug: a card loads but the reviewer webview stays blank.
        expect(result.qaLen ?? 0, `tile ${key}: reviewer #qa was empty`)
            .toBeGreaterThan(0);
        expect(result.interactive, `tile ${key}: not the interactive reviewer`)
            .toBeTruthy();
        expect(result.state, `tile ${key}: wrong reviewer`).toBe(EXPECTED_STATE[key]);
    }
});

test("native Study Now opens an interactive question for all four decks", async ({ page }) => {
    for (const key of DECK_KEYS) {
        const result = await probe(page, { key, native: true });
        expect(result.ok, `native ${key}: ${result.error ?? ""}`).toBeTruthy();
        expect(result.card, `native ${key}: no card loaded`).toBeTruthy();
        expect(result.qaLen ?? 0, `native ${key}: reviewer #qa was empty`)
            .toBeGreaterThan(0);
        expect(result.interactive, `native ${key}: not the interactive reviewer`)
            .toBeTruthy();
        expect(result.state, `native ${key}: wrong reviewer`).toBe(EXPECTED_STATE[key]);
    }
});

test("MCQ is answerable and a wrong answer triggers teach-on-miss", async ({ page }) => {
    // A first-try correct answer reveals the explanation and a Continue button,
    // and must NOT drop into the guiding ladder.
    const correct = await probe(page, { key: "mcq", answer: "correct" });
    expect(correct.ok).toBeTruthy();
    expect(correct.qa ?? "").toContain("rmcq-explanation");
    expect(correct.qa ?? "").toContain("Continue");
    expect(correct.qa ?? "").not.toContain("Start guiding questions");

    // A wrong first answer must trigger teach-on-miss: the guiding ladder is
    // offered instead of just handing over the answer.
    const wrong = await probe(page, { key: "mcq", answer: "wrong" });
    expect(wrong.ok).toBeTruthy();
    expect(wrong.qa ?? "").toContain("Start guiding questions");
    // Retrieve-before-reveal: on a first miss the answer stays HIDDEN — the
    // correct option must NOT be highlighted and no explanation is shown. Only
    // the guiding-questions button is offered.
    expect(wrong.qa ?? "", "the correct option was revealed on a first miss")
        .not.toContain("rmcq-option correct");
    expect(wrong.qa ?? "", "the explanation was revealed on a first miss")
        .not.toContain("rmcq-explanation");

    // Working through the ladder and still missing flags the concept as
    // struggling (so the points-at-stake queue resurfaces it).
    const wrongFull = await probe(page, { key: "mcq", answer: "wrongFull" });
    expect(wrongFull.ok).toBeTruthy();
    expect(wrongFull.struggling, "a repeated miss did not flag struggling")
        .toBeTruthy();
});
