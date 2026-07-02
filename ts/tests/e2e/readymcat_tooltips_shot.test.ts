// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Screenshot + interaction proof for the ReadyMCAT explanatory info tooltips
// (the InfoTooltip popover wired into the honest-scores Dashboard and the home
// hub score pills). Skipped in the normal e2e suite; opt in with
// READYMCAT_TOOLTIP_CAPTURE=1, e.g.
//   READYMCAT_TOOLTIP_CAPTURE=1 READYMCAT_SEED_DEMO=1 ANKI_API_PORT=40100 \
//     yarn test:e2e ts/tests/e2e/readymcat_tooltips_shot.test.ts
// READYMCAT_SEED_DEMO makes the launcher auto-seed SYNTHETIC data so every stat
// clears its give-up threshold and the confidence/FSRS-recall terms render.

import type { Locator, Page } from "@playwright/test";
import { mkdirSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { expect, test } from "./fixtures";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const taxonomy = resolve(repoRoot, "taxonomy.json");
const outDir = resolve(repoRoot, "readymcat");
const dashboardUrl = `/readymcat-dashboard?taxonomy=${encodeURIComponent(taxonomy)}`;
const homeUrl = `/readymcat-home?taxonomy=${encodeURIComponent(taxonomy)}`;
const capture = process.env.READYMCAT_TOOLTIP_CAPTURE === "1";

const tooltip = (page: Page): Locator => page.locator("[role='tooltip']");

test.use({ viewport: { width: 900, height: 860 } });
test.setTimeout(120_000);

// Reload until the seeded dashboard has populated (a real range, not the
// ".muted" give-up text), so the confidence and FSRS-recall terms exist.
async function waitForPopulatedDashboard(page: Page): Promise<void> {
    for (let i = 0; i < 20; i++) {
        await page.goto(dashboardUrl);
        await page.locator(".dashboard .card").first().waitFor({
            state: "visible",
            timeout: 30_000,
        });
        await page.waitForTimeout(500);
        if ((await page.locator(".stat .stat-range:not(.muted)").count()) > 0) {
            break;
        }
    }
    await expect(page.locator(".stat .stat-range:not(.muted)").first()).toBeVisible({
        timeout: 10_000,
    });
    await page.waitForTimeout(400);
}

(capture ? test : test.skip)("dashboard term tooltips open on hover AND click", async ({
    page,
}) => {
    mkdirSync(outDir, { recursive: true });
    await waitForPopulatedDashboard(page);

    // Every headline stat label is now an info trigger.
    await expect(page.locator(".stat .eyebrow button.rmcat-tip")).toHaveCount(3);

    // --- HOVER: the Memory statistic label -------------------------------
    const memoryTrigger = page.locator(".stat .eyebrow button.rmcat-tip").first();
    await memoryTrigger.hover();
    await expect(tooltip(page)).toBeVisible();
    await expect(tooltip(page)).toContainText(/recall a card/i);
    await expect(memoryTrigger).toHaveAttribute("aria-expanded", "true");
    await page.screenshot({
        path: resolve(outDir, "readymcat-tooltip-dashboard-hover.png"),
    });

    // Move the pointer off so the hover popover closes before the next shot.
    await page.mouse.move(5, 5);
    await expect(tooltip(page)).toHaveCount(0);

    // --- CLICK/TAP: the app-native "FSRS recall" term --------------------
    const fsrsTrigger = page.getByRole("button", { name: /FSRS recall/i });
    await fsrsTrigger.click();
    await expect(tooltip(page)).toBeVisible();
    await expect(tooltip(page)).toContainText(/Free Spaced Repetition Scheduler/i);
    await expect(fsrsTrigger).toHaveAttribute("aria-expanded", "true");

    // The popover must be portaled to <body> and fully opaque on top, so it is
    // never clipped or out-stacked by the card it explains.
    const style = await page.evaluate(() => {
        const el = document.querySelector("[role='tooltip']") as HTMLElement | null;
        if (!el) {
            return null;
        }
        const cs = getComputedStyle(el);
        return { parent: el.parentElement?.tagName, opacity: cs.opacity };
    });
    expect(style?.parent).toBe("BODY");
    expect(Number(style?.opacity)).toBeGreaterThan(0.99);
    // Pinned by click: it survives the pointer leaving the trigger.
    await page.mouse.move(5, 5);
    await expect(tooltip(page)).toBeVisible();
    await page.screenshot({
        path: resolve(outDir, "readymcat-tooltip-dashboard-click.png"),
    });

    // Escape dismisses it.
    await page.keyboard.press("Escape");
    await expect(tooltip(page)).toHaveCount(0);
});

(capture ? test : test.skip)("home hub score pills expose info tooltips", async ({
    page,
}) => {
    mkdirSync(outDir, { recursive: true });
    await page.goto(homeUrl);
    await page.locator(".hub .statusbar").waitFor({ state: "visible", timeout: 30_000 });

    const memoryPill = page
        .locator(".pill button.rmcat-tip")
        .filter({ hasText: "Memory" });
    await expect(memoryPill).toHaveCount(1);
    await memoryPill.click();
    await expect(tooltip(page)).toBeVisible();
    await expect(tooltip(page)).toContainText(/recall a card/i);
    await page.screenshot({
        path: resolve(outDir, "readymcat-tooltip-home-pill.png"),
    });
    await page.keyboard.press("Escape");
    await expect(tooltip(page)).toHaveCount(0);
});
