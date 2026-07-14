<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

Shared interactive "topic mastery" grid — the signature ReadyMCAT visualization,
used by both the honest dashboard and the home hub. Each AAMC content category is
a radial ring that FILLS to the student's recall (FSRS mean retrievability) on
load, colour-banded by strength, sortable, and click-to-expand for the topic's
details. Replaces the old dense per-topic table + study-next + reasons stack.
-->
<script lang="ts" context="module">
    export interface MasteryTopic {
        category: string;
        name: string;
        topicWeight: number;
        studentWeakness: number;
        gradedCards: number;
        totalCards: number;
        meanRetrievability: number;
        accuracy?: number | null;
        attempts?: number;
        hits?: number;
    }
</script>

<script lang="ts">
    import { onMount } from "svelte";

    import { pct } from "$lib/readymcat/scores";

    export let topics: MasteryTopic[] = [];
    /** Tighter sizing + no legend, for the home hub's secondary column. */
    export let compact = false;
    /** Cap the number of rings shown (0 = all). */
    export let limit = 0;
    /** Set (to a fresh object) by the "Study next" card's "start with <topic>"
     * pointer to focus a category: sorts by Focus, pins the topic into view even
     * under `limit`, and expands its ring. A new object identity each request so
     * re-clicking the same topic re-focuses it. */
    export let focusRequest: { category: string } | null = null;

    type SortKey = "focus" | "mastery" | "weight" | "name";
    let sort: SortKey = "focus";
    let expanded: string | null = null;
    /** Category force-included in `shown` (so a focused topic can't be hidden by
     * `limit`); driven by `focusRequest`. */
    let pinnedCategory: string | null = null;

    // Respond to a focus request from the study-next pointer.
    $: if (focusRequest) {
        sort = "focus";
        pinnedCategory = focusRequest.category;
        expanded = focusRequest.category;
    }

    // Rings start empty and animate to their value once mounted — the "filling
    // up with mastery" the design calls for. requestAnimationFrame so the 0→value
    // transition actually plays instead of snapping.
    let filled = false;
    onMount(() => requestAnimationFrame(() => (filled = true)));

    const R = 26;
    const STROKE = 6;
    const CIRC = 2 * Math.PI * R;

    const points = (t: MasteryTopic): number => t.topicWeight * t.studentWeakness;
    const hasData = (t: MasteryTopic): boolean => t.gradedCards > 0;

    function band(t: MasteryTopic): "strong" | "medium" | "weak" | "none" {
        if (!hasData(t)) {
            return "none";
        }
        if (t.meanRetrievability >= 0.8) {
            return "strong";
        }
        if (t.meanRetrievability >= 0.6) {
            return "medium";
        }
        return "weak";
    }

    const sorters: Record<SortKey, (a: MasteryTopic, b: MasteryTopic) => number> = {
        // Focus = most points at stake (exam weight × weakness): what to study now.
        focus: (a, b) => points(b) - points(a),
        mastery: (a, b) => b.meanRetrievability - a.meanRetrievability,
        weight: (a, b) => b.topicWeight - a.topicWeight,
        name: (a, b) => a.category.localeCompare(b.category),
    };
    const sortOptions: Array<{ key: SortKey; label: string }> = [
        { key: "focus", label: "Focus" },
        { key: "mastery", label: "Mastery" },
        { key: "weight", label: "Exam weight" },
        { key: "name", label: "A–Z" },
    ];

    $: shown = (() => {
        const arr = [...topics].sort(sorters[sort]);
        let capped = limit > 0 ? arr.slice(0, limit) : arr;
        // Keep a focused (pinned) topic visible even when `limit` would drop it.
        if (pinnedCategory && !capped.some((t) => t.category === pinnedCategory)) {
            const pin = arr.find((t) => t.category === pinnedCategory);
            if (pin) {
                capped = [pin, ...capped.slice(0, Math.max(0, capped.length - 1))];
            }
        }
        return capped;
    })();

    // Overall mastery = card-weighted mean recall across studied topics (honest:
    // only topics with evidence count; null when nothing's been studied yet).
    $: studied = topics.filter(hasData);
    $: overall = (() => {
        const cards = studied.reduce((n, t) => n + t.gradedCards, 0);
        if (cards === 0) {
            return null;
        }
        return (
            studied.reduce((s, t) => s + t.meanRetrievability * t.gradedCards, 0) /
            cards
        );
    })();

    function toggle(cat: string): void {
        expanded = expanded === cat ? null : cat;
    }
    function onKey(e: KeyboardEvent, cat: string): void {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle(cat);
        }
    }

    // dashoffset for a ring: full circumference (empty) until `filled`, then the
    // remainder after filling to `value`.
    const offset = (value: number, on: boolean): number =>
        on ? CIRC * (1 - Math.max(0, Math.min(1, value))) : CIRC;
</script>

