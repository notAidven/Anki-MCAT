<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PointsAtStakeResponse } from "@generated/anki/points_at_stake_pb";

    export let data: PointsAtStakeResponse | null;
    export let error: string | null;
    /** When the aggregation was computed (ms epoch); drives "last updated". */
    export let generatedAt: number = Date.now();

    // The give-up rule (mirrors the Rust thresholds): show no score until there
    // is enough evidence.
    const MIN_REVIEWS = 200;
    const MIN_COVERAGE = 0.5;

    const pct = (x: number): string => `${Math.round(x * 100)}%`;

    $: memory = data?.memory;
    $: coverage = data?.coverage;
    $: topics = data?.topics ?? [];

    $: mean = memory?.mean ?? 0;
    $: rangeLow = memory?.rangeLow ?? 0;
    $: rangeHigh = memory?.rangeHigh ?? 0;
    $: gradedReviews = memory?.gradedReviews ?? 0;
    $: gradedCards = memory?.gradedCards ?? 0;

    $: coverageFraction = coverage?.fraction ?? 0;
    $: weightedFraction = coverage?.weightedFraction ?? 0;
    $: categoriesCovered = coverage?.categoriesCovered ?? 0;
    $: categoriesTotal = coverage?.categoriesTotal ?? 0;

    $: reviewProgress = Math.min(1, gradedReviews / MIN_REVIEWS);
    $: coverageProgress = Math.min(1, coverageFraction / MIN_COVERAGE);

    // "How sure": the width of the reported 95% interval is the honest measure
    // of confidence — more evidence tightens it. Never invented, always derived.
    type ConfLevel = "high" | "moderate" | "low";
    function levelFor(margin: number): ConfLevel {
        if (margin <= 2.5) {
            return "high";
        }
        if (margin <= 6) {
            return "moderate";
        }
        return "low";
    }
    function labelFor(level: ConfLevel): string {
        if (level === "high") {
            return "High confidence";
        }
        if (level === "moderate") {
            return "Moderate confidence";
        }
        return "Low confidence";
    }
    $: marginPoints = ((rangeHigh - rangeLow) / 2) * 100;
    $: confidenceLevel = levelFor(marginPoints);
    $: confidenceLabel = labelFor(confidenceLevel);

    // "What to study next": topics with the most points at stake.
    $: studyNext = topics
        .filter((t) => t.totalCards > 0)
        .map((t) => ({ ...t, points: t.topicWeight * t.studentWeakness }))
        .sort((a, b) => b.points - a.points)
        .slice(0, 5);

    $: topicsByWeight = [...topics].sort((a, b) => b.topicWeight - a.topicWeight);
    $: withData = topics.filter((t) => t.gradedCards > 0);
    $: noDataCount = topics.length - withData.length;
    $: strongest = [...withData]
        .sort((a, b) => b.meanRetrievability - a.meanRetrievability)
        .slice(0, 3);
    $: rankedCount = data?.rankedCards.length ?? 0;

    // Drivers behind the number, by category code (full names live in the
    // "what to study next" list right above).
    $: weakCodes = studyNext
        .slice(0, 3)
        .map((t) => t.category)
        .join(", ");
    $: strongCodes = strongest.map((t) => t.category).join(", ");

    $: updatedLabel = new Date(generatedAt || Date.now()).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    });
</script>

