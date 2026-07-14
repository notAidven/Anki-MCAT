<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

The shared "Study next: <format>" card. Reads the honest scores through the pure
`recommendStudyFormat` decision ladder ($lib/readymcat/scores) and surfaces ONE
format to study next with a one-line, number-grounded "why", a one-tap launch
(the existing `startDeck:<key>` bridge), and a "start with <topic>" pointer that
asks the host to focus that ring in the Topic Mastery grid (dispatched as
`starttopic`). Used by BOTH the home hub and the dashboard so the two screens
never disagree about what to study next. When there is not enough data it
renders the honest "build a baseline" state (give-up meters + a diagnostic CTA),
never a fabricated recommendation.
-->
<script lang="ts">
    import type { PointsAtStakeResponse } from "@generated/anki/points_at_stake_pb";
    import { bridgeCommand } from "@tslib/bridgecommand";
    import { createEventDispatcher } from "svelte";

    import { glossary } from "$lib/readymcat/glossary";
    import InfoTooltip from "$lib/readymcat/InfoTooltip.svelte";
    import {
        MIN_ATTEMPTS,
        MIN_COVERAGE,
        MIN_REVIEWS,
        pct,
        recommendStudyFormat,
        type StudyFormatKey,
    } from "$lib/readymcat/scores";

    export let points: PointsAtStakeResponse | null = null;
    export let pointsError: string | null = null;
    /** Whether the first-launch diagnostic has been taken. The home hub supplies
     * it (drives the baseline "take the diagnostic" CTA); the dashboard omits it. */
    export let diagnosticTaken: boolean | undefined = undefined;
    /** Per-format availability + due counts, for the launch button. The home hub
     * supplies it; the dashboard omits it (a launch is then always offered — the
     * backend's `start_deck_review` is a no-op if the deck is missing). */
    export let decks: Partial<
        Record<StudyFormatKey, { present: boolean; due: number }>
    > | null = null;

    const dispatch = createEventDispatcher<{ starttopic: string }>();

    // Each format's accent (mirrors the home launch tiles + iOS), used for the
    // card's left rail + the format glyph so the card reads as tied to its tile.
    const ACCENT: Record<StudyFormatKey, string> = {
        mcq: "#2563eb",
        fr: "#7c3aed",
        passage: "#059669",
        cars: "#ea580c",
    };

    $: rec = pointsError
        ? null
        : recommendStudyFormat(
              points,
              diagnosticTaken === undefined ? undefined : { diagnosticTaken },
          );

    $: recDeck = rec && decks ? (decks[rec.key] ?? null) : null;
    // Unknown decks (dashboard passes none) => assume launchable.
    $: available = decks ? !!recDeck?.present : true;
    $: freshSet = !!recDeck && recDeck.present && recDeck.due <= 0;
    let startLabel = "";
    $: {
        if (!available) {
            startLabel = "Loading…";
        } else if (freshSet) {
            startLabel = "Start a fresh set";
        } else {
            startLabel = rec ? `Start ${rec.title}` : "";
        }
    }

    // Give-up meters for the honest baseline state (read straight from the
    // response, mirroring the dashboard's meters + shared thresholds).
    $: reviews = points?.memory?.gradedReviews ?? 0;
    $: coverageFraction = points?.coverage?.fraction ?? 0;
    $: attempts = points?.performance?.attempts ?? 0;

    function start(): void {
        if (!rec || !available) {
            return;
        }
        bridgeCommand(`startDeck:${rec.key}`);
    }
    function openDiagnostic(): void {
        bridgeCommand("openDiagnostic");
    }
    function startWithTopic(): void {
        if (rec?.topic) {
            dispatch("starttopic", rec.topic.category);
        }
    }
</script>