<div class="tm" class:compact>
    <div class="tm-bar">
        <div class="tm-title">
            <h3>Topic mastery</h3>
            {#if overall !== null}
                <span class="tm-overall">
                    avg <b>{pct(overall)}</b>
                    recall
                </span>
            {:else}
                <span class="tm-overall muted">not studied yet</span>
            {/if}
        </div>
        <div class="tm-sort" role="group" aria-label="Sort topics">
            {#each sortOptions as opt (opt.key)}
                <button
                    type="button"
                    class="tm-sortbtn"
                    class:active={sort === opt.key}
                    on:click={() => (sort = opt.key)}
                >
                    {opt.label}
                </button>
            {/each}
        </div>
    </div>

    {#if shown.length === 0}
        <p class="tm-empty">No topics to show yet.</p>
    {:else}
        <div class="tm-grid">
            {#each shown as t, i (t.category)}
                {@const b = band(t)}
                {@const open = expanded === t.category}
                <div class="tm-cell b-{b}" class:open>
                    <button
                        type="button"
                        class="tm-ringbtn"
                        aria-expanded={open}
                        on:click={() => toggle(t.category)}
                        on:keydown={(e) => onKey(e, t.category)}
                        title={`${t.category} · ${t.name}`}
                    >
                        <span class="tm-ring">
                            <svg viewBox="0 0 64 64" aria-hidden="true">
                                <circle
                                    class="tm-track"
                                    cx="32"
                                    cy="32"
                                    r={R}
                                    stroke-width={STROKE}
                                />
                                <circle
                                    class="tm-fill"
                                    cx="32"
                                    cy="32"
                                    r={R}
                                    stroke-width={STROKE}
                                    stroke-dasharray={CIRC}
                                    stroke-dashoffset={offset(
                                        t.meanRetrievability,
                                        filled,
                                    )}
                                    style:transition-delay={`${Math.min(i, 12) * 55}ms`}
                                />
                            </svg>
                            <span class="tm-pct">
                                {#if hasData(t)}
                                    {Math.round(t.meanRetrievability * 100)}
                                    <i>%</i>
                                {:else}
                                    <i class="tm-dash">–</i>
                                {/if}
                            </span>
                        </span>
                        <span class="tm-label">
                            <span class="tm-cat">{t.category}</span>
                            <span class="tm-name">{t.name}</span>
                        </span>
                    </button>

                    {#if open}
                        <div class="tm-detail">
                            <div class="tm-drow">
                                <span>Recall</span>
                                <b>
                                    {hasData(t) ? pct(t.meanRetrievability) : "no data"}
                                </b>
                            </div>
                            <div class="tm-drow">
                                <span>Exam weight</span>
                                <b>{t.topicWeight.toFixed(1)}</b>
                            </div>
                            <div class="tm-drow">
                                <span>Cards studied</span>
                                <b>{t.gradedCards}/{t.totalCards}</b>
                            </div>
                            <div class="tm-drow">
                                <span>First-try accuracy</span>
                                <b>
                                    {#if t.attempts && t.attempts > 0}
                                        {pct(t.accuracy ?? 0)}
                                        <em>({t.hits}/{t.attempts})</em>
                                    {:else}
                                        —
                                    {/if}
                                </b>
                            </div>
                            <div class="tm-weakness">
                                <div class="tm-wtop">
                                    <span>Points at stake</span>
                                    <span>{points(t).toFixed(1)}</span>
                                </div>
                                <div class="tm-wbar">
                                    <div
                                        class="tm-wfill"
                                        style:width={pct(t.studentWeakness)}
                                    ></div>
                                </div>
                            </div>
                        </div>
                    {/if}
                </div>
            {/each}
        </div>
    {/if}

    {#if !compact}
        <div class="tm-legend" aria-hidden="true">
            <span class="lg s">
                <i></i>
                Strong ≥80%
            </span>
            <span class="lg m">
                <i></i>
                Building 60–79%
            </span>
            <span class="lg w">
                <i></i>
                Weak &lt;60%
            </span>
            <span class="lg n">
                <i></i>
                Not studied
            </span>
        </div>
    {/if}
</div>

<style lang="scss">
    .tm {
        --strong: #10b981;
        --medium: #f59e0b;
        --weak: #f43f5e;
        --none: var(--fg-faint, #9aa4b2);
    }

    .tm-bar {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 0.75rem;
        flex-wrap: wrap;
        margin-bottom: 0.9rem;
    }

    .tm-title {
        display: flex;
        align-items: baseline;
        gap: 0.6rem;
    }

    .tm-title h3 {
        margin: 0;
        font-size: 15px;
        font-weight: 800;
        letter-spacing: -0.01em;
    }

    .tm-overall {
        font-size: 12px;
        color: var(--fg-subtle);
    }
    .tm-overall b {
        color: var(--fg);
        font-weight: 800;
    }
    .tm-overall.muted {
        color: var(--fg-faint);
    }

    // segmented sort control
    .tm-sort {
        display: inline-flex;
        background: var(--canvas-inset);
        border: 1px solid var(--border-subtle);
        border-radius: 999px;
        padding: 2px;
        gap: 2px;
    }

    .tm-sortbtn {
        font: inherit;
        font-size: 11.5px;
        font-weight: 700;
        color: var(--fg-subtle);
        background: none;
        border: none;
        padding: 4px 10px;
        border-radius: 999px;
        cursor: pointer;
        white-space: nowrap;
    }
    .tm-sortbtn:hover {
        color: var(--fg);
    }
    .tm-sortbtn.active {
        background: var(--canvas-elevated);
        color: var(--fg);
        box-shadow: 0 1px 2px color-mix(in srgb, var(--shadow-subtle) 50%, transparent);
    }

    .tm-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 0.6rem;
    }

    .compact .tm-grid {
        grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
        gap: 0.5rem;
    }

    .tm-cell {
        background: var(--canvas-inset);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        overflow: hidden;
        transition:
            border-color 0.15s ease,
            transform 0.15s ease;
    }

    .tm-cell:hover {
        transform: translateY(-1px);
        border-color: color-mix(
            in srgb,
            var(--band, var(--none)) 55%,
            var(--border-subtle)
        );
    }

    .tm-cell.open {
        border-color: color-mix(
            in srgb,
            var(--band, var(--none)) 70%,
            var(--border-subtle)
        );
        grid-column: span 2;
    }

    .compact .tm-cell.open {
        grid-column: auto;
    }

    // per-band accent, consumed by hover/open border + the ring stroke
    .b-strong {
        --band: var(--strong);
    }
    .b-medium {
        --band: var(--medium);
    }
    .b-weak {
        --band: var(--weak);
    }
    .b-none {
        --band: var(--none);
    }

    .tm-ringbtn {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.6rem 0.7rem;
        background: none;
        border: none;
        cursor: pointer;
        text-align: left;
        font: inherit;
        color: inherit;
    }

    .tm-ring {
        position: relative;
        width: 52px;
        height: 52px;
        flex-shrink: 0;
    }

    .tm-ring svg {
        width: 100%;
        height: 100%;
        transform: rotate(-90deg); // start the fill at 12 o'clock
    }

    .tm-track {
        fill: none;
        stroke: color-mix(in srgb, var(--fg-faint, #9aa4b2) 22%, transparent);
    }

    .tm-fill {
        fill: none;
        stroke: var(--band, var(--none));
        stroke-linecap: round;
        transition: stroke-dashoffset 0.9s cubic-bezier(0.22, 1, 0.36, 1);
    }

    .b-none .tm-fill {
        // unstudied: leave the ring hollow (no fill drawn)
        stroke: transparent;
    }

    .tm-pct {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 800;
        font-variant-numeric: tabular-nums;
        color: var(--fg);
    }
    .tm-pct i {
        font-style: normal;
        font-size: 9px;
        font-weight: 700;
        color: var(--fg-subtle);
        margin-left: 1px;
    }
    .tm-dash {
        color: var(--fg-faint);
        font-size: 16px;
    }

    .tm-label {
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 1px;
    }

    .tm-cat {
        font-size: 10.5px;
        font-weight: 800;
        letter-spacing: 0.02em;
        color: var(--band, var(--fg-subtle));
    }

    .tm-name {
        font-size: 12px;
        font-weight: 600;
        color: var(--fg);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    // click-to-drill detail panel
    .tm-detail {
        padding: 0.15rem 0.75rem 0.7rem;
        display: grid;
        gap: 0.28rem;
    }

    .tm-drow {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        font-size: 11.5px;
        color: var(--fg-subtle);
    }
    .tm-drow b {
        color: var(--fg);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    .tm-drow em {
        font-style: normal;
        color: var(--fg-faint);
        font-size: 10.5px;
    }

    .tm-weakness {
        margin-top: 0.15rem;
    }
    .tm-wtop {
        display: flex;
        justify-content: space-between;
        font-size: 10.5px;
        color: var(--fg-faint);
        margin-bottom: 3px;
    }
    .tm-wbar {
        height: 6px;
        border-radius: 999px;
        background: color-mix(in srgb, var(--fg-faint, #9aa4b2) 20%, transparent);
        overflow: hidden;
    }
    .tm-wfill {
        height: 100%;
        border-radius: 999px;
        background: var(--band, var(--none));
        transition: width 0.5s ease;
    }

    .tm-empty {
        font-size: 12.5px;
        color: var(--fg-subtle);
        margin: 0.25rem 0;
    }

    .tm-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem 1rem;
        margin-top: 0.9rem;
        font-size: 11px;
        color: var(--fg-subtle);
    }
    .lg {
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }
    .lg i {
        width: 9px;
        height: 9px;
        border-radius: 3px;
        display: inline-block;
    }
    .lg.s i {
        background: var(--strong);
    }
    .lg.m i {
        background: var(--medium);
    }
    .lg.w i {
        background: var(--weak);
    }
    .lg.n i {
        background: var(--none);
    }

    @media (prefers-reduced-motion: reduce) {
        .tm-fill,
        .tm-wfill {
            transition: none;
        }
    }
</style>
