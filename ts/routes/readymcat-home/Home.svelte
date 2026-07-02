<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PointsAtStakeResponse } from "@generated/anki/points_at_stake_pb";
    import { bridgeCommand } from "@tslib/bridgecommand";

    import type { DeckLaunchCounts, DeckLaunchKey, HomeStatus } from "./types";

    export let points: PointsAtStakeResponse | null;
    export let pointsError: string | null;
    export let status: HomeStatus | null;
    export let statusError: string | null;
    /** When this snapshot was fetched (ms epoch); drives "last updated". */
    export let generatedAt: number = Date.now();

    // Mirrors the honest-memory dashboard's give-up thresholds exactly (see
    // ts/routes/readymcat-dashboard/Dashboard.svelte) — the hub's status
    // strip must agree with the dashboard about when there's enough evidence.
    const MIN_REVIEWS = 200;
    const MIN_COVERAGE = 0.5;

    const pct = (x: number): string => `${Math.round(x * 100)}%`;

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

    $: studyNext = topics
        .filter((t) => t.totalCards > 0)
        .map((t) => ({ ...t, points: t.topicWeight * t.studentWeakness }))
        .sort((a, b) => b.points - a.points)
        .slice(0, 4);

    $: home = status?.available ? status : null;
    $: decks = home?.decks;
    $: progress = home?.progress;
    $: diagnostic = home?.diagnostic;

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
            return "NOT LOADED YET";
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
    <header class="statusbar">
        <div class="brand">
            <span class="mark"></span>
            <span class="word">ReadyMCAT</span>
        </div>
        <div class="pills">
            {#if pointsError || !points}
                <div class="pill warn">Scores: taxonomy not configured</div>
            {:else}
                <div class="pill">
                    Memory
                    {#if meetsDataThreshold}
                        <b>{pct(rangeLow)}–{pct(rangeHigh)}</b>
                    {:else}
                        <span class="pill-sub">not enough data</span>
                    {/if}
                </div>
                <div class="pill">
                    Performance
                    {#if performanceReady}
                        <b>{pct(perfLow)}–{pct(perfHigh)}</b>
                    {:else}
                        <span class="pill-sub">not enough data</span>
                    {/if}
                </div>
                <div class="pill">
                    Readiness
                    {#if readinessReady}
                        <b>{Math.round(readyLow)}–{Math.round(readyHigh)}</b>
                    {:else}
                        <span class="pill-sub">not enough data</span>
                    {/if}
                </div>
            {/if}
            {#if points && !pointsError}
                <div class="pill">
                    Coverage <b>{pct(coverageFraction)}</b>
                    <span class="pill-sub">
                        ({categoriesCovered}/{categoriesTotal})
                    </span>
                </div>
            {/if}
            {#if progress && progress.streakDays > 0}
                <div class="pill streak">
                    🔥 <b>{progress.streakDays}-day</b>
                    streak
                </div>
            {/if}
            {#if diagnostic}
                <div class="pill" class:ok={diagnostic.taken}>
                    {diagnostic.taken ? "✓ Diagnostic taken" : "Diagnostic not taken"}
                </div>
            {/if}
        </div>
    </header>

    {#if statusError}
        <section class="banner warn">
            Couldn't load your ReadyMCAT counts: {statusError}
        </section>
    {:else if home && Object.values(home.decks ?? {}).every((d) => !d.present)}
        <section class="banner warn">
            No ReadyMCAT content is loaded yet. Restart Anki once to let it pre-load the
            question bank, or check <code>Tools → ReadyMCAT Dashboard</code>
            .
        </section>
    {/if}

    <h1 class="hero-title">Continue studying</h1>
    <div class="tiles">
        {#each tiles as tile (tile.key)}
            {@const counts = countsFor(tile.key)}
            {@const available = !!counts?.present}
            <button
                type="button"
                class="tile {tile.cssClass}"
                class:unavailable={!available}
                disabled={!available}
                on:click={() => startDeck(tile.key)}
                aria-label={`Start studying ${tile.name}`}
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
        <section class="card">
            <div class="panel-head">
                <h3>What to study next</h3>
                <span class="tag">POINTS AT STAKE</span>
            </div>
            {#if !points || pointsError}
                <p class="empty-note">
                    Needs <code>taxonomy.json</code>
                    to rank topics. See the ReadyMCAT Dashboard for details.
                </p>
            {:else if studyNext.length === 0}
                <p class="empty-note">
                    Nothing due right now — every topic is caught up.
                </p>
            {:else}
                {#each studyNext as topic, i (topic.category)}
                    <div class="next-row">
                        <div class="rankchip" class:top={i === 0}>{i + 1}</div>
                        <div class="next-name">{topic.name}</div>
                        <div class="next-pct">
                            {topic.gradedCards > 0
                                ? `${pct(1 - topic.studentWeakness)} recall`
                                : "no data yet"}
                        </div>
                    </div>
                {/each}
            {/if}
            <div class="panel-footer">
                <button type="button" class="link-btn" on:click={openDashboard}>
                    Ranked by topic weight × your weakness — see full breakdown →
                </button>
            </div>
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
                    {#if meetsDataThreshold}
                        <div class="mini-bar">
                            <i
                                style:left={pct(rangeLow)}
                                style:width={pct(Math.max(0.02, rangeHigh - rangeLow))}
                            ></i>
                        </div>
                    {:else}
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

    // --- compact status strip -------------------------------------------
    .statusbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        background: var(--canvas-elevated);
        border: 1px solid var(--border-subtle);
        border-radius: 999px;
        padding: 8px 10px 8px 18px;
        box-shadow: 0 8px 20px -14px
            color-mix(in srgb, var(--shadow-subtle) 60%, transparent);
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
        row-gap: 8px;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 9px;
        font-weight: 900;
        font-size: 16px;
        letter-spacing: -0.02em;
        flex-shrink: 0;
    }

    .brand .mark {
        width: 24px;
        height: 24px;
        border-radius: 8px;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        flex-shrink: 0;
    }

    .pills {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }

    .pill {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 12.5px;
        font-weight: 700;
        background: var(--canvas-inset);
        border: 1px solid var(--border-subtle);
        padding: 6px 12px;
        border-radius: 999px;
        color: var(--fg-subtle);
        white-space: nowrap;
    }

    .pill b {
        color: var(--fg);
        font-weight: 800;
    }

    .pill-sub {
        color: var(--fg-faint);
        font-weight: 600;
    }

    .pill.warn {
        color: var(--flag2, #d9822b);
        border-color: color-mix(in srgb, var(--flag2, #d9822b) 40%, transparent);
    }

    .pill.streak b {
        color: #ea580c;
    }

    .pill.ok {
        color: var(--state-review, #2e7d32);
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

    .hero-title {
        font-size: 13px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--fg-faint);
        margin: 0 0 0.6rem;
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

    .tile-mcq .tile-start {
        color: #2563eb;
    }
    .tile-fr .tile-start {
        color: #7c3aed;
    }
    .tile-ps .tile-start {
        color: #059669;
    }
    .tile-cars .tile-start {
        color: #ea580c;
    }

    // --- secondary row -----------------------------------------------------
    .secondary {
        display: grid;
        grid-template-columns: 1.3fr 1fr;
        gap: 1rem;
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

    .panel-head .tag {
        font-size: 10px;
        font-weight: 800;
        color: var(--accent-danger, #c62828);
        background: color-mix(in srgb, var(--accent-danger, #c62828) 12%, transparent);
        padding: 3px 8px;
        border-radius: 999px;
    }

    .next-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 16px;
        border-top: 1px solid var(--border-subtle);
    }

    .next-row:first-of-type {
        border-top: none;
    }

    .rankchip {
        width: 20px;
        height: 20px;
        border-radius: 6px;
        background: var(--canvas-inset);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: 800;
        color: var(--fg-faint);
        flex-shrink: 0;
    }

    .rankchip.top {
        background: #f59e0b;
        color: #231600;
    }

    .next-name {
        font-size: 12.5px;
        font-weight: 700;
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .next-pct {
        font-size: 11px;
        color: var(--fg-faint);
        flex-shrink: 0;
    }

    .panel-footer {
        padding: 10px 16px 14px;
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
        display: flex;
        flex-direction: column;
        gap: 1rem;
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

    .mini-bar {
        height: 6px;
        border-radius: 999px;
        background: var(--canvas-inset);
        margin-top: 8px;
        overflow: hidden;
        position: relative;
    }

    .mini-bar i {
        position: absolute;
        top: 0;
        bottom: 0;
        background: var(--state-review, #2e7d32);
        border-radius: 999px;
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
        .secondary {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 640px) {
        .hub {
            padding: 0.75rem 0.75rem 2rem;
        }
        .statusbar {
            border-radius: 16px;
            padding: 10px 12px;
        }
        .brand span.word {
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
