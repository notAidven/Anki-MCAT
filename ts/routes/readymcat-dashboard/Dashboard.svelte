<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PointsAtStakeResponse } from "@generated/anki/points_at_stake_pb";

    export let data: PointsAtStakeResponse | null;
    export let error: string | null;

    // The give-up rule (mirrors the Rust thresholds): show no score until there
    // is enough evidence.
    const MIN_REVIEWS = 200;
    const MIN_COVERAGE = 0.5;

    const pct = (x: number): string => `${Math.round(x * 100)}%`;

    $: memory = data?.memory;
    $: coverage = data?.coverage;
    $: gradedReviews = memory?.gradedReviews ?? 0;
    $: coverageFraction = coverage?.fraction ?? 0;
    $: reviewProgress = Math.min(1, gradedReviews / MIN_REVIEWS);
    $: coverageProgress = Math.min(1, coverageFraction / MIN_COVERAGE);

    // "What to study next": the topics with the most points at stake.
    $: studyNext = (data?.topics ?? [])
        .filter((t) => t.totalCards > 0)
        .map((t) => ({ ...t, points: t.topicWeight * t.studentWeakness }))
        .sort((a, b) => b.points - a.points)
        .slice(0, 6);

    $: topicsByWeight = [...(data?.topics ?? [])].sort(
        (a, b) => b.topicWeight - a.topicWeight,
    );
</script>

