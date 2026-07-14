// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Screenshot helper for the ReadyMCAT honest-scores dashboard (Memory,
// Performance, Readiness). Skipped in the normal e2e suite; opt in with
// READYMCAT_SHOT_CAPTURE=1, e.g.
//   READYMCAT_SHOT_CAPTURE=1 READYMCAT_SEED_DEMO=1 READYMCAT_SHOT=populated \
//     yarn test:e2e ts/tests/e2e/readymcat_dashboard_shot.test.ts
// The launcher (qt/tests/launch_anki_for_e2e.py) inherits READYMCAT_SEED_DEMO,
// so "populated" auto-seeds SYNTHETIC demo data (enough that ALL THREE scores
// clear their give-up thresholds); without it the empty profile renders the
// honest give-up/abstain state in every stat card.

import type { Locator, Page } from "@playwright/test";
import { mkdirSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { expect, test } from "./fixtures";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const taxonomy = resolve(repoRoot, "taxonomy.json");
const outDir = resolve(repoRoot, "readymcat");
const shot = process.env.READYMCAT_SHOT ?? "populated";
const url = `/readymcat-dashboard?taxonomy=${encodeURIComponent(taxonomy)}`;
// Only run when explicitly capturing, so the standard e2e suite stays fast and
// doesn't require a seeded profile.
const capture = process.env.READYMCAT_SHOT_CAPTURE === "1";

test.use({ viewport: { width: 860, height: 1000 } });
// Demo seeding can still be running as mediasrv starts answering, so allow
// generous time for the expected state to appear.
test.setTimeout(120_000);

// Reload until the expected state renders (seeding may lag server readiness).
async function waitForState(page: Page, target: Locator): Promise<void> {
    for (let i = 0; i < 20; i++) {
        await page.goto(url);
        await page.locator(".dashboard .card").first().waitFor({
            state: "visible",
            timeout: 30_000,
        });
        await page.waitForTimeout(500);
        if ((await target.count()) > 0) {
            break;
        }
    }
    await expect(target.first()).toBeVisible({ timeout: 10_000 });
    // Let bar/gauge width transitions settle before capturing.
    await page.waitForTimeout(600);
}

(capture ? test : test.skip)(`readymcat dashboard screenshot (${shot})`, async ({
    page,
}) => {
    mkdirSync(outDir, { recursive: true });

    if (shot === "populated") {
        // A populated stat shows a real range (not the ".muted" give-up text).
        await waitForState(page, page.locator(".stat .stat-range:not(.muted)"));

        // All three headline scores must be populated at once.
        await expect(page.locator(".stat:not(.is-giveup)")).toHaveCount(3);
        for (const label of ["Memory", "Performance", "Readiness"]) {
            await expect(
                page.locator(".stat .eyebrow", { hasText: label }).first(),
            ).toBeVisible();
        }
        // Readiness must stay honestly flagged as a heuristic projection.
        await expect(page.locator(".stat.readiness .caveat")).toContainText(
            /uncalibrated|heuristic/i,
        );

        await page.screenshot({
            path: resolve(outDir, "readymcat-dashboard-simplified.png"),
            fullPage: true,
        });

        // Expand the collapsible per-topic table so the full breakdown
        // (including "no data" topics) is visible in one capture.
        const summary = page.locator("details.details summary");
        if ((await summary.count()) > 0) {
            await summary.click();
            await page.waitForTimeout(300);
            await page.screenshot({
                path: resolve(outDir, "readymcat-dashboard-simplified-expanded.png"),
                fullPage: true,
            });
        }
    } else {
        // Empty profile: every stat card renders its honest give-up state.
        await waitForState(page, page.locator(".stat.is-giveup"));
        await expect(page.locator(".stat.is-giveup")).toHaveCount(3);
        await page.screenshot({
            path: resolve(outDir, `readymcat-dashboard-${shot}.png`),
            fullPage: true,
        });
    }
});
