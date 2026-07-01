// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { pointsAtStakeQueue } from "@generated/backend";

import type { PageLoad } from "./$types";
import type { HomeStatus } from "./types";

async function fetchHomeStatus(): Promise<HomeStatus> {
    const res = await fetch("/_anki/readymcatHomeStatus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
    });
    if (!res.ok) {
        throw new Error(await res.text());
    }
    return (await res.json()) as HomeStatus;
}

export const load = (async ({ url }) => {
    // The Qt layer may pass an explicit taxonomy.json path; otherwise the
    // backend looks next to the collection (matches readymcat-dashboard).
    const taxonomyPath = url.searchParams.get("taxonomy") ?? "";

    const [pointsResult, statusResult] = await Promise.allSettled([
        pointsAtStakeQueue({ taxonomyPath, deckId: 0n, limit: 50 }),
        fetchHomeStatus(),
    ]);

    return {
        points: pointsResult.status === "fulfilled" ? pointsResult.value : null,
        pointsError: pointsResult.status === "rejected" ? String(pointsResult.reason) : null,
        status: statusResult.status === "fulfilled" ? statusResult.value : null,
        statusError: statusResult.status === "rejected" ? String(statusResult.reason) : null,
        generatedAt: Date.now(),
    };
}) satisfies PageLoad;