<div class="dashboard">
    <header>
        <h1>ReadyMCAT — Honest Memory</h1>
        <p class="subtitle">
            Memory is recall probability from FSRS, aggregated per AAMC topic. We show
            it as a range, never a single number — and not at all until there is enough
            evidence.
        </p>
    </header>

    {#if error || !data}
        <section class="panel warn">
            <h2>Taxonomy not configured</h2>
            <p>
                The dashboard needs a <code>taxonomy.json</code>
                mapping the deck's tags to the AAMC outline. Place it next to your
                collection, or open this page with a
                <code>?taxonomy=&lt;path&gt;</code>
                 parameter.
            </p>
            {#if error}
                <p class="detail">{error}</p>
            {/if}
        </section>
    {:else if !data.meetsDataThreshold}
        <section class="panel giveup">
            <h2>Not enough evidence yet</h2>
            <p>
                A system that knows when it doesn't know is more trustworthy than one
                that always answers. We'll show your memory score once you've done at
                least {MIN_REVIEWS} graded reviews
                <em>and</em>
                covered at least {pct(MIN_COVERAGE)} of the outline.
            </p>

            <div class="progress-row">
                <div class="progress-label">
                    Graded reviews
                    <span>{gradedReviews} / {MIN_REVIEWS}</span>
                </div>
                <div class="bar">
                    <div class="fill" style:width={pct(reviewProgress)}></div>
                </div>
            </div>

            <div class="progress-row">
                <div class="progress-label">
                    Topic coverage
                    <span>{pct(coverageFraction)} / {pct(MIN_COVERAGE)}</span>
                </div>
                <div class="bar">
                    <div class="fill" style:width={pct(coverageProgress)}></div>
                </div>
            </div>
        </section>

        <section class="panel">
            <h2>Coverage so far</h2>
            <div class="coverage-headline">
                {coverage?.categoriesCovered ?? 0} / {coverage?.categoriesTotal ?? 0}
                AAMC categories
                <span class="detail">
                    ({pct(coverageFraction)} of the outline; {pct(
                        coverage?.weightedFraction ?? 0,
                    )} by exam weight)
                </span>
            </div>
            <div class="bar">
                <div class="fill" style:width={pct(coverageFraction)}></div>
            </div>
        </section>
    {:else}
        <section class="panel score">
            <h2>Memory score</h2>
            <div class="range">
                {pct(memory?.rangeLow ?? 0)} – {pct(memory?.rangeHigh ?? 0)}
            </div>
            <p class="detail">
                Estimated recall probability across {memory?.gradedCards ?? 0}
                graded cards, shown as a 95% interval. Based on {gradedReviews}
                graded reviews.
            </p>
        </section>

        <section class="panel">
            <h2>Outline coverage</h2>
            <div class="coverage-headline">
                {coverage?.categoriesCovered ?? 0} / {coverage?.categoriesTotal ?? 0}
                AAMC categories
                <span class="detail">
                    ({pct(coverageFraction)} of the outline; {pct(
                        coverage?.weightedFraction ?? 0,
                    )} by exam weight)
                </span>
            </div>
            <div class="bar">
                <div class="fill" style:width={pct(coverageFraction)}></div>
            </div>
        </section>

        <section class="panel">
            <h2>What to study next</h2>
            <p class="detail">
                Highest points at stake = topic weight × your weakness. The
                points-at-stake queue surfaces these cards first ({data.rankedCards
                    .length} due cards ranked).
            </p>
            <ul class="study-next">
                {#each studyNext as topic (topic.category)}
                    <li>
                        <span class="cat">{topic.category}</span>
                        <span class="name">{topic.name}</span>
                        <span class="points">{topic.points.toFixed(1)} pts</span>
                    </li>
                {/each}
            </ul>
        </section>

        <section class="panel">
            <h2>Per-topic mastery</h2>
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
                        <tr class:empty={topic.totalCards === 0}>
                            <td>
                                <span class="cat">{topic.category}</span>
                                {topic.name}
                            </td>
                            <td class="num">{topic.topicWeight.toFixed(1)}</td>
                            <td class="num">{topic.gradedCards}/{topic.totalCards}</td>
                            <td>
                                {#if topic.gradedCards > 0}
                                    <div class="mastery">
                                        <div class="bar small">
                                            <div
                                                class="fill"
                                                style:width={pct(
                                                    topic.meanRetrievability,
                                                )}
                                            ></div>
                                        </div>
                                        <span>{pct(topic.meanRetrievability)}</span>
                                    </div>
                                {:else}
                                    <span class="detail">no data</span>
                                {/if}
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </section>
    {/if}
</div>

<style lang="scss">
    .dashboard {
        max-width: 880px;
        margin: 0 auto;
        padding: 1rem;
        color: var(--fg, #2c2c2c);
    }

    header h1 {
        font-size: 1.6rem;
        margin-bottom: 0.25rem;
    }

    .subtitle {
        color: var(--fg-subtle, #66676b);
        margin-top: 0;
        max-width: 60ch;
    }

    .panel {
        background: var(--canvas-elevated, #f7f7f9);
        border: 1px solid var(--border-subtle, #e0e0e3);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }

    .panel h2 {
        font-size: 1.05rem;
        margin: 0 0 0.5rem;
    }

    .panel.warn {
        border-color: var(--flag1-fg, #e07a5f);
    }

    .score .range {
        font-size: 2.6rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: var(--accent-card, #2d6cdf);
    }

    .detail {
        color: var(--fg-subtle, #66676b);
        font-size: 0.85rem;
    }

    .coverage-headline {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    .coverage-headline .detail {
        display: block;
        font-weight: 400;
    }

    .progress-row {
        margin: 0.75rem 0;
    }

    .progress-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.85rem;
        margin-bottom: 0.25rem;
    }

    .bar {
        background: var(--canvas-inset, #e9e9ec);
        border-radius: 999px;
        height: 10px;
        overflow: hidden;
    }

    .bar.small {
        height: 8px;
        flex: 1;
    }

    .bar .fill {
        height: 100%;
        background: var(--accent-card, #2d6cdf);
        border-radius: 999px;
        transition: width 0.3s ease;
    }

    .study-next {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .study-next li {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid var(--border-subtle, #e0e0e3);
    }

    .study-next .name {
        flex: 1;
    }

    .study-next .points {
        font-variant-numeric: tabular-nums;
        font-weight: 600;
    }

    .cat {
        display: inline-block;
        min-width: 2.4em;
        font-weight: 600;
        color: var(--accent-card, #2d6cdf);
    }

    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }

    th,
    td {
        text-align: left;
        padding: 0.4rem 0.5rem;
        border-bottom: 1px solid var(--border-subtle, #e0e0e3);
    }

    th.num,
    td.num {
        text-align: right;
        font-variant-numeric: tabular-nums;
    }

    tr.empty {
        color: var(--fg-faint, #9a9aa0);
    }

    .mastery {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .mastery span {
        font-variant-numeric: tabular-nums;
        min-width: 3em;
    }

    code {
        background: var(--canvas-inset, #e9e9ec);
        padding: 0 0.25em;
        border-radius: 4px;
    }
</style>
