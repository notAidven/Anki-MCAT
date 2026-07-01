// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Screenshot helper for the ReadyMCAT home / study-launcher hub. Skipped in
// the normal e2e suite; opt in with READYMCAT_SHOT_CAPTURE=1, e.g.
//   READYMCAT_SHOT_CAPTURE=1 READYMCAT_SEED_DEMO=1 \
//     yarn test:e2e ts/tests/e2e/readymcat_home_shot.test.ts
// The launcher (qt/tests/launch_anki_for_e2e.py) inherits READYMCAT_SEED_DEMO,
// so it auto-seeds SYNTHETIC review history (memory/progress populate) on top
// of the always-on first-launch MCQ/FR/Passage/CARS provisioning, which is
// what makes the hub's tile counts non-zero even without seeding.

import type { Page } from "@playwright/test";
import { mkdirSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { expect, test } from "./fixtures";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const taxonomy = resolve(repoRoot, "taxonomy.json");
const outDir = resolve(repoRoot, "readymcat");
const url = `/readymcat-home?taxonomy=${encodeURIComponent(taxonomy)}`;
// Only run when explicitly capturing, so the standard e2e suite stays fast
// and doesn't require a seeded/provisioned profile.
const capture = process.env.READYMCAT_SHOT_CAPTURE === "1";

test.setTimeout(120_000);

// Reload until the hub renders (provisioning/seeding may lag server readiness).
async function waitForHub(page: Page): Promise<void> {
    for (let i = 0; i < 20; i++) {
        await page.goto(url);
        const tile = page.locator(".tiles button.tile").first();
        try {
            await tile.waitFor({ state: "visible", timeout: 30_000 });
            break;
        } catch {
            // try again
        }
    }
    await expect(page.locator(".tiles button.tile").first()).toBeVisible({
        timeout: 10_000,
    });
    // let any transitions/reactive layout settle before capturing.
    await page.waitForTimeout(500);
}

(capture ? test : test.skip)("readymcat home hub screenshot (desktop)", async ({
    page,
}) => {
    mkdirSync(outDir, { recursive: true });
    await page.setViewportSize({ width: 1180, height: 900 });
    await waitForHub(page);
    await page.screenshot({
        path: resolve(outDir, "readymcat-home-hub-desktop.png"),
        fullPage: true,
    });
});

(capture ? test : test.skip)("readymcat home hub screenshot (mobile)", async ({
    page,
}) => {
    mkdirSync(outDir, { recursive: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await waitForHub(page);
    await page.screenshot({
        path: resolve(outDir, "readymcat-home-hub-mobile.png"),
        fullPage: true,
    });
});
