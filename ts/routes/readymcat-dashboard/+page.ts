// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { pointsAtStakeQueue } from "@generated/backend";

import type { PageLoad } from "./$types";

export const load = (async ({ url }) => {
    // The Qt layer may pass an explicit taxonomy.json path; otherwise the
    // backend looks next to the collection.
    const taxonomyPath = url.searchParams.get("taxonomy") ?? "";
    try {
        const data = await pointsAtStakeQueue({
            taxonomyPath,
            deckId: 0n,
            limit: 50,
        });
        // When the aggregation was computed, so the dashboard can show an
        // honest "last updated" timestamp.
        return { data, error: null as string | null, generatedAt: Date.now() };
    } catch (err) {
        return { data: null, error: String(err), generatedAt: Date.now() };
    }
}) satisfies PageLoad;
