// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { pointsAtStakeQueue } from "@generated/backend";

import type { PageLoad } from "./$types";
import type { HomeStatus } from "./types";

/** An "available: false" status the hub treats as "not ready yet": it renders
 * the graceful "updating…" loading state and keeps polling until the real
 * counts come back. Used whenever the endpoint can't be read/parsed. */
function unavailableStatus(reason: string): HomeStatus {
    return { available: false, reason };
}

export async function fetchHomeStatus(): Promise<HomeStatus> {
    // NEVER throws. During a sync Anki locks/closes the collection, so this
    // endpoint can briefly reply with an empty body (HTTP 204 while the sync
    // holds the collection) or a non-OK status (e.g. 404 when mw.col is None).
    // Calling res.json() on an empty body throws
    // "SyntaxError: Unexpected end of JSON input", which used to surface to the
    // user as a raw "Couldn't load your ReadyMCAT counts" error. Instead we
    // return an honest "not available yet" status so the hub shows its
    // "updating…" state and recovers on the next poll.
    try {
        // mediasrv rejects any /_anki POST whose Content-Type isn't
        // "application/binary" with a 403 — and pops a warning dialog in the
        // desktop app (see qt/aqt/mediasrv.py::_check_dynamic_request_permissions).
        // The Python handler ignores the request body, so an empty one is fine.
        const res = await fetch("/_anki/readymcatHomeStatus", {
            method: "POST",
            headers: { "Content-Type": "application/binary" },
            body: "",
        });
        if (!res.ok) {
            return unavailableStatus(`http ${res.status}`);
        }
        // Read as text first so an empty body doesn't throw in .json().
        const text = await res.text();
        if (!text.trim()) {
            return unavailableStatus("empty response");
        }
        return JSON.parse(text) as HomeStatus;
    } catch (err) {
        // Network hiccup mid-sync or a malformed body: degrade to the loading
        // state rather than surfacing a raw error to the user.
        return unavailableStatus(String(err));
    }
}

export const load = (async ({ url }) => {
    // The Qt layer may pass an explicit taxonomy.json path; otherwise the
    // backend looks next to the collection (matches readymcat-dashboard).
    const taxonomyPath = url.searchParams.get("taxonomy") ?? "";

    // Fetch the two collection-reading endpoints SEQUENTIALLY, never at the same
    // time. Both pointsAtStakeQueue and readymcatHomeStatus are wrapped
    // server-side in a NON-BLOCKING sync-lock guard (see
    // qt/aqt/mediasrv.py::_sync_guarded): whichever runs while the other already
    // holds the lock is served an "unavailable"/"syncing" fallback instead of
    // reading the collection. Fired concurrently (the previous
    // Promise.allSettled), the lighter readymcatHomeStatus reliably lost the lock
    // race to the heavy pointsAtStakeQueue and came back
    // { available: false, reason: "syncing" } — which parked the hub in its
    // "updating…" state with every format tile disabled ("NOT LOADED YET"/
    // "SETTING UP…") even though all four decks are fully present. Awaiting them
    // one at a time lets each take the lock cleanly, so the launch tiles reflect
    // the real deck counts on first paint; the settingUp/poll fallback in
    // +page.svelte is then reserved for a genuinely still-importing bank.
    let points: Awaited<ReturnType<typeof pointsAtStakeQueue>> | null = null;
    let pointsError: string | null = null;
    try {
        points = await pointsAtStakeQueue({ taxonomyPath, deckId: 0n, limit: 50 });
    } catch (reason) {
        pointsError = String(reason);
    }

    // fetchHomeStatus never rejects — on any failure (incl. the "syncing"
    // fallback) it returns an { available: false } status — so there is no
    // separate "status error" to surface. The hub renders its graceful
    // "updating…" loading state from an unavailable status and recovers on the
    // next poll.
    const status = await fetchHomeStatus();

    return {
        points,
        pointsError,
        status,
        generatedAt: Date.now(),
    };
}) satisfies PageLoad;
