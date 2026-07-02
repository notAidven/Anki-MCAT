// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Single-window coverage for the ReadyMCAT tab bar: the four surfaces —
// Home · Study · Decks · Dashboard — must all render inside ONE Qt window,
// swapping content in place rather than opening separate popup windows.
//
// The tabs are Qt toolbar navigations that render the ReadyMCAT SvelteKit pages
// into a dedicated (API-capable) web view and the deck browser/reviewer into the
// shared mw.web — none of which the Playwright harness (its own Chromium talking
// HTTP to mediasrv) can load directly. So this suite drives a real tab switch
// through the dev-only `readymcatTabProbe` endpoint (qt/aqt/mediasrv.py ->
// readymcat_home.tab_probe, gated behind dev_mode/ANKIDEV which the e2e launcher
// sets) and reads back what each tab's live web view actually painted.

import type { APIResponse, Page } from "@playwright/test";

import { expect, test } from "./fixtures";

const DECK_KEYS = ["mcq", "fr", "passage", "cars"] as const;

interface TabProbeResult {
    ok: boolean;
    tab?: string;
    state?: string;
    // whether the shared mw.web is the visible central widget (True for
    // Decks/Study; False for the API-capable Home/Dashboard views)
    centralIsMainWeb?: boolean;
    found?: boolean;
    markerLen?: number;
    qaLen?: number;
    interactive?: boolean;
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

async function tabProbe(
    page: Page,
    options: Record<string, unknown>,
): Promise<TabProbeResult> {
    const res = await postAnki(page, "readymcatTabProbe", JSON.stringify(options));
    expect(res.ok(), `tab probe HTTP ${res.status()} for ${JSON.stringify(options)}`)
        .toBeTruthy();
    return res.json() as Promise<TabProbeResult>;
}

// First-launch provisioning runs deferred on the main thread; wait until every
// format's deck exists before probing (mirrors readymcat_study.test.ts).
async function waitForProvision(page: Page): Promise<void> {
    for (let i = 0; i < 60; i++) {
        const res = await postAnki(page, "readymcatHomeStatus", "");
        if (res.ok()) {
            const status = await res.json();
            const decks = status?.decks ?? {};
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

test("Home and Dashboard tabs render in-window (own API-capable view)", async ({ page }) => {
    // The Home hub + honest-memory Dashboard render their SvelteKit page into a
    // dedicated web view (NOT the shared mw.web, which lacks internal-API access
    // for their pointsAtStakeQueue/readymcatHomeStatus fetches).
    for (const tab of ["home", "dashboard"] as const) {
        const r = await tabProbe(page, { tab });
        expect(r.ok, `${tab}: ${r.error ?? ""}`).toBeTruthy();
        expect(r.found, `${tab}: content marker did not render`).toBeTruthy();
        expect(r.markerLen ?? 0, `${tab}: content was empty`).toBeGreaterThan(0);
        expect(r.centralIsMainWeb, `${tab}: must not render into the shared mw.web`)
            .toBeFalsy();
    }
});

test("Decks tab renders the deck browser in the same window", async ({ page }) => {
    const decks = await tabProbe(page, { tab: "decks" });
    expect(decks.ok, `decks: ${decks.error ?? ""}`).toBeTruthy();
    expect(decks.state, "decks: not the deck browser").toBe("deckBrowser");
    expect(decks.found, "decks: deck browser did not render").toBeTruthy();
    expect(decks.centralIsMainWeb, "decks: should render into the shared mw.web")
        .toBeTruthy();
});

test("Study tab serves an interactive question in the same window", async ({ page }) => {
    const study = await tabProbe(page, { tab: "study", key: "mcq" });
    expect(study.ok, `study: ${study.error ?? ""}`).toBeTruthy();
    expect(study.state, "study: did not enter the reviewer").toBe("review");
    // The bug the reviewer regressions guard: a card loads but #qa stays blank.
    expect(study.qaLen ?? 0, "study: reviewer #qa was empty").toBeGreaterThan(0);
    expect(study.interactive, "study: not the interactive reviewer").toBeTruthy();
    expect(study.centralIsMainWeb, "study: should render into the shared mw.web")
        .toBeTruthy();
});
