// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
// @vitest-environment jsdom

import { flushSync, mount, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { glossary } from "./glossary";
import InfoTooltip from "./InfoTooltip.svelte";

// Headless confirmation that the reusable info affordance renders and opens on
// hover AND click AND keyboard focus, and dismisses on mouse-leave / blur /
// Escape, with the accessibility wiring the dashboard relies on.

let host: HTMLDivElement;
let instance: ReturnType<typeof mount> | undefined;

beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
});

afterEach(() => {
    if (instance) {
        unmount(instance);
        instance = undefined;
    }
    host.remove();
    document.body.innerHTML = "";
});

function render(props: { entry: typeof glossary.memory; variant?: "text" | "icon" }): void {
    instance = mount(InfoTooltip, { target: host, props });
    flushSync();
}

function button(): HTMLButtonElement {
    const el = host.querySelector<HTMLButtonElement>("button.rmcat-tip");
    if (!el) {
        throw new Error("trigger button not rendered");
    }
    return el;
}

function popover(): HTMLElement | null {
    // The popover is portaled to <body>, so query the whole document.
    return document.querySelector<HTMLElement>("[role='tooltip']");
}

function fire(el: Element, event: Event): void {
    el.dispatchEvent(event);
    flushSync();
}

describe("InfoTooltip", () => {
    test("renders a focusable trigger and stays closed until interaction", () => {
        render({ entry: glossary.memory });
        const btn = button();
        expect(btn.tagName).toBe("BUTTON");
        expect(btn.getAttribute("aria-expanded")).toBe("false");
        expect(btn.getAttribute("aria-describedby")).toBeNull();
        expect(popover()).toBeNull();
    });

    test("opens on hover and closes on mouse-leave", () => {
        render({ entry: glossary.memory });
        const btn = button();

        fire(btn, new MouseEvent("mouseenter", { bubbles: true }));
        const pop = popover();
        expect(pop).not.toBeNull();
        expect(btn.getAttribute("aria-expanded")).toBe("true");
        // aria-describedby must point at the visible tooltip.
        expect(btn.getAttribute("aria-describedby")).toBe(pop!.id);
        expect(pop!.textContent).toContain(glossary.memory.what);

        fire(btn, new MouseEvent("mouseleave", { bubbles: true }));
        expect(popover()).toBeNull();
        expect(btn.getAttribute("aria-expanded")).toBe("false");
    });

    test("opens on keyboard focus and closes on blur", () => {
        render({ entry: glossary.performance });
        const btn = button();

        btn.focus();
        flushSync();
        expect(popover()).not.toBeNull();

        btn.blur();
        flushSync();
        expect(popover()).toBeNull();
    });

    test("click pins it open (survives mouse-leave) and toggles closed", () => {
        render({ entry: glossary.readiness });
        const btn = button();

        fire(btn, new MouseEvent("click", { bubbles: true }));
        expect(popover()).not.toBeNull();

        // Pinned by click: leaving with the mouse must NOT dismiss it.
        fire(btn, new MouseEvent("mouseleave", { bubbles: true }));
        expect(popover()).not.toBeNull();

        // A second click toggles it back closed.
        fire(btn, new MouseEvent("click", { bubbles: true }));
        expect(popover()).toBeNull();
    });

    test("Escape dismisses an open popover", () => {
        render({ entry: glossary.coverage });
        const btn = button();

        btn.focus();
        flushSync();
        expect(popover()).not.toBeNull();

        fire(btn, new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        expect(popover()).toBeNull();
    });

    test("an outside pointer-down dismisses a pinned popover", () => {
        render({ entry: glossary.fsrs });
        const btn = button();

        fire(btn, new MouseEvent("click", { bubbles: true }));
        expect(popover()).not.toBeNull();

        // jsdom lacks PointerEvent; a MouseEvent of type "pointerdown" still
        // exercises the component's document-level pointerdown listener.
        fire(document.body, new MouseEvent("pointerdown", { bubbles: true }));
        expect(popover()).toBeNull();
    });

    test("icon variant is labelled and shows no inline text label", () => {
        render({ entry: glossary.confidence, variant: "icon" });
        const btn = button();
        expect(btn.classList.contains("as-icon")).toBe(true);
        expect(btn.getAttribute("aria-label")).toBe(`About ${glossary.confidence.title}`);
        expect(host.querySelector(".rmcat-tip-label")).toBeNull();
    });
});
