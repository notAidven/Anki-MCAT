<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PointsAtStakeResponse } from "@generated/anki/points_at_stake_pb";
    import { bridgeCommand } from "@tslib/bridgecommand";
    import { tick } from "svelte";

    import { glossary } from "$lib/readymcat/glossary";
    import InfoTooltip from "$lib/readymcat/InfoTooltip.svelte";
    import {
        MIN_COVERAGE,
        MIN_REVIEWS,
        pct,
        recommendStudyFormat,
    } from "$lib/readymcat/scores";
    import StudyNext from "$lib/readymcat/StudyNext.svelte";
    import TopicMastery, {
        type MasteryTopic,
    } from "$lib/readymcat/TopicMastery.svelte";

    import type { DeckLaunchCounts, DeckLaunchKey, HomeStatus } from "./types";

    export let points: PointsAtStakeResponse | null;
    export let pointsError: string | null;
    export let status: HomeStatus | null;
    /** When this snapshot was fetched (ms epoch); drives "last updated". */
    export let generatedAt: number = Date.now();
    /** True while the counts aren't ready yet — a first-launch question-bank
     * import or an in-progress sync — so the hub shows an "updating…" state
     * (and keeps polling) instead of the "restart Anki" fallback or, worse, a
     * raw fetch/parse error. */
    export let settingUp: boolean = false;

    // Give-up thresholds (MIN_REVIEWS / MIN_COVERAGE), the percentage formatter
    // and the study-next ranking come from $lib/readymcat/scores, shared with
    // the dashboard so the hub's status strip always agrees with it about when
    // there's enough evidence.

    $: memory = points?.memory;
    $: coverage = points?.coverage;
    $: topics = points?.topics ?? [];
    $: meetsDataThreshold = points?.meetsDataThreshold ?? false;

    $: rangeLow = memory?.rangeLow ?? 0;
    $: rangeHigh = memory?.rangeHigh ?? 0;
    $: coverageFraction = coverage?.fraction ?? 0;
    $: categoriesCovered = coverage?.categoriesCovered ?? 0;
    $: categoriesTotal = coverage?.categoriesTotal ?? 0;

    // Performance + readiness (mirror the dashboard) so the hub shows all three
    // honest scores wherever it shows memory — each with its own give-up rule.
    $: performance = points?.performance;
    $: readiness = points?.readiness;
    $: perfLow = performance?.rangeLow ?? 0;
    $: perfHigh = performance?.rangeHigh ?? 0;
    $: performanceReady = performance?.meetsDataThreshold ?? false;
    $: readyLow = readiness?.rangeLow ?? 0;
    $: readyHigh = readiness?.rangeHigh ?? 0;
    $: readyPoint = readiness?.point ?? 0;
    $: readinessReady = readiness?.meetsDataThreshold ?? false;

    // Enriched topics for the interactive mastery ring grid (recall +
    // first-attempt accuracy merged per AAMC category), shared with the dashboard.
    $: perfByCat = new Map((performance?.topics ?? []).map((t) => [t.category, t]));
    $: masteryTopics = topics.map((t): MasteryTopic => {
        const p = perfByCat.get(t.category);
        return {
            category: t.category,
            name: t.name,
            topicWeight: t.topicWeight,
            studentWeakness: t.studentWeakness,
            gradedCards: t.gradedCards,
            totalCards: t.totalCards,
            meanRetrievability: t.meanRetrievability,
            accuracy: p?.accuracy ?? null,
            attempts: p?.attempts ?? 0,
            hits: p?.hits ?? 0,
        };
    });

    $: home = status?.available ? status : null;
    $: decks = home?.decks;
    $: progress = home?.progress;
    $: diagnostic = home?.diagnostic;

    // The "Study next" recommendation, computed with the SAME shared ladder the
    // StudyNext card uses (same inputs -> same verdict), so the tile we badge
    // always matches the format the card leads with. `recommendedKey` is only a
    // format key when there's a CONFIDENT pick (state "recommend"); in the honest
    // "baseline"/not-enough-data case it stays null so NO tile is badged — the
    // grid never claims a recommendation the card itself is abstaining from.
    $: diagnosticTaken = diagnostic?.taken;
    $: recommendation = pointsError
        ? null
        : recommendStudyFormat(
              points,
              diagnosticTaken === undefined ? undefined : { diagnosticTaken },
          );
    $: recommendedKey = recommendation && recommendation.state === "recommend"
        ? recommendation.key
        : null;

    interface Tile {
        key: DeckLaunchKey;
        name: string;
        description: string;
        noun: string;
        cssClass: string;
        icon: "circle" | "square" | "book" | "passage";
    }

    const tiles: Tile[] = [
        {
            key: "mcq",
            name: "Multiple Choice",
            description: "Discrete exam-style questions",
            noun: "questions",
            cssClass: "tile-mcq",
            icon: "circle",
        },
        {
            key: "fr",
            name: "Free Response",
            description: "Type-in recall, the core loop",
            noun: "cards",
            cssClass: "tile-fr",
            icon: "square",
        },
        {
            key: "passage",
            name: "Passage Sets",
            description: "Full AAMC-style passages",
            noun: "questions",
            cssClass: "tile-ps",
            icon: "book",
        },
        {
            key: "cars",
            name: "CARS",
            description: "Critical analysis & reasoning",
            noun: "questions",
            cssClass: "tile-cars",
            icon: "passage",
        },
    ];

    function countsFor(key: DeckLaunchKey): DeckLaunchCounts | null {
        return decks?.[key] ?? null;
    }

    function dueLabel(counts: DeckLaunchCounts | null): string {
        if (!counts || !counts.present) {
            return settingUp ? "SETTING UP…" : "NOT LOADED YET";
        }
        if (counts.due <= 0) {
            return "UP TO DATE";
        }
        return `${counts.due.toLocaleString()} DUE`;
    }

    function startDeck(key: DeckLaunchKey): void {
        const counts = countsFor(key);
        if (!counts || !counts.present) {
            return;
        }
        bridgeCommand(`startDeck:${key}`);
    }

    function openDiagnostic(): void {
        bridgeCommand("openDiagnostic");
    }

    function openDashboard(): void {
        bridgeCommand("openDashboard");
    }

    // The "Study next" card's "start with <topic>" pointer: focus that ring in
    // the Topic Mastery grid (a fresh object so re-clicks re-focus) and scroll
    // it into view. Topic-scoped launch is deferred; this reuses the tile launch
    // + the mastery viz per the v1 design.
    let masterySection: HTMLElement | undefined;
    let focusRequest: { category: string } | null = null;

    async function focusTopic(category: string): Promise<void> {
        focusRequest = { category };
        await tick();
        masterySection?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function daysAgo(unixSeconds: number | null | undefined): string {
        if (!unixSeconds) {
            return "";
        }
        const days = Math.floor((Date.now() / 1000 - unixSeconds) / 86400);
        if (days <= 0) {
            return "today";
        }
        if (days === 1) {
            return "1 day ago";
        }
        return `${days} days ago`;
    }

    function accuracyLabel(value: number | null | undefined): string {
        if (value === null || value === undefined) {
            return "—";
        }
        return pct(value);
    }

    $: updatedLabel = new Date(generatedAt || Date.now()).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    });