{#if rec}
    <section
        class="studynext"
        class:baseline={rec.state === "baseline"}
        style:--sn-accent={ACCENT[rec.key]}
        aria-label="Study next"
    >
        <span class="sn-rail" aria-hidden="true"></span>
        <div class="sn-body">
            <div class="sn-eyebrow">
                <InfoTooltip entry={glossary.studyNext}>Study next</InfoTooltip>
            </div>

            {#if rec.state === "baseline"}
                <div class="sn-title">Build a baseline</div>
                <p class="sn-why">{rec.why}</p>
                <div class="sn-actions">
                    {#if rec.takeDiagnostic}
                        <button
                            type="button"
                            class="sn-primary"
                            on:click={openDiagnostic}
                        >
                            Take the diagnostic
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
                        </button>
                    {:else}
                        <button
                            type="button"
                            class="sn-primary"
                            disabled={!available}
                            on:click={start}
                        >
                            {startLabel}
                            {#if available}
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
                            {/if}
                        </button>
                    {/if}
                </div>
                <div class="sn-meters" aria-label="Progress to your first scores">
                    <div class="sn-meter">
                        <div class="sn-meter-top">
                            <span>Reviews</span>
                            <span class="sn-meter-val">{reviews}/{MIN_REVIEWS}</span>
                        </div>
                        <div class="sn-bar">
                            <div
                                class="sn-fill"
                                class:met={reviews >= MIN_REVIEWS}
                                style:width={pct(Math.min(1, reviews / MIN_REVIEWS))}
                            ></div>
                        </div>
                    </div>
                    <div class="sn-meter">
                        <div class="sn-meter-top">
                            <span>Coverage</span>
                            <span class="sn-meter-val">
                                {pct(coverageFraction)}/{pct(MIN_COVERAGE)}
                            </span>
                        </div>
                        <div class="sn-bar">
                            <div
                                class="sn-fill"
                                class:met={coverageFraction >= MIN_COVERAGE}
                                style:width={pct(
                                    Math.min(1, coverageFraction / MIN_COVERAGE),
                                )}
                            ></div>
                        </div>
                    </div>
                    <div class="sn-meter">
                        <div class="sn-meter-top">
                            <span>Attempts</span>
                            <span class="sn-meter-val">{attempts}/{MIN_ATTEMPTS}</span>
                        </div>
                        <div class="sn-bar">
                            <div
                                class="sn-fill"
                                class:met={attempts >= MIN_ATTEMPTS}
                                style:width={pct(Math.min(1, attempts / MIN_ATTEMPTS))}
                            ></div>
                        </div>
                    </div>
                </div>
            {:else}
                <div class="sn-title">
                    <span class="sn-glyph" aria-hidden="true">
                        {#if rec.key === "mcq"}
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <circle cx="12" cy="12" r="10" />
                            </svg>
                        {:else if rec.key === "fr"}
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <rect x="2" y="2" width="20" height="20" rx="4" />
                            </svg>
                        {:else if rec.key === "passage"}
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
                    </span>
                    <span class="sn-title-text">{rec.title}</span>
                </div>
                <p class="sn-why">{rec.why}</p>
                <div class="sn-actions">
                    <button
                        type="button"
                        class="sn-primary"
                        disabled={!available}
                        on:click={start}
                    >
                        {startLabel}
                        {#if available}
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
                        {/if}
                    </button>
                    {#if rec.topic}
                        <button
                            type="button"
                            class="sn-topic"
                            on:click={startWithTopic}
                        >
                            Start with {rec.topic.name}
                        </button>
                    {/if}
                </div>
            {/if}
        </div>
    </section>
{/if}

<style lang="scss">
    // A single flat, border-defined card (the same 14px surface language as the
    // score rail + mastery panel) with a left accent rail in the recommended
    // format's colour, so the card reads as tied to its launch tile.
    .studynext {
        display: flex;
        gap: 0;
        background: var(--canvas-elevated);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 1px 2px color-mix(in srgb, var(--shadow-subtle) 40%, transparent);
    }

    .sn-rail {
        flex: 0 0 5px;
        align-self: stretch;
        background: var(--sn-accent, var(--accent-card, #2d6cdf));
    }

    // The baseline (abstain) state is quieter — a dashed, muted accent — so it
    // never looks like a confident verdict.
    .studynext.baseline .sn-rail {
        background: repeating-linear-gradient(
            180deg,
            var(--fg-faint, #9aa4b2) 0 6px,
            transparent 6px 11px
        );
        opacity: 0.7;
    }

    .sn-body {
        flex: 1 1 auto;
        min-width: 0;
        padding: 13px 16px 15px;
    }

    .sn-eyebrow {
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--fg-subtle);
        margin-bottom: 6px;
    }

    .sn-title {
        display: flex;
        align-items: center;
        gap: 9px;
        font-size: 19px;
        font-weight: 900;
        letter-spacing: -0.02em;
        color: var(--fg);
        margin-bottom: 5px;
    }

    .sn-glyph {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border-radius: 9px;
        background: var(--sn-accent, var(--accent-card, #2d6cdf));
        color: #fff;
        flex-shrink: 0;
    }

    .sn-glyph svg {
        width: 17px;
        height: 17px;
    }

    .sn-why {
        margin: 0 0 12px;
        font-size: 13px;
        line-height: 1.45;
        color: var(--fg-subtle);
        max-width: 62ch;
    }

    .sn-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px 14px;
    }

    .sn-primary {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font: inherit;
        font-size: 13px;
        font-weight: 800;
        color: #fff;
        background: var(--sn-accent, var(--accent-card, #2d6cdf));
        border: none;
        border-radius: 999px;
        padding: 8px 16px;
        cursor: pointer;
        white-space: nowrap;
    }

    .sn-primary:not(:disabled):hover {
        filter: brightness(1.06);
    }

    .sn-primary:disabled {
        cursor: default;
        opacity: 0.55;
    }

    .sn-primary svg {
        width: 15px;
        height: 15px;
    }

    .sn-topic {
        font: inherit;
        font-size: 12.5px;
        font-weight: 700;
        color: var(--fg-subtle);
        background: none;
        border: none;
        padding: 0;
        cursor: pointer;
        white-space: nowrap;
    }

    .sn-topic::after {
        content: " ↝";
    }

    .sn-topic:hover {
        color: var(--sn-accent, var(--accent-card, #2d6cdf));
        text-decoration: underline;
    }

    // give-up meters (baseline)
    .sn-meters {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px 14px;
        margin-top: 13px;
    }

    .sn-meter-top {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        color: var(--fg-subtle);
        margin-bottom: 4px;
    }

    .sn-meter-val {
        font-variant-numeric: tabular-nums;
        color: var(--fg-faint);
    }

    .sn-bar {
        height: 7px;
        border-radius: 999px;
        background: var(--canvas-inset);
        border: 1px solid var(--border-subtle);
        overflow: hidden;
    }

    .sn-fill {
        height: 100%;
        border-radius: 999px;
        background: var(--accent-card, #2d6cdf);
        transition: width 0.3s ease;
    }

    .sn-fill.met {
        background: #10b981;
    }

    @media (max-width: 640px) {
        .sn-meters {
            grid-template-columns: 1fr;
        }
    }
</style>
