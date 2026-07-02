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

    // Give-up rules (mirror the Rust thresholds): show no score until there is
    // enough evidence. Memory needs 200 graded reviews AND 50% coverage;
    // Performance needs 30 first-attempts on question cards; Readiness needs
    // BOTH (it is projected from them).
    const MIN_REVIEWS = 200;
    const MIN_COVERAGE = 0.5;
    const MIN_ATTEMPTS = 30;

    // The real MCAT total-score scale readiness projects onto.
    const SCORE_MIN = 472;
    const SCORE_MAX = 528;

    const pct = (x: number): string => `${Math.round(x * 100)}%`;
    // Position of a scaled score on the 472–528 axis, as a 0..1 fraction.
    const scorePos = (s: number): number =>
        Math.max(0, Math.min(1, (s - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)));

    $: memory = data?.memory;
    $: coverage = data?.coverage;
    $: performance = data?.performance;
    $: readiness = data?.readiness;
    $: topics = data?.topics ?? [];

    // --- memory -----------------------------------------------------------
    $: memMean = memory?.mean ?? 0;
    $: memLow = memory?.rangeLow ?? 0;
    $: memHigh = memory?.rangeHigh ?? 0;
    $: gradedReviews = memory?.gradedReviews ?? 0;
    $: gradedCards = memory?.gradedCards ?? 0;
    // meetsDataThreshold is the memory give-up flag (kept for compatibility).
    $: memoryReady = data?.meetsDataThreshold ?? false;

    // --- coverage ---------------------------------------------------------
    $: coverageFraction = coverage?.fraction ?? 0;
    $: weightedFraction = coverage?.weightedFraction ?? 0;
    $: categoriesCovered = coverage?.categoriesCovered ?? 0;
    $: categoriesTotal = coverage?.categoriesTotal ?? 0;

    // --- performance (accuracy on practice questions) ---------------------
    $: perfMean = performance?.mean ?? 0;
    $: perfLow = performance?.rangeLow ?? 0;
    $: perfHigh = performance?.rangeHigh ?? 0;
    $: attempts = performance?.attempts ?? 0;
    $: hits = performance?.hits ?? 0;
    $: performanceReady = performance?.meetsDataThreshold ?? false;
    $: perfTopics = performance?.topics ?? [];

    // --- readiness (heuristic 472–528 projection) -------------------------
    $: readyPoint = readiness?.point ?? 0;
    $: readyLow = readiness?.rangeLow ?? 0;
    $: readyHigh = readiness?.rangeHigh ?? 0;
    $: readinessReady = readiness?.meetsDataThreshold ?? false;

    // give-up progress meters
    $: reviewProgress = Math.min(1, gradedReviews / MIN_REVIEWS);
    $: coverageProgress = Math.min(1, coverageFraction / MIN_COVERAGE);
    $: attemptsProgress = Math.min(1, attempts / MIN_ATTEMPTS);

    // "How sure": the width of the reported 95% interval is the honest measure
    // of confidence — more evidence tightens it. Never invented, always derived.
    type ConfLevel = "high" | "moderate" | "low";
    // Confidence from a fractional (0..1 → percentage-point) interval width.
    function fracLevel(marginPts: number): ConfLevel {
        if (marginPts <= 2.5) {
            return "high";
        }
        if (marginPts <= 6) {
            return "moderate";
        }
        return "low";
    }
    // Confidence from a scaled-score interval width (readiness, in points).
    function scoreLevel(marginPts: number): ConfLevel {
        if (marginPts <= 3) {
            return "high";
        }
        if (marginPts <= 8) {
            return "moderate";
        }
        return "low";
    }
    function confLabel(level: ConfLevel): string {
        if (level === "high") {
            return "High confidence";
        }
        if (level === "moderate") {
            return "Moderate confidence";
        }
        return "Low confidence";
    }
    const confClass = (level: ConfLevel): string => `is-${level}`;

    $: memMargin = ((memHigh - memLow) / 2) * 100;
    $: memConf = fracLevel(memMargin);
    $: perfMargin = ((perfHigh - perfLow) / 2) * 100;
    $: perfConf = fracLevel(perfMargin);
    $: readyMargin = (readyHigh - readyLow) / 2;
    $: readyConf = scoreLevel(readyMargin);

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

    // Per-topic first-attempt accuracy, keyed by category for the detail table.
    $: accuracyByCat = new Map(perfTopics.map((t) => [t.category, t]));

    $: updatedLabel = new Date(generatedAt || Date.now()).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    });
