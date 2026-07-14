// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { afterEach, describe, expect, test, vi } from "vitest";

// +page.ts imports the generated protobuf client at module load; stub it so
// this unit test stays hermetic (it only exercises fetchHomeStatus).
vi.mock("@generated/backend", () => ({ pointsAtStakeQueue: vi.fn() }));

import { fetchHomeStatus } from "./+page";

// A faithful stand-in for a Fetch Response: json() throws on an empty body,
// exactly like the browser ("SyntaxError: Unexpected end of JSON input") — the
// original bug — so these tests prove fetchHomeStatus never lets that escape.
function fakeResponse(body: string, ok = true, status = 200): Response {
    return {
        ok,
        status,
        text: async () => body,
        json: async () => JSON.parse(body),
    } as unknown as Response;
}

function stubFetch(impl: () => Promise<Response>): void {
    vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => {
    vi.unstubAllGlobals();
});

describe("fetchHomeStatus mid-sync robustness", () => {
    test("parses a well-formed JSON body", async () => {
        stubFetch(async () =>
            fakeResponse(
                JSON.stringify({
                    available: true,
                    decks: { mcq: { present: true, deckId: 1, due: 3, total: 9 } },
                }),
            )
        );
        const status = await fetchHomeStatus();
        expect(status.available).toBe(true);
        expect(status.decks?.mcq.total).toBe(9);
    });

    test("an empty 204 body (a sync holding the collection) never throws", async () => {
        // Before the fix this hit res.json() on "" and threw
        // "Unexpected end of JSON input"; now it degrades to "not available".
        stubFetch(async () => fakeResponse("", true, 204));
        const status = await fetchHomeStatus();
        expect(status.available).toBe(false);
        expect(status.reason).toBeTruthy();
    });

    test("a non-OK response (mw.col is None → 404) never throws", async () => {
        stubFetch(async () => fakeResponse("collection not open", false, 404));
        const status = await fetchHomeStatus();
        expect(status.available).toBe(false);
        expect(status.reason).toContain("404");
    });

    test("a malformed body never surfaces a raw SyntaxError", async () => {
        stubFetch(async () => fakeResponse("<html>not json</html>"));
        const status = await fetchHomeStatus();
        expect(status.available).toBe(false);
        expect(status.reason).toBeTruthy();
    });

    test("a network failure degrades to an unavailable status", async () => {
        stubFetch(async () => {
            throw new TypeError("Failed to fetch");
        });
        const status = await fetchHomeStatus();
        expect(status.available).toBe(false);
        expect(status.reason).toBeTruthy();
    });
});
