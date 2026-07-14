<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import { bridgeCommand } from "@tslib/bridgecommand";
    import { onDestroy, onMount } from "svelte";

    import type { PageData } from "./$types";
    import { fetchHomeStatus } from "./+page";
    import Home from "./Home.svelte";
    import type { HomeStatus } from "./types";

    export let data: PageData;

    function bankReady(s: HomeStatus | null): boolean {
        if (!s || !s.available || !s.decks) {
            return false;
        }
        return Object.values(s.decks).some((d) => d?.present);
    }

    // The hub shows an "updating…" state (settingUp) and polls whenever the
    // question bank isn't ready yet. Two cases reach this:
    //   1. A brand-new profile whose bundled bank is still importing (every
    //      deck comes back `present: false`).
    //   2. A sync in progress: Anki locks/closes the collection, so the status
    //      endpoint answers with an { available: false, reason: "syncing" }
    //      status (see qt/aqt/mediasrv.py). fetchHomeStatus never throws, so a
    //      mid-sync fetch never surfaces a raw SyntaxError — it just looks
    //      "not ready", and we poll until the real counts return.
    let status: HomeStatus | null = data.status;
    // Start in the loading state (no first-render flash) when the bank isn't
    // ready; a later successful poll clears it.
    let settingUp = !bankReady(data.status);
    let timer: ReturnType<typeof setTimeout> | undefined;
    let tries = 0;
    const POLL_MS = 1500;
    const MAX_TRIES = 25; // ~37s — long enough for a first-launch bank import
    // A full-hub reload (bridgeCommand("refresh")) is how the points/scores
    // panels pick up a freshly-restored/provisioned collection. But the
    // reloaded page re-runs its own status fetch, which can momentarily race the
    // desktop's home re-provision and answer "not ready" — which would poll,
    // see ready, and reload again, forever (the ~1.6s refresh loop). Bound the
    // reload to ONCE per app session: after that we simply render the polled
    // `status` reactively (Home repaints its tiles from it), so the loop can't
    // happen. sessionStorage survives the reload; a module `let` would not.
    const REFRESH_ONCE_KEY = "readymcat:home:refreshed";

    function alreadyRefreshed(): boolean {
        try {
            return sessionStorage.getItem(REFRESH_ONCE_KEY) === "1";
        } catch {
            return false;
        }
    }

    function markRefreshed(): void {
        try {
            sessionStorage.setItem(REFRESH_ONCE_KEY, "1");
        } catch {
            // sessionStorage unavailable: the reactive `status` update still
            // repaints the tiles, so this is non-fatal.
        }
    }

    async function poll(): Promise<void> {
        tries += 1;
        try {
            const next = await fetchHomeStatus();
            status = next;
            if (bankReady(next)) {
                settingUp = false;
                // Reload the whole hub once so the scores/points panels (which
                // depend on the now-placed taxonomy.json / restored collection)
                // refresh alongside the tiles. Never more than once, so a
                // reloaded page that still races the provision can't loop. The
                // reactive `status` above already shows the tiles either way;
                // this bridge is desktop-only.
                if (!alreadyRefreshed()) {
                    markRefreshed();
                    bridgeCommand("refresh");
                }
                return;
            }
        } catch {
            // Defensive: fetchHomeStatus already swallows failures into an
            // "unavailable" status, but never let a poll error break the loop —
            // keep polling rather than surfacing an error.
        }
        if (tries < MAX_TRIES) {
            timer = setTimeout(poll, POLL_MS);
        } else {
            // Give up after the bounded window: fall back to the normal
            // "no content loaded" guidance rather than spinning forever.
            settingUp = false;
        }
    }

    onMount(() => {
        if (!bankReady(data.status)) {
            settingUp = true;
            timer = setTimeout(poll, POLL_MS);
        }
    });

    onDestroy(() => {
        if (timer) {
            clearTimeout(timer);
        }
    });
</script>

<Home
    points={data.points}
    pointsError={data.pointsError}
    {status}
    {settingUp}
    generatedAt={data.generatedAt}
/>
