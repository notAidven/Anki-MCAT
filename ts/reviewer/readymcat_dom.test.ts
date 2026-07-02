// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
// @vitest-environment jsdom

import { afterEach, describe, expect, test } from "vitest";

import { firstUrl, makeButton, qaEl, typeset } from "./readymcat_dom";

afterEach(() => {
    document.body.innerHTML = "";
});

describe("qaEl", () => {
    test("returns the reviewer #qa container", () => {
        const qa = document.createElement("div");
        qa.id = "qa";
        document.body.appendChild(qa);
        expect(qaEl()).toBe(qa);
    });
});

describe("firstUrl", () => {
    test("returns the first http(s) link in the text", () => {
        expect(firstUrl("see https://example.com/x for more")).toBe("https://example.com/x");
        expect(firstUrl("a http://a.test and https://b.test")).toBe("http://a.test");
    });

    test("stops at quotes, angle brackets, whitespace and a closing paren", () => {
        expect(firstUrl("(https://example.com/page)")).toBe("https://example.com/page");
        expect(firstUrl("<a href=\"https://example.com/z\">")).toBe("https://example.com/z");
    });

    test("returns null when there is no link", () => {
        expect(firstUrl("no link here")).toBeNull();
        expect(firstUrl("")).toBeNull();
    });
});

describe("makeButton", () => {
    test("uses the overlay prefix and variant class, and is a type=button", () => {
        const button = makeButton("rmcq", "Submit", "primary", () => undefined);
        expect(button.className).toBe("rmcq-btn primary");
        expect(button.type).toBe("button");
        expect(button.textContent).toBe("Submit");
    });

    test("invokes the click handler", () => {
        let clicks = 0;
        const button = makeButton("rmpsg", "Go", "good", () => {
            clicks += 1;
        });
        button.click();
        button.click();
        expect(clicks).toBe(2);
    });
});

describe("typeset", () => {
    test("is a no-op that resolves when MathJax is unavailable", async () => {
        const el = document.createElement("div");
        await expect(typeset(el)).resolves.toBeUndefined();
    });
});