</script>

<div class="hub">
    <!-- The header is an integrated page masthead, not a floating bar: a
         wordmark + a quiet secondary status line, then the three honest scores
         as one connected "score rail" (the primary signal). `.statusbar` (root)
         and the `pill` class on each score are retained as hooks for the
         Playwright e2e / tooltip probe; `.tiles` below is the tab probe marker. -->
    <header class="statusbar">
        <div class="masthead">
            <div class="brand">
                <span class="mark" aria-hidden="true"></span>
                <span class="word">ReadyMCAT</span>
            </div>
            <div class="status" aria-label="Study status">
                {#if points && !pointsError}
                    <span class="item">
                        <InfoTooltip entry={glossary.coverage}>Coverage</InfoTooltip>
                        <b>{pct(coverageFraction)}</b>
                        <span class="muted">
                            ({categoriesCovered}/{categoriesTotal})
                        </span>
                    </span>
                {/if}
                {#if progress && progress.streakDays > 0}
                    <span class="item">
                        <span aria-hidden="true">🔥</span>
                        <b>{progress.streakDays}-day</b>
                        streak
                    </span>
                {/if}
                {#if diagnostic}
                    {#if diagnostic.taken}
                        <span class="item done">✓ Diagnostic</span>
                    {:else}
                        <button
                            type="button"
                            class="item cta"
                            on:click={openDiagnostic}
                        >
                            Take the diagnostic
                            <svg
                                class="cta-arrow"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            >
                                <path d="M5 12h14M13 6l6 6-6 6" />
                            </svg>
                        </button>
                    {/if}
                {/if}
            </div>
        </div>

        <div class="scores" role="group" aria-label="Honest scores">
            {#if pointsError || !points}
                <p class="scores-empty">
                    Scores need a <code>taxonomy.json</code>
                    — not configured yet.
                </p>
            {:else}
                <div class="score pill">
                    <span class="score-label">
                        <InfoTooltip entry={glossary.memory}>Memory</InfoTooltip>
                    </span>
                    {#if meetsDataThreshold}
                        <span class="score-val">{pct(rangeLow)}–{pct(rangeHigh)}</span>
                    {:else}
                        <span class="score-empty">not enough data</span>
                    {/if}
                </div>
                <div class="score pill">
                    <span class="score-label">
                        <InfoTooltip entry={glossary.performance}>
                            Performance
                        </InfoTooltip>
                    </span>
                    {#if performanceReady}
                        <span class="score-val">{pct(perfLow)}–{pct(perfHigh)}</span>
                    {:else}
                        <span class="score-empty">not enough data</span>
                    {/if}
                </div>
                <div class="score pill">
                    <span class="score-label">
                        <InfoTooltip entry={glossary.readiness}>Readiness</InfoTooltip>
                    </span>
                    {#if readinessReady}
                        <span class="score-val">
                            {Math.round(readyLow)}–{Math.round(readyHigh)}
                        </span>
                    {:else}
                        <span class="score-empty">not enough data</span>
                    {/if}
                </div>
            {/if}
        </div>
    </header>

    {#if settingUp}
        <section class="banner info">
            Updating your ReadyMCAT hub… this happens on a new profile or while your
            collection is syncing, and refreshes automatically when it's ready.
        </section>
    {:else if home && Object.values(home.decks ?? {}).every((d) => !d.present)}
        <section class="banner warn">
            No ReadyMCAT content is loaded yet. Restart Anki once to let it pre-load the
            question bank, or check <code>Tools → ReadyMCAT Dashboard</code>
            .
        </section>
    {/if}

    {#if !settingUp}
        <div class="studynext-slot">
            <StudyNext
                {points}
                {pointsError}
                diagnosticTaken={diagnostic?.taken}
                decks={decks ?? null}
                on:starttopic={(e) => focusTopic(e.detail)}
            />
        </div>
    {/if}

    <div class="hero-head">
        <h1 class="hero-title">Continue studying</h1>
        {#if recommendedKey}
            <!-- Quiet cue tying the "Study next" card to this picker: the card
                 leads with one format, but every tile below is equally
                 launchable. Shown only when a real recommendation exists. -->
            <span class="hero-hint">Recommended for you — or pick any format</span>
        {/if}
    </div>
    <div class="tiles">
        {#each tiles as tile (tile.key)}
            {@const counts = countsFor(tile.key)}
            {@const available = !!counts?.present}
            {@const recommended = tile.key === recommendedKey}
            <button
                type="button"
                class="tile {tile.cssClass}"
                class:unavailable={!available}
                class:recommended
                disabled={!available}
                on:click={() => startDeck(tile.key)}
                aria-label={recommended
                    ? `Start studying ${tile.name} (recommended)`
                    : `Start studying ${tile.name}`}
            >
                <div class="tile-glyph">
                    {#if tile.icon === "circle"}
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <circle cx="12" cy="12" r="10" />
                        </svg>
                    {:else if tile.icon === "square"}
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <rect x="2" y="2" width="20" height="20" rx="4" />
                        </svg>
                    {:else if tile.icon === "book"}
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <rect x="3" y="2" width="18" height="20" rx="3" />
                        </svg>
                    {:else}
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path
                                d="M4 19V5a2 2 0 0 1 2-2h8l6 6v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z"
                            />
                        </svg>
                    {/if}
                </div>
                <div class="tile-top">
                    <div>
                        {#if recommended}
                            <div class="tile-badge">
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                    <path
                                        d="M12 2.5l2.6 5.55 6.02.79-4.44 4.15 1.14 5.96L12 21.9l-5.32 2.99 1.14-5.96-4.44-4.15 6.02-.79L12 2.5z"
                                    />
                                </svg>
                                Recommended
                            </div>
                        {/if}
                        <div class="tile-name">{tile.name}</div>
                        <div class="tile-desc">{tile.description}</div>
                    </div>
                    <div class="tile-due">{dueLabel(counts)}</div>
                </div>
                <div class="tile-bottom">
                    <div class="tile-count">
                        {(counts?.total ?? 0).toLocaleString()}
                        <span>total {tile.noun}</span>
                    </div>
                    {#if available}
                        <div class="tile-start">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            >
                                <path d="M5 12h14M13 6l6 6-6 6" />
                            </svg>
                        </div>
                    {/if}
                </div>
            </button>
        {/each}
    </div>

    <div class="secondary">
        <section
            class="card mastery-card"
            bind:this={masterySection}
            id="rmcat-home-topics"
        >
            <div class="panel-head">
                <h3>Topic mastery</h3>
                <button
                    type="button"
                    class="link-btn head-link"
                    on:click={openDashboard}
                >
                    Full breakdown →
                </button>
            </div>
            {#if !points || pointsError}
                <p class="empty-note">
                    Needs <code>taxonomy.json</code>
                    to rank topics. See the ReadyMCAT Dashboard for details.
                </p>
            {:else}
                <TopicMastery topics={masteryTopics} compact limit={8} {focusRequest} />
            {/if}
        </section>

        <div class="stack">
            <section class="card mini-card">
                <div class="mini-head"><h3>Scores</h3></div>
                {#if !points || pointsError}
                    <p class="empty-note">Not configured yet.</p>
                {:else}
                    <div class="memory-line">
                        <span>Memory</span>
                        {#if meetsDataThreshold}
                            <b>{pct(rangeLow)}–{pct(rangeHigh)}</b>
                        {:else}
                            <span>not enough data yet</span>
                        {/if}
                    </div>
                    {#if !meetsDataThreshold}
                        <p class="mini-sub">
                            Needs {MIN_REVIEWS} graded reviews and {pct(MIN_COVERAGE)} outline
                            coverage before a score is shown.
                        </p>
                    {/if}
                    <div class="memory-line">
                        <span>Performance</span>
                        {#if performanceReady}
                            <b>{pct(perfLow)}–{pct(perfHigh)}</b>
                        {:else}
                            <span>not enough data yet</span>
                        {/if}
                    </div>
                    <div class="memory-line">
                        <span>Readiness</span>
                        {#if readinessReady}
                            <b>{Math.round(readyLow)}–{Math.round(readyHigh)}</b>
                            <span>≈{Math.round(readyPoint)}/528</span>
                        {:else}
                            <span>not enough data yet</span>
                        {/if}
                    </div>
                {/if}
                {#if points && !pointsError}
                    <div class="mini-sub">
                        {categoriesCovered}/{categoriesTotal} AAMC categories · {pct(
                            coverageFraction,
                        )} outline coverage
                    </div>
                {/if}
            </section>

            <section class="card mini-card">
                <div class="diag-row">
                    <div class="diag-info">
                        <div class="t">Diagnostic Quiz</div>
                        <div class="s">
                            {#if diagnostic?.taken}
                                Taken {daysAgo(diagnostic.takenAt)}
                            {:else}
                                Not taken yet
                            {/if}
                        </div>
                    </div>
                    <button type="button" class="btn-sm" on:click={openDiagnostic}>
                        {diagnostic?.taken ? "Retake" : "Take diagnostic"}
                    </button>
                </div>
            </section>

            <section class="card mini-card">
                <div class="mini-head"><h3>Overall progress</h3></div>
                {#if progress}
                    <div class="progress-grid">
                        <div class="pstat">
                            <div class="label">Studied</div>
                            <div class="value">
                                {progress.cardsStudied.toLocaleString()}
                                <small>cards</small>
                            </div>
                        </div>
                        <div class="pstat">
                            <div class="label">Streak</div>
                            <div class="value">
                                {progress.streakDays}
                                <small>days</small>
                            </div>
                        </div>
                        <div class="pstat">
                            <div class="label">Active days (7d)</div>
                            <div class="value">
                                {progress.activeDaysThisWeek}
                                <small>/ 7</small>
                            </div>
                        </div>
                        <div class="pstat">
                            <div class="label">7-day acc.</div>
                            <div class="value">
                                {accuracyLabel(progress.accuracy7d)}
                            </div>
                        </div>
                    </div>
                {:else}
                    <p class="empty-note">No study history yet.</p>
                {/if}
            </section>
        </div>
    </div>

    <footer class="updated">Updated {updatedLabel}</footer>
</div>

<style lang="scss">
    .hub {
        max-width: 1180px;
        margin: 0 auto;
        padding: 1rem 1.25rem 2.5rem;
        color: var(--fg);
    }

    // --- integrated masthead + honest-score rail ------------------------
    // Sits on the page canvas (no floating elevated bar): a wordmark + a quiet
    // divided status line, then the three honest scores in one bordered rail —
    // the same flat, border-defined 14px card language as the mastery panel.
    .statusbar {
        display: flex;
        flex-direction: column;
        gap: 0.85rem;
        margin-bottom: 1.6rem;
    }

    .masthead {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem 1.25rem;
        flex-wrap: wrap;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 900;
        font-size: 18px;
        letter-spacing: -0.03em;
        flex-shrink: 0;
    }

    .brand .mark {
        width: 26px;
        height: 26px;
        border-radius: 9px;
        // Brand mark keeps a fixed gradient (ties to the MCQ/FR launch tiles);
        // it reads on both themes, unlike a themed surface token.
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        box-shadow: 0 2px 6px -2px color-mix(in srgb, #6d3bf5 55%, transparent);
        flex-shrink: 0;
    }

    // Secondary status: a calm, divided "ledger" line — coverage, streak,
    // diagnostic — deliberately lighter than the scores below it.
    .status {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        row-gap: 6px;
        font-size: 12.5px;
        font-weight: 600;
        color: var(--fg-subtle);
    }

    .status .item {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        white-space: nowrap;
    }

    // Hairline divider between whichever items render (the motif is reused from
    // the score rail); the leading item never shows one.
    .status .item::before {
        content: "";
        width: 1px;
        height: 13px;
        margin: 0 12px;
        background: var(--border-subtle);
    }

    .status .item:first-child::before {
        display: none;
    }

    .status .item b {
        color: var(--fg);
        font-weight: 800;
        font-variant-numeric: tabular-nums;
    }

    .status .muted {
        color: var(--fg-faint);
        font-variant-numeric: tabular-nums;
    }

    .status .item.done {
        color: #10b981;
        font-weight: 700;
    }

    .status button.item {
        font: inherit;
        font-weight: 700;
        color: var(--accent-card, #2d6cdf);
        background: none;
        border: none;
        padding: 0;
        cursor: pointer;
    }

    .status button.item:hover {
        text-decoration: underline;
    }

    .status .cta-arrow {
        width: 13px;
        height: 13px;
        transition: transform 0.15s ease;
    }

    .status button.item:hover .cta-arrow {
        transform: translateX(2px);
    }

    // The honest-score rail: three co-equal segments in one flat card, split by
    // hairline dividers — one readout, read together (mirrors the dashboard's
    // three headline scores).
    .scores {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        background: var(--canvas-elevated);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 1px 2px color-mix(in srgb, var(--shadow-subtle) 40%, transparent);
    }

    .score {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 13px 16px 14px;
    }

    .score + .score {
        border-left: 1px solid var(--border-subtle);
    }

    .score-label {
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--fg-subtle);
    }

    // Value / empty state share a baseline row so the three segments line up
    // whether a score is shown or still honestly withheld.
    .score-val,
    .score-empty {
        display: flex;
        align-items: flex-end;
        min-height: 26px;
    }

    .score-val {
        font-size: 22px;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.02em;
        color: var(--fg);
        font-variant-numeric: tabular-nums;
    }

    // The honest empty state is real information, so keep it legible (subtle,
    // not faint) — it must stay readable on the dark elevated surface too.
    .score-empty {
        font-size: 12.5px;
        font-weight: 600;
        color: var(--fg-subtle);
    }

    .scores-empty {
        grid-column: 1 / -1;
        margin: 0;
        padding: 14px 16px;
        font-size: 12.5px;
        color: var(--fg-subtle);
    }

    .banner {
        border-radius: 10px;
        padding: 0.7rem 1rem;
        margin-bottom: 1.25rem;
        font-size: 0.86rem;
    }

    .banner.warn {
        background: color-mix(in srgb, var(--flag2, #d9822b) 12%, transparent);
        border: 1px solid color-mix(in srgb, var(--flag2, #d9822b) 40%, transparent);
        color: var(--fg);
    }

    .banner.info {
        background: color-mix(in srgb, var(--accent-card, #2d6cdf) 12%, transparent);
        border: 1px solid
            color-mix(in srgb, var(--accent-card, #2d6cdf) 40%, transparent);
        color: var(--fg);
    }

    // The "Study next" recommendation card sits above the format tiles as the
    // lead action; it uses the shared StudyNext component's own card styling.
    .studynext-slot {
        margin-bottom: 1.6rem;
    }

    // The picker header: the "Continue studying" label with a quiet inline cue
    // (shown only when a recommendation exists) that the grid below is a free
    // choice, not locked to the recommended format.
    .hero-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.5rem 1rem;
        flex-wrap: wrap;
        margin: 0 0 0.6rem;
    }

    .hero-title {
        font-size: 13px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--fg-faint);
        margin: 0;
    }

    .hero-hint {
        font-size: 12px;
        font-weight: 600;
        color: var(--fg-subtle);
    }

    // --- format tiles: the hero ------------------------------------------
    .tiles {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }

    .tile {
        position: relative;
        overflow: hidden;
        border-radius: 18px;
        padding: 1.15rem;
        color: #fff;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 150px;
        box-shadow: 0 14px 28px -18px rgba(20, 20, 40, 0.5);
        cursor: pointer;
        border: none;
        text-align: left;
        font-family: inherit;
        appearance: none;
    }

    .tile:disabled,
    .tile.unavailable {
        cursor: default;
        opacity: 0.55;
    }

    .tile:not(:disabled):hover {
        filter: brightness(1.04);
    }

    // The recommended tile carries a soft white ring on top of its drop shadow
    // so it's unmistakable at a glance without changing its footprint. Reads on
    // both themes (the ring rides on the tile's own colour gradient).
    .tile.recommended {
        box-shadow:
            0 14px 28px -18px rgba(20, 20, 40, 0.5),
            0 0 0 2px rgba(255, 255, 255, 0.6);
    }

    .tile-mcq {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
    }
    .tile-fr {
        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
    }
    .tile-ps {
        background: linear-gradient(135deg, #10b981, #059669);
    }
    .tile-cars {
        background: linear-gradient(135deg, #f97316, #ea580c);
    }

    .tile-glyph {
        position: absolute;
        right: -10px;
        bottom: -16px;
        opacity: 0.16;
        pointer-events: none;
    }

    .tile-glyph svg {
        width: 108px;
        height: 108px;
    }

    .tile-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 0.5rem;
    }

    // "Recommended" pill: a solid white chip with the tile's own accent as its
    // text (mirrors the white circular start button), so it clearly marks the
    // suggested format while staying on-brand. Sits above the tile name in the
    // top-left corner. Per-format text colour set alongside .tile-start below.
    .tile-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        width: fit-content;
        margin-bottom: 8px;
        padding: 3px 9px 3px 7px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.95);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        box-shadow: 0 2px 6px -2px rgba(20, 20, 40, 0.4);
    }

    .tile-badge svg {
        width: 11px;
        height: 11px;
    }

    .tile-name {
        font-size: 16px;
        font-weight: 800;
        letter-spacing: -0.01em;
    }

    .tile-desc {
        font-size: 12px;
        opacity: 0.85;
        margin-top: 2px;
    }

    .tile-due {
        font-size: 10.5px;
        font-weight: 800;
        background: rgba(255, 255, 255, 0.22);
        padding: 4px 9px;
        border-radius: 999px;
        letter-spacing: 0.02em;
        white-space: nowrap;
        flex-shrink: 0;
    }

    .tile-bottom {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
    }

    .tile-count {
        font-size: 30px;
        font-weight: 900;
        letter-spacing: -0.02em;
    }

    .tile-count span {
        font-size: 11px;
        font-weight: 600;
        opacity: 0.8;
        display: block;
        margin-top: 2px;
    }

    .tile-start {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.94);
        flex-shrink: 0;
    }

    .tile-start svg {
        width: 16px;
        height: 16px;
        color: currentColor;
    }

    .tile-mcq .tile-start,
    .tile-mcq .tile-badge {
        color: #2563eb;
    }
    .tile-fr .tile-start,
    .tile-fr .tile-badge {
        color: #7c3aed;
    }
    .tile-ps .tile-start,
    .tile-ps .tile-badge {
        color: #059669;
    }
    .tile-cars .tile-start,
    .tile-cars .tile-badge {
        color: #ea580c;
    }

    // --- secondary row -----------------------------------------------------
    .secondary {
        display: block;
    }

    .mastery-card {
        margin-bottom: 1rem;
        padding: 14px 16px 16px;
    }

    .head-link {
        font-size: 11.5px;
    }

    .card {
        background: var(--canvas-elevated);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        box-shadow: 0 1px 2px color-mix(in srgb, var(--shadow-subtle) 40%, transparent);
    }

    .panel-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 16px 8px;
    }

    .panel-head h3 {
        font-size: 13.5px;
        font-weight: 800;
        margin: 0;
    }

    .link-btn {
        font-size: 11.5px;
        font-weight: 700;
        color: var(--fg-subtle);
        background: none;
        border: none;
        padding: 0;
        cursor: pointer;
        text-align: left;
    }

    .link-btn:hover {
        color: var(--accent-card, #2d6cdf);
    }

    .empty-note {
        font-size: 12.5px;
        color: var(--fg-subtle);
        padding: 0 16px 12px;
        margin: 0;
    }

    .stack {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        align-items: start;
    }

    .mini-card {
        padding: 1rem 1rem 0.9rem;
    }

    .mini-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }

    .mini-head h3 {
        font-size: 13px;
        font-weight: 800;
        margin: 0;
    }

    .memory-line {
        display: flex;
        align-items: baseline;
        gap: 8px;
        flex-wrap: wrap;
    }

    .memory-line b {
        font-size: 24px;
        font-weight: 900;
        letter-spacing: -0.02em;
    }

    .memory-line span {
        font-size: 11.5px;
        color: var(--fg-faint);
    }

    .mini-sub {
        font-size: 11px;
        color: var(--fg-faint);
        margin-top: 8px;
    }

    .diag-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
    }

    .diag-info .t {
        font-size: 12.5px;
        font-weight: 800;
    }

    .diag-info .s {
        font-size: 11px;
        color: var(--fg-faint);
        margin-top: 2px;
    }

    .btn-sm {
        font-size: 11.5px;
        font-weight: 800;
        padding: 7px 12px;
        border-radius: 999px;
        border: 1px solid var(--border-subtle);
        background: var(--canvas-inset);
        color: var(--fg);
        cursor: pointer;
        white-space: nowrap;
    }

    .btn-sm:hover {
        border-color: var(--accent-card, #2d6cdf);
    }

    .progress-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
    }

    .pstat {
        background: var(--canvas-inset);
        border-radius: 10px;
        padding: 8px 10px;
    }

    .pstat .label {
        font-size: 9.5px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--fg-faint);
    }

    .pstat .value {
        font-size: 17px;
        font-weight: 900;
        margin-top: 3px;
    }

    .pstat .value small {
        font-size: 10.5px;
        font-weight: 600;
        color: var(--fg-faint);
    }

    .updated {
        text-align: right;
        font-size: 11px;
        color: var(--fg-faint);
        margin-top: 1.25rem;
    }

    @media (max-width: 920px) {
        .stack {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 640px) {
        .hub {
            padding: 0.75rem 0.75rem 2rem;
        }
        // Stack the three scores; the hairline divider turns horizontal.
        .scores {
            grid-template-columns: 1fr;
        }
        .score + .score {
            border-left: none;
            border-top: 1px solid var(--border-subtle);
        }
        // Drop the vertical rules so wrapped status items don't show a stray
        // leading divider; spacing carries the separation instead.
        .status {
            column-gap: 16px;
        }
        .status .item::before {
            display: none;
        }
        .tiles {
            grid-template-columns: 1fr;
        }
        .tile {
            min-height: 120px;
        }
        .tile-count {
            font-size: 26px;
        }
    }
</style>
