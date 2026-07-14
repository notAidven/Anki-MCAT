// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { _teachOnMissStart } from "./teach_on_miss";

// The teach-on-miss overlay now runs ONLY the guiding ladder. When the ladder
// finishes it must hand control back to Python via `tom:reshow` — which
// re-displays the REAL card through the reviewer's native render path — instead
// of reconstructing the flashcard in the overlay (a reconstruction never
// matched Anki's native design). These headless checks lock that contract: the
// overlay never rebuilds the card, and completing the ladder posts `tom:reshow`.

interface Overrides {
    ladder?: unknown[];
}

function makePayload(overrides: Overrides = {}) {
    return {
        title: "Glycolysis",
        category: "1D",
        ladder: overrides.ladder ?? [],
    };
}

let bridge: ReturnType<typeof vi.fn>;

beforeEach(() => {
    document.body.innerHTML = "<div id=\"qa\"></div>";
    document.body.className = "";
    bridge = vi.fn();
    window.bridgeCommand = bridge as unknown as typeof window.bridgeCommand;
});

afterEach(() => {
    document.body.innerHTML = "";
    document.body.className = "";
    vi.restoreAllMocks();
});

function qa(): HTMLElement {
    const el = document.getElementById("qa");
    if (!el) {
        throw new Error("#qa missing");
    }
    return el;
}

function clickButton(label: string): void {
    const button = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
        .find((b) => b.textContent === label);
    if (!button) {
        throw new Error(`button "${label}" not found`);
    }
    button.click();
}

function bridgeCalls(): string[] {
    return bridge.mock.calls.map((call) => String(call[0]));
}

describe("teach-on-miss overlay (guiding ladder only)", () => {
    test("hands back to Python for the native card re-show when the ladder ends", () => {
        _teachOnMissStart(makePayload({ ladder: [] }));

        // It asks Python to re-render the real card through the normal reviewer
        // path, and does NOT reconstruct the card itself: no overlay card box,
        // no injected card <style>, #qa left untouched for the native render.
        expect(bridgeCalls()).toContain("tom:reshow");
        expect(qa().querySelector(".tom-main")).toBeNull();
        expect(qa().querySelector(".tom-regrade")).toBeNull();
        expect(qa().querySelector("style")).toBeNull();
        expect(qa().children.length).toBe(0);
    });

    test("runs a guiding MCQ rung, reports the mark, then hands back", () => {
        _teachOnMissStart(
            makePayload({
                ladder: [
                    {
                        question: "Which enzyme phosphorylates fructose-6-phosphate?",
                        options: ["PFK-1", "Amylase", "Lipase"],
                        correctIndex: 0,
                        explanation: "PFK-1 catalyses that committed step.",
                    },
                ],
            }),
        );

        // The rung renders in the overlay.
        const stem = qa().querySelector(".tom-q");
        expect(stem?.textContent).toContain("phosphorylates fructose-6-phosphate");

        // Choose the correct option and check -> the mark is reported to Python.
        const options = Array.from(qa().querySelectorAll<HTMLButtonElement>(".tom-option"));
        expect(options).toHaveLength(3);
        options[0].click();
        clickButton("Check");
        expect(bridgeCalls()).toContain("tom:mark:got:0");

        // Advancing past the last rung hands back for the native re-show; the
        // overlay never reconstructs the card.
        clickButton("Back to the question");
        expect(bridgeCalls()).toContain("tom:reshow");
        expect(qa().querySelector(".tom-main")).toBeNull();
    });

    test("renders untrusted AI ladder text as inert plain text (no HTML injection)", () => {
        // AI-generated ladder strings are untrusted (a crafted imported card can
        // steer the model into emitting active markup). They must render as text,
        // so an <img onerror> payload never becomes a live element that fires in
        // the reviewer webview where bridgeCommand/pycmd is reachable.
        const evil = "<img src=x onerror=\"window.__xss=1\">";
        _teachOnMissStart(
            makePayload({
                ladder: [
                    {
                        question: `Stem ${evil}`,
                        options: [`Option ${evil}`, "Safe choice"],
                        correctIndex: 0,
                        explanation: `Because ${evil}`,
                    },
                ],
            }),
        );

        // The stem shows the payload as literal text, with no live <img> node.
        const stem = qa().querySelector(".tom-q");
        expect(stem?.textContent).toContain(evil);
        expect(stem?.querySelector("img")).toBeNull();

        // Option text is inert too.
        const optText = qa().querySelector(".tom-opt-text");
        expect(optText?.textContent).toContain(evil);
        expect(qa().querySelector(".tom-options img")).toBeNull();

        // Reveal the explanation and confirm it is inert text as well.
        Array.from(qa().querySelectorAll<HTMLButtonElement>(".tom-option"))[0].click();
        clickButton("Check");
        const explanation = qa().querySelector(".tom-explanation .tom-a");
        expect(explanation?.textContent).toContain(evil);
        expect(explanation?.querySelector("img")).toBeNull();

        // Belt and suspenders: no injected element anywhere in the overlay.
        expect(qa().querySelector("img")).toBeNull();
    });
});