<div class="dashboard">
    <header class="masthead">
        <div class="titles">
            <h1>ReadyMCAT — Honest Memory</h1>
            <p class="subtitle">
                Recall probability from FSRS, aggregated per AAMC topic — shown as a
                range, never a bare number.
            </p>
        </div>
        <div class="updated" title="When this aggregation was computed">
            Updated {updatedLabel}
        </div>
    </header>

    {#if error || !data}
        <section class="card warn">
            <div class="eyebrow warn-text">Taxonomy not configured</div>
            <p>
                The dashboard needs a <code>taxonomy.json</code>
                mapping the deck's tags to the AAMC outline. Place it next to your collection,
                or open this page with a
                <code>?taxonomy=&lt;path&gt;</code>
                parameter.
            </p>
            {#if error}
                <p class="detail">{error}</p>
            {/if}
        </section>
    {:else if !data.meetsDataThreshold}
        <!-- Give-up / abstain state: no score, and an honest "why". -->
        <section class="card hero giveup">
            <div class="eyebrow warn-text">Not enough evidence yet — no score</div>
            <p class="giveup-lead">
                A tool that knows when it doesn't know is more trustworthy than one that
                always answers. Your memory score stays hidden until there are at least {MIN_REVIEWS}
                graded reviews
                <em>and</em>
                {pct(MIN_COVERAGE)} of the outline is covered.
            </p>
            <div class="meters">
                <div class="meter">
                    <div class="meter-top">
                        <span>Graded reviews</span>
                        <span class="meter-val">{gradedReviews} / {MIN_REVIEWS}</span>
                    </div>
                    <div class="bar">
                        <div
                            class="bar-fill"
                            class:is-met={reviewProgress >= 1}
                            style:width={pct(reviewProgress)}
                        ></div>
                    </div>
                </div>
                <div class="meter">
                    <div class="meter-top">
                        <span>Topic coverage</span>
                        <span class="meter-val">
                            {pct(coverageFraction)} / {pct(MIN_COVERAGE)}
                        </span>
                    </div>
                    <div class="bar">
                        <div
                            class="bar-fill"
                            class:is-met={coverageProgress >= 1}
                            style:width={pct(coverageProgress)}
                        ></div>
                    </div>
                </div>
            </div>
        </section>

        <section class="card">
            <div class="eyebrow">Outline coverage</div>
            <div class="cov-head">
                {categoriesCovered} / {categoriesTotal} AAMC categories
                <span class="cov-sub">
                    {pct(coverageFraction)} of the outline · {pct(weightedFraction)} by exam
                    weight
                </span>
            </div>
            <div class="bar">
                <div class="bar-fill" style:width={pct(coverageFraction)}></div>
            </div>
        </section>

        <section class="card">
            <div class="eyebrow">What to study next</div>
            <p class="section-note">
                Ordering only — not a readiness score. Highest points at stake = topic
                weight × your weakness ({rankedCount} due cards ranked).
            </p>
            <ul class="study-next">
                {#each studyNext as topic (topic.category)}
                    <li>
                        <span class="sn-cat">{topic.category}</span>
                        <span class="sn-name">{topic.name}</span>
                        <span class="sn-points">{topic.points.toFixed(1)}</span>
                    </li>
                {/each}
            </ul>
        </section>
    {:else}
        <!-- Populated state: memory hero leads, detail is subordinate. -->
        <section class="card hero">
            <div class="eyebrow">Memory score</div>
            <div class="score-row">
                <div class="range">{pct(rangeLow)}–{pct(rangeHigh)}</div>
                <span
                    class="chip conf"
                    class:is-high={confidenceLevel === "high"}
                    class:is-moderate={confidenceLevel === "moderate"}
                    class:is-low={confidenceLevel === "low"}
                >
                    {confidenceLabel} · ±{marginPoints.toFixed(1)}%
                </span>
            </div>
            <p class="point">
                Point estimate ≈ {pct(mean)} · shown as a 95% interval, never a bare number.
            </p>

            <div class="gauge" aria-hidden="true">
                <div
                    class="gauge-band"
                    style:left={pct(rangeLow)}
                    style:width={pct(rangeHigh - rangeLow)}
                ></div>
                <div class="gauge-mean" style:left={pct(mean)}></div>
            </div>
            <div class="gauge-scale" aria-hidden="true">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
            </div>

            <div class="facts">
                <div class="fact">
                    <div class="fact-num">{pct(coverageFraction)}</div>
                    <div class="fact-label">Outline coverage</div>
                    <div class="fact-sub">
                        {categoriesCovered}/{categoriesTotal} cats · {pct(
                            weightedFraction,
                        )} by weight
                    </div>
                </div>
                <div class="fact">
                    <div class="fact-num">{gradedReviews.toLocaleString()}</div>
                    <div class="fact-label">Graded reviews</div>
                    <div class="fact-sub">FSRS review log</div>
                </div>
                <div class="fact">
                    <div class="fact-num">{gradedCards.toLocaleString()}</div>
                    <div class="fact-label">Graded cards</div>
                    <div class="fact-sub">with a memory state</div>
                </div>
            </div>
        </section>

        <section class="card">
            <div class="eyebrow">What to study next</div>
            <p class="section-note">
                Highest points at stake = topic weight × your weakness. The
                points-at-stake queue surfaces these first ({rankedCount} due cards ranked).
            </p>
            <ul class="study-next">
                {#each studyNext as topic (topic.category)}
                    <li>
                        <span class="sn-cat">{topic.category}</span>
                        <span class="sn-name">{topic.name}</span>
                        <span class="sn-points">{topic.points.toFixed(1)}</span>
                    </li>
                {/each}
            </ul>
        </section>

        <section class="card">
            <div class="eyebrow">Why this range</div>
            <ul class="reasons">
                <li>
                    <span class="reason-key">Evidence</span>
                    {gradedReviews.toLocaleString()} graded reviews across {gradedCards}
                    cards — more evidence narrows the range.
                </li>
                <li>
                    <span class="reason-key">Coverage</span>
                    {pct(coverageFraction)} of the outline ({pct(weightedFraction)} by exam
                    weight); topics with no cards are never scored.
                </li>
                <li>
                    <span class="reason-key">Certainty</span>
                    95% interval spans {pct(rangeLow)}–{pct(rangeHigh)} (±{marginPoints.toFixed(
                        1,
                    )}%) → {confidenceLabel.toLowerCase()}.
                </li>
                {#if weakCodes}
                    <li>
                        <span class="reason-key">Weighing it down</span>
                        weak, high-yield topics {weakCodes}.
                    </li>
                {/if}
                {#if strongCodes}
                    <li>
                        <span class="reason-key">Holding it up</span>
                        strong topics {strongCodes}.
                    </li>
                {/if}
            </ul>
        </section>

        <details class="card details">
            <summary>
                <span class="eyebrow">Per-topic mastery</span>
                <span class="summary-meta">
                    {withData.length} with data · {noDataCount} no data · {topics.length}
                    AAMC categories
                </span>
            </summary>
            <table>
                <thead>
                    <tr>
                        <th>Topic</th>
                        <th class="num">Weight</th>
                        <th class="num">Cards</th>
                        <th>Mastery</th>
                    </tr>
                </thead>
                <tbody>
                    {#each topicsByWeight as topic (topic.category)}
                        <tr
                            class:empty={topic.totalCards === 0 ||
                                topic.gradedCards === 0}
                        >
                            <td>
                                <span class="sn-cat">{topic.category}</span>
                                {topic.name}
                            </td>
                            <td class="num">{topic.topicWeight.toFixed(1)}</td>
                            <td class="num">{topic.gradedCards}/{topic.totalCards}</td>
                            <td>
                                {#if topic.gradedCards > 0}
                                    <div class="mastery-cell">
                                        <div class="bar mini">
                                            <div
                                                class="bar-fill"
                                                class:is-strong={topic.meanRetrievability >=
                                                    0.8}
                                                class:is-medium={topic.meanRetrievability >=
                                                    0.6 &&
                                                    topic.meanRetrievability < 0.8}
                                                class:is-weak={topic.meanRetrievability <
                                                    0.6}
                                                style:width={pct(
                                                    topic.meanRetrievability,
                                                )}
                                            ></div>
                                        </div>
                                        <span class="mono">
                                            {pct(topic.meanRetrievability)}
                                        </span>
                                    </div>
                                {:else}
                                    <span class="detail">no data</span>
                                {/if}
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </details>
    {/if}
</div>

<style lang="scss">
    .dashboard {
        max-width: 760px;
        margin: 0 auto;
        padding: 1.25rem 1rem 2rem;
        color: var(--fg);
    }

    /* --- masthead ------------------------------------------------------- */
    .masthead {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1.25rem;
    }

    h1 {
        font-size: 1.4rem;
        line-height: 1.2;
        margin: 0 0 0.25rem;
    }

    .subtitle {
        color: var(--fg-subtle);
        margin: 0;
        max-width: 52ch;
        font-size: 0.9rem;
    }

    .updated {
        flex: none;
        color: var(--fg-subtle);
        font-size: 0.78rem;
        white-space: nowrap;
        padding-top: 0.2rem;
    }

    /* --- shared card + label ------------------------------------------- */
    .card {
        background: var(--canvas-elevated);
        border: 1px solid var(--border-subtle);
        border-radius: var(--border-radius-medium, 12px);
        padding: 1rem 1.25rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 1px 2px color-mix(in srgb, var(--shadow-subtle) 40%, transparent);
    }

    .eyebrow {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--fg-subtle);
        margin-bottom: 0.5rem;
    }

    .warn-text {
        color: var(--flag2, #d9822b);
    }

    .card.warn {
        border-color: var(--flag2, #d9822b);
    }

    .detail {
        color: var(--fg-subtle);
        font-size: 0.85rem;
    }

    .section-note {
        color: var(--fg-subtle);
        font-size: 0.82rem;
        margin: 0 0 0.6rem;
    }

    code {
        background: var(--canvas-inset);
        padding: 0 0.25em;
        border-radius: 4px;
    }

    /* --- hero: the top-line summary ------------------------------------ */
    .hero {
        padding: 1.25rem 1.25rem 1.1rem;
    }

    .score-row {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: 0.75rem 1rem;
    }

    .range {
        font-size: 3rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -0.01em;
        color: var(--accent-card, #2d6cdf);
        font-variant-numeric: tabular-nums;
    }

    .chip {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 0.2rem 0.6rem;
        font-size: 0.76rem;
        font-weight: 600;
        border: 1px solid var(--border-subtle);
    }

    .conf.is-high {
        color: var(--state-review, #2e7d32);
        border-color: color-mix(in srgb, var(--state-review, #2e7d32) 40%, transparent);
        background: color-mix(in srgb, var(--state-review, #2e7d32) 12%, transparent);
    }

    .conf.is-moderate {
        color: var(--flag2, #d9822b);
        border-color: color-mix(in srgb, var(--flag2, #d9822b) 40%, transparent);
        background: color-mix(in srgb, var(--flag2, #d9822b) 12%, transparent);
    }

    .conf.is-low {
        color: var(--accent-danger, #c62828);
        border-color: color-mix(
            in srgb,
            var(--accent-danger, #c62828) 40%,
            transparent
        );
        background: color-mix(in srgb, var(--accent-danger, #c62828) 12%, transparent);
    }

    .point {
        color: var(--fg-subtle);
        font-size: 0.86rem;
        margin: 0.5rem 0 0.9rem;
    }

    /* interval gauge: the shaded band shows the range, the tick the estimate */
    .gauge {
        position: relative;
        height: 12px;
        border-radius: 999px;
        background: var(--canvas-inset);
        border: 1px solid var(--border-subtle);
    }

    .gauge-band {
        position: absolute;
        top: 0;
        bottom: 0;
        min-width: 6px;
        background: color-mix(in srgb, var(--accent-card, #2d6cdf) 45%, transparent);
        border-radius: 999px;
    }

    .gauge-mean {
        position: absolute;
        top: -3px;
        bottom: -3px;
        width: 3px;
        margin-left: -1.5px;
        border-radius: 2px;
        background: var(--accent-card, #2d6cdf);
    }

    .gauge-scale {
        display: flex;
        justify-content: space-between;
        color: var(--fg-faint);
        font-size: 0.68rem;
        margin-top: 0.25rem;
    }

    /* key facts strip */
    .facts {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
        margin-top: 1.1rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border-subtle);
    }

    .fact-num {
        font-size: 1.35rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }

    .fact-label {
        font-size: 0.8rem;
        font-weight: 600;
    }

    .fact-sub {
        font-size: 0.72rem;
        color: var(--fg-subtle);
    }

    /* --- give-up meters ------------------------------------------------- */
    .giveup-lead {
        margin: 0 0 0.9rem;
        font-size: 0.9rem;
        max-width: 60ch;
    }

    .meters {
        display: grid;
        gap: 0.8rem;
    }

    .meter-top {
        display: flex;
        justify-content: space-between;
        font-size: 0.82rem;
        margin-bottom: 0.3rem;
    }

    .meter-val {
        font-variant-numeric: tabular-nums;
        color: var(--fg-subtle);
    }

    /* --- bars (meters, coverage, table) -------------------------------- */
    .bar {
        background: var(--canvas-inset);
        border-radius: 999px;
        height: 9px;
        overflow: hidden;
    }

    .bar.mini {
        height: 7px;
        flex: 1;
    }

    .bar-fill {
        height: 100%;
        background: var(--accent-card, #2d6cdf);
        border-radius: 999px;
        transition: width 0.3s ease;
    }

    .bar-fill.is-met,
    .bar-fill.is-strong {
        background: var(--state-review, #2e7d32);
    }

    .bar-fill.is-medium {
        background: var(--accent-card, #2d6cdf);
    }

    .bar-fill.is-weak {
        background: var(--accent-danger, #c62828);
    }

    /* --- coverage headline --------------------------------------------- */
    .cov-head {
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    .cov-sub {
        display: block;
        font-weight: 400;
        font-size: 0.82rem;
        color: var(--fg-subtle);
    }

    /* --- what to study next -------------------------------------------- */
    .study-next {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .study-next li {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.4rem 0;
        border-bottom: 1px solid var(--border-subtle);
    }

    .study-next li:last-child {
        border-bottom: none;
    }

    .sn-cat {
        display: inline-block;
        min-width: 2.4em;
        font-weight: 700;
        color: var(--accent-card, #2d6cdf);
        font-variant-numeric: tabular-nums;
    }

    .sn-name {
        flex: 1;
        font-size: 0.9rem;
    }

    .sn-points {
        font-variant-numeric: tabular-nums;
        font-weight: 700;
    }

    /* --- drivers -------------------------------------------------------- */
    .reasons {
        list-style: none;
        padding: 0;
        margin: 0;
        display: grid;
        gap: 0.5rem;
    }

    .reasons li {
        font-size: 0.86rem;
        line-height: 1.4;
    }

    .reason-key {
        display: inline-block;
        min-width: 8.5em;
        font-weight: 700;
        color: var(--fg);
        margin-right: 0.3rem;
    }

    /* --- collapsible per-topic table ----------------------------------- */
    .details summary {
        display: flex;
        align-items: baseline;
        gap: 0.6rem;
        cursor: pointer;
        list-style: none;
    }

    .details summary::-webkit-details-marker {
        display: none;
    }

    .details summary::before {
        content: "▸";
        color: var(--fg-subtle);
        font-size: 0.8rem;
    }

    .details[open] summary::before {
        content: "▾";
    }

    .details summary .eyebrow {
        margin-bottom: 0;
    }

    .summary-meta {
        color: var(--fg-subtle);
        font-size: 0.78rem;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        margin-top: 0.85rem;
    }

    th,
    td {
        text-align: left;
        padding: 0.35rem 0.5rem;
        border-bottom: 1px solid var(--border-subtle);
    }

    th {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--fg-subtle);
    }

    th.num,
    td.num {
        text-align: right;
        font-variant-numeric: tabular-nums;
    }

    tr.empty {
        color: var(--fg-faint);
    }

    .mastery-cell {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .mono {
        font-variant-numeric: tabular-nums;
        min-width: 2.8em;
        text-align: right;
    }
</style>