</script>

<div class="dashboard">
    <header class="masthead">
        <div class="titles">
            <h1>ReadyMCAT — Honest Scores</h1>
            <p class="subtitle">
                Three separate, honest scores — <strong>Memory</strong>
                ,
                <strong>Performance</strong>
                and
                <strong>Readiness</strong>
                 — each a range with a confidence level, each hidden until there's enough
                evidence to back it up.
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
    {:else}
        <!-- Three co-equal headline stats. Each shows a range + confidence chip
             when it has enough evidence, or an honest give-up state below it. -->
        <section class="stats" aria-label="Headline scores">
            <!-- MEMORY -->
            <article class="card stat" class:is-giveup={!memoryReady}>
                <div class="stat-head">
                    <span class="eyebrow">Memory</span>
                    <span class="stat-tag">recall right now</span>
                </div>
                {#if memoryReady}
                    <div class="stat-range">{pct(memLow)}–{pct(memHigh)}</div>
                    <span class="chip conf {confClass(memConf)}">
                        {confLabel(memConf)} · ±{memMargin.toFixed(1)}%
                    </span>
                    <p class="stat-note">
                        Point ≈ {pct(memMean)} · FSRS recall across {gradedCards.toLocaleString()}
                        cards.
                    </p>
                    <div class="gauge" aria-hidden="true">
                        <div
                            class="gauge-band"
                            style:left={pct(memLow)}
                            style:width={pct(memHigh - memLow)}
                        ></div>
                        <div class="gauge-mean" style:left={pct(memMean)}></div>
                    </div>
                    <div class="gauge-scale" aria-hidden="true">
                        <span>0%</span>
                        <span>50%</span>
                        <span>100%</span>
                    </div>
                {:else}
                    <div class="stat-range muted">Not enough data</div>
                    <span class="chip needs">Needs evidence</span>
                    <p class="stat-note">
                        Hidden until {MIN_REVIEWS} graded reviews
                        <em>and</em>
                        {pct(MIN_COVERAGE)} coverage.
                    </p>
                    <div class="mini-meter">
                        <div class="meter-top">
                            <span>Reviews</span>
                            <span class="meter-val">
                                {gradedReviews} / {MIN_REVIEWS}
                            </span>
                        </div>
                        <div class="bar">
                            <div
                                class="bar-fill"
                                class:is-met={reviewProgress >= 1}
                                style:width={pct(reviewProgress)}
                            ></div>
                        </div>
                        <div class="meter-top">
                            <span>Coverage</span>
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
                {/if}
            </article>

            <!-- PERFORMANCE -->
            <article class="card stat" class:is-giveup={!performanceReady}>
                <div class="stat-head">
                    <span class="eyebrow">Performance</span>
                    <span class="stat-tag">practice-question accuracy</span>
                </div>
                {#if performanceReady}
                    <div class="stat-range">{pct(perfLow)}–{pct(perfHigh)}</div>
                    <span class="chip conf {confClass(perfConf)}">
                        {confLabel(perfConf)} · ±{perfMargin.toFixed(1)}%
                    </span>
                    <p class="stat-note">
                        Point ≈ {pct(perfMean)} · {hits.toLocaleString()}/{attempts.toLocaleString()}
                        first tries correct on practice questions.
                    </p>
                    <div class="gauge" aria-hidden="true">
                        <div
                            class="gauge-band alt"
                            style:left={pct(perfLow)}
                            style:width={pct(perfHigh - perfLow)}
                        ></div>
                        <div class="gauge-mean alt" style:left={pct(perfMean)}></div>
                    </div>
                    <div class="gauge-scale" aria-hidden="true">
                        <span>0%</span>
                        <span>50%</span>
                        <span>100%</span>
                    </div>
                {:else}
                    <div class="stat-range muted">Not enough data</div>
                    <span class="chip needs">Needs evidence</span>
                    <p class="stat-note">
                        First-attempt accuracy on MCQ / free-response / passage cards,
                        hidden until {MIN_ATTEMPTS} attempts.
                    </p>
                    <div class="mini-meter">
                        <div class="meter-top">
                            <span>Attempts</span>
                            <span class="meter-val">{attempts} / {MIN_ATTEMPTS}</span>
                        </div>
                        <div class="bar">
                            <div
                                class="bar-fill alt"
                                class:is-met={attemptsProgress >= 1}
                                style:width={pct(attemptsProgress)}
                            ></div>
                        </div>
                    </div>
                {/if}
            </article>

            <!-- READINESS -->
            <article class="card stat readiness" class:is-giveup={!readinessReady}>
                <div class="stat-head">
                    <span class="eyebrow">Readiness</span>
                    <span class="stat-tag heuristic-tag">heuristic · 472–528</span>
                </div>
                {#if readinessReady}
                    <div class="stat-range">{readyLow}–{readyHigh}</div>
                    <span class="chip conf {confClass(readyConf)}">
                        {confLabel(readyConf)} · ±{readyMargin.toFixed(0)}
                    </span>
                    <p class="stat-note">
                        Projected ≈ <strong>{readyPoint}</strong>
                         on the 472–528 scale.
                    </p>
                    <div class="gauge" aria-hidden="true">
                        <div
                            class="gauge-band ready"
                            style:left={pct(scorePos(readyLow))}
                            style:width={pct(scorePos(readyHigh) - scorePos(readyLow))}
                        ></div>
                        <div
                            class="gauge-mean ready"
                            style:left={pct(scorePos(readyPoint))}
                        ></div>
                    </div>
                    <div class="gauge-scale" aria-hidden="true">
                        <span>472</span>
                        <span>500</span>
                        <span>528</span>
                    </div>
                    <p class="caveat">
                        Heuristic projection from Performance + Memory — <strong>
                            uncalibrated
                        </strong>
                        , not a real MCAT score.
                    </p>
                {:else}
                    <div class="stat-range muted">Not enough data</div>
                    <span class="chip needs">Needs evidence</span>
                    <p class="stat-note">
                        Projected only once <em>both</em>
                         Memory and Performance have enough evidence.
                    </p>
                    <p class="caveat">
                        When shown it is a heuristic, uncalibrated projection — never a
                        real MCAT score.
                    </p>
                {/if}
            </article>
        </section>

        <!-- Supporting detail. -->
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
                Ordering only — not a score. Highest points at stake = topic weight ×
                your weakness ({rankedCount} due cards ranked).
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

        {#if memoryReady}
            <section class="card">
                <div class="eyebrow">Why these ranges</div>
                <ul class="reasons">
                    <li>
                        <span class="reason-key">Memory</span>
                        {gradedReviews.toLocaleString()} graded reviews across {gradedCards}
                        cards → {pct(memLow)}–{pct(memHigh)} ({confLabel(
                            memConf,
                        ).toLowerCase()}).
                    </li>
                    {#if performanceReady}
                        <li>
                            <span class="reason-key">Performance</span>
                            {hits.toLocaleString()}/{attempts.toLocaleString()} first-attempt
                            hits → {pct(perfLow)}–{pct(perfHigh)} ({confLabel(
                                perfConf,
                            ).toLowerCase()}).
                        </li>
                    {:else}
                        <li>
                            <span class="reason-key">Performance</span>
                            only {attempts}/{MIN_ATTEMPTS} question attempts so far — no score
                            yet.
                        </li>
                    {/if}
                    <li>
                        <span class="reason-key">Readiness</span>
                        {#if readinessReady}
                            heuristic blend (0.6·performance + 0.4·memory) → {readyLow}–{readyHigh},
                            widened for {pct(1 - weightedFraction)} uncovered weight.
                        {:else}
                            needs both memory and performance before it can be
                            projected.
                        {/if}
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
        {/if}

        <details class="card details">
            <summary>
                <span class="eyebrow">Per-topic breakdown</span>
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
                        <th class="num">Accuracy</th>
                    </tr>
                </thead>
                <tbody>
                    {#each topicsByWeight as topic (topic.category)}
                        {@const perfRow = accuracyByCat.get(topic.category)}
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
                            <td class="num">
                                {#if perfRow && perfRow.attempts > 0}
                                    <span class="mono">{pct(perfRow.accuracy)}</span>
                                    <span class="acc-sub">
                                        {perfRow.hits}/{perfRow.attempts}
                                    </span>
                                {:else}
                                    <span class="detail">—</span>
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

    /* --- three co-equal headline stats --------------------------------- */
    .stats {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.85rem;
        margin-bottom: 0.85rem;
    }

    @media (max-width: 640px) {
        .stats {
            grid-template-columns: 1fr;
        }
    }

    .stat {
        display: flex;
        flex-direction: column;
        margin-bottom: 0;
        padding: 1rem 1.1rem 1.1rem;
    }

    .stat.is-giveup {
        border-style: dashed;
    }

    .stat.readiness {
        border-color: color-mix(
            in srgb,
            var(--accent-card, #2d6cdf) 25%,
            var(--border-subtle)
        );
    }

    .stat-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.5rem;
        margin-bottom: 0.55rem;
    }

    .stat-head .eyebrow {
        margin-bottom: 0;
    }

    .stat-tag {
        font-size: 0.68rem;
        color: var(--fg-faint);
        text-align: right;
        line-height: 1.2;
    }

    .heuristic-tag {
        color: var(--flag2, #d9822b);
        font-weight: 600;
    }

    .stat-range {
        font-size: 1.95rem;
        font-weight: 800;
        line-height: 1.05;
        letter-spacing: -0.01em;
        color: var(--accent-card, #2d6cdf);
        font-variant-numeric: tabular-nums;
        margin-bottom: 0.4rem;
    }

    .stat-range.muted {
        color: var(--fg-faint);
        font-size: 1.35rem;
        font-weight: 700;
    }

    .stat-note {
        color: var(--fg-subtle);
        font-size: 0.8rem;
        margin: 0.55rem 0 0.7rem;
        flex: 1;
    }

    .caveat {
        font-size: 0.72rem;
        line-height: 1.35;
        color: var(--flag2, #d9822b);
        margin: 0.6rem 0 0;
        padding-top: 0.5rem;
        border-top: 1px dashed
            color-mix(in srgb, var(--flag2, #d9822b) 35%, transparent);
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

    .chip.needs {
        color: var(--fg-subtle);
        border-style: dashed;
        align-self: flex-start;
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

    /* performance uses a distinct hue so the three stats read apart */
    .gauge-band.alt {
        background: color-mix(in srgb, var(--state-review, #2e7d32) 42%, transparent);
    }

    .gauge-mean.alt {
        background: var(--state-review, #2e7d32);
    }

    .gauge-band.ready {
        background: color-mix(in srgb, var(--flag2, #d9822b) 45%, transparent);
    }

    .gauge-mean.ready {
        background: var(--flag2, #d9822b);
    }

    .gauge-scale {
        display: flex;
        justify-content: space-between;
        color: var(--fg-faint);
        font-size: 0.68rem;
        margin-top: 0.25rem;
    }

    /* --- give-up meters (inside a stat card) --------------------------- */
    .mini-meter {
        display: grid;
        gap: 0.25rem;
        margin-top: auto;
    }

    .meter-top {
        display: flex;
        justify-content: space-between;
        font-size: 0.78rem;
        margin-top: 0.25rem;
    }

    .meter-top:first-child {
        margin-top: 0;
    }

    .meter-val {
        font-variant-numeric: tabular-nums;
        color: var(--fg-subtle);
    }

    /* second-hue fill for the performance meter/gauge */
    .bar-fill.alt {
        background: var(--state-review, #2e7d32);
    }

    .acc-sub {
        display: block;
        font-size: 0.68rem;
        color: var(--fg-faint);
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
