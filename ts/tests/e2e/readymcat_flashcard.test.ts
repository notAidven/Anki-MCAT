// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// End-to-end coverage for the retrieve-BEFORE-reveal teach-on-miss flow on
// basic front/back flashcards. On a demo authorless flashcard, taking the
// question-side "Stuck? work it out" path must run a guiding ladder (here
// AI-generated from the card's front/back) with the back STILL hidden — i.e.
// the ladder appears before the answer is revealed.
//
// This drives the real desktop reviewer through the dev-only
// `readymcatFlashcardProbe` mediasrv endpoint (the reviewer renders into the
// Qt mw.web webview, which the Playwright harness cannot observe directly),
// mirroring readymcat_study.test.ts. It is OPT-IN — it needs the SYNTHETIC demo
// seeded (READYMCAT_SEED_DEMO=1) and a live OPENAI_API_KEY for generation — so
// it is skipped in the standard suite and enabled with:
//   READYMCAT_FLASHCARD_CAPTURE=1 READYMCAT_SEED_DEMO=1 OPENAI_API_KEY=... \
//     yarn test:e2e ts/tests/e2e/readymcat_flashcard.test.ts

import type { APIResponse, Page } from "@playwright/test";

import { expect, test } from "./fixtures";

const capture = process.env.READYMCAT_FLASHCARD_CAPTURE === "1";

interface FlashcardProbe {
    ok: boolean;
    state?: string;
    card?: boolean;
    qa?: string;
    qaLen?: number;
    ladderShown?: boolean;
    loading?: boolean;
    answerHidden?: boolean;
    error?: string;
}

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

async function flashcardProbe(
    page: Page,
    options: Record<string, unknown>,
): Promise<FlashcardProbe> {
    const res = await postAnki(page, "readymcatFlashcardProbe", JSON.stringify(options));
    expect(res.ok(), `probe HTTP ${res.status()}`).toBeTruthy();
    return res.json() as Promise<FlashcardProbe>;
}

// The demo flashcards are seeded at collection load; poll the probe until the
// deck exists (front card loads) before exercising the "Stuck?" path.
async function waitForFlashcardDeck(page: Page): Promise<void> {
    for (let i = 0; i < 60; i++) {
        const res = await flashcardProbe(page, { stuck: false });
        if (res.ok && res.card) {
            return;
        }
        await page.waitForTimeout(1500);
    }
    throw new Error("demo flashcard deck was not seeded in time");
}

test.setTimeout(180_000);

(capture ? test : test.skip)(
    "a demo flashcard 'Stuck? work it out' runs a ladder before revealing the back",
    async ({ page }) => {
        await waitForFlashcardDeck(page);

        // 1) The front is shown, back not yet revealed (normal question state).
        const front = await flashcardProbe(page, { stuck: false });
        expect(front.ok).toBeTruthy();
        expect(front.state).toBe("question");
        expect(front.qaLen ?? 0).toBeGreaterThan(0);

        // 2) Taking the retrieve-first path runs the guiding ladder with the
        //    back STILL hidden — the whole point of retrieve-before-reveal.
        const stuck = await flashcardProbe(page, { stuck: true, wait_ms: 90000 });
        expect(stuck.ok, stuck.error ?? "").toBeTruthy();
        expect(stuck.state, "expected the teaching (ladder) state").toBe("teaching");
        expect(stuck.ladderShown, "guiding ladder did not render").toBeTruthy();
        expect(stuck.loading, "still on the 'building…' spinner").toBeFalsy();
        expect(stuck.answerHidden, "the back was revealed before the ladder").toBeTruthy();
        // The ladder is the teach-on-miss UI asking a guiding question first.
        expect(stuck.qa ?? "").toContain("tom-wrap");
        expect(stuck.qa ?? "").toContain("Reveal sub-answer");
    },
);
