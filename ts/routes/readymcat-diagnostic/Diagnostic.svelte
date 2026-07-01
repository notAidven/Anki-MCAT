<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import { scoreAndSeedDiagnostic } from "@generated/backend";
    import type { DiagnosticQuiz } from "@generated/anki/diagnostic_pb";
    import { bridgeCommand } from "@tslib/bridgecommand";

    export let quiz: DiagnosticQuiz | null;
    export let error: string | null;

    type RecordedResponse = {
        itemId: string;
        category: string;
        chosen: string;
        answered: boolean;
        correct: boolean;
        difficulty: string;
    };

    $: items = quiz?.items ?? [];
    $: available = !error && !!quiz && quiz.present && items.length > 0;

    // "intro" -> "quiz" -> "submitting" -> "done" (or "error").
    let phase: "intro" | "quiz" | "submitting" | "done" | "error" = "intro";
    let idx = 0;
    let selectedKey: string | null = null;
    let revealed = false;
    let responses: RecordedResponse[] = [];
    let submitError = "";

    $: current = items[idx];
    $: isLast = idx >= items.length - 1;

    function begin(): void {
        phase = "quiz";
        idx = 0;
        responses = [];
        selectedKey = null;
        revealed = false;
    }

    function choose(key: string): void {
        if (revealed) {
            return;
        }
        selectedKey = key;
    }

    function reveal(): void {
        if (selectedKey === null) {
            return;
        }
        revealed = true;
    }

    function record(answered: boolean): void {
        const item = current;
        responses = [
            ...responses,
            {
                itemId: item.id,
                category: item.category,
                chosen: answered ? (selectedKey ?? "") : "",
                answered,
                // The client grades against the key the backend served; the
                // scorer only ever treats this as evidence for a prior.
                correct: answered ? selectedKey === item.answer : false,
                difficulty: item.difficulty,
            },
        ];
        selectedKey = null;
        revealed = false;
        if (isLast) {
            void submit();
        } else {
            idx += 1;
        }
    }

    async function submit(): Promise<void> {
        phase = "submitting";
        try {
            await scoreAndSeedDiagnostic({
                responses,
                mode: quiz?.mode ?? "short",
            });
            phase = "done";
        } catch (err) {
            submitError = String(err);
            phase = "error";
        }
    }

    function optionClass(key: string): string {
        if (!revealed) {
            return selectedKey === key ? "option selected" : "option";
        }
        if (key === current.answer) {
            return "option correct";
        }
        if (key === selectedKey) {
            return "option wrong";
        }
        return "option muted";
    }
</script>

<div class="diagnostic">
    {#if !available}
        <section class="panel warn">
            <h2>Diagnostic not available</h2>
            <p>
                The introductory diagnostic needs its question bank
                (<code>diagnostic_quiz.json</code>). It ships in
                <code>readymcat/diagnostic/</code>; place it next to your collection or
                open this page with a
                <code>?quiz=&lt;path&gt;</code>
                parameter.
            </p>
            {#if error}
                <p class="detail">{error}</p>
            {/if}
        </section>
    {:else if phase === "intro"}
        <section class="panel">
            <h1>{quiz?.title ?? "ReadyMCAT Introductory Diagnostic"}</h1>
            <p class="subtitle">
                A short quiz that samples every AAMC content category. Its only job is
                to personalize what you study first and where your learning starts.
            </p>
            <p class="honesty">
                <strong>This is not a test.</strong> There is no score, no percentile,
                and nothing here goes to your memory or readiness numbers — a short quiz
                is a starting <em>prior</em>, not a verdict. It just makes session one
                smarter. Answer what you can; skip what you don't know.
            </p>
            <p class="detail">
                {items.length} questions · about {items.length <= 31 ? "20–30" : "28–40"} minutes
            </p>
            <button class="primary" on:click={begin}>Begin diagnostic</button>
        </section>
    {:else if phase === "quiz" && current}
        <section class="panel">
            <div class="progress-head">
                <span class="cat">{current.category}</span>
                <span class="detail">Question {idx + 1} of {items.length}</span>
            </div>
            <div class="bar">
                <div class="fill" style:width={`${((idx + 1) / items.length) * 100}%`}></div>
            </div>

            <h2 class="stem">{current.stem}</h2>

            <div class="options">
                {#each current.options as option (option.key)}
                    <button
                        class={optionClass(option.key)}
                        disabled={revealed}
                        on:click={() => choose(option.key)}
                    >
                        <span class="key">{option.key}</span>
                        <span class="text">{option.text}</span>
                    </button>
                {/each}
            </div>

            {#if revealed}
                <div class="feedback" class:right={selectedKey === current.answer}>
                    <strong>
                        {selectedKey === current.answer ? "Correct" : "Not quite"}
                    </strong>
                    {#if current.rationale}
                        <p>{current.rationale}</p>
                    {/if}
                    {#if current.sourceUrl}
                        <p class="detail">
                            Review this concept for free:
                            <a href={current.sourceUrl} target="_blank" rel="noreferrer">
                                {current.sourceUrl}
                            </a>
                        </p>
                    {/if}
                </div>
            {/if}

            <div class="controls">
                <button class="ghost" on:click={() => record(false)}>Skip</button>
                {#if !revealed}
                    <button class="primary" disabled={selectedKey === null} on:click={reveal}>
                        Check answer
                    </button>
                {:else}
                    <button class="primary" on:click={() => record(true)}>
                        {isLast ? "Finish" : "Next question"}
                    </button>
                {/if}
            </div>
        </section>
    {:else if phase === "submitting"}
        <section class="panel">
            <h2>Personalizing your study path…</h2>
            <p class="detail">Turning your answers into a starting prior.</p>
        </section>
    {:else if phase === "done"}
        <section class="panel done">
            <h1>You're all set</h1>
            <p>
                Your study queue and learning path are now personalized to what you
                already know. High-yield topics you're weakest in will surface first,
                and known foundations won't be re-taught.
            </p>
            <p class="honesty">
                By design, we're <strong>not</strong> showing you a score. A short quiz is
                a prior, not a readiness verdict — your honest memory score appears on the
                dashboard only once there's enough real review evidence to back it up.
            </p>
            <button class="primary" on:click={() => bridgeCommand("close")}>
                Start studying
            </button>
        </section>
    {:else if phase === "error"}
        <section class="panel warn">
            <h2>Couldn't save your diagnostic</h2>
            <p class="detail">{submitError}</p>
            <button class="primary" on:click={submit}>Try again</button>
        </section>
    {/if}
</div>

<style lang="scss">
    .diagnostic {
        max-width: 720px;
        margin: 0 auto;
        padding: 1rem;
        color: var(--fg, #2c2c2c);
    }

    h1 {
        font-size: 1.6rem;
        margin-bottom: 0.35rem;
    }

    .subtitle {
        color: var(--fg-subtle, #66676b);
        margin-top: 0;
    }

    .panel {
        background: var(--canvas-elevated, #f7f7f9);
        border: 1px solid var(--border-subtle, #e0e0e3);
        border-radius: 10px;
        padding: 1.25rem 1.4rem;
        margin-bottom: 1rem;
    }

    .panel.warn {
        border-color: var(--flag1-fg, #e07a5f);
    }

    .honesty {
        background: var(--canvas-inset, #eef1f6);
        border-left: 3px solid var(--accent-card, #2d6cdf);
        padding: 0.6rem 0.85rem;
        border-radius: 6px;
        font-size: 0.92rem;
    }

    .detail {
        color: var(--fg-subtle, #66676b);
        font-size: 0.85rem;
    }

    .progress-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 0.4rem;
    }

    .cat {
        font-weight: 700;
        color: var(--accent-card, #2d6cdf);
    }

    .bar {
        background: var(--canvas-inset, #e9e9ec);
        border-radius: 999px;
        height: 8px;
        overflow: hidden;
        margin-bottom: 1rem;
    }

    .bar .fill {
        height: 100%;
        background: var(--accent-card, #2d6cdf);
        border-radius: 999px;
        transition: width 0.25s ease;
    }

    .stem {
        font-size: 1.15rem;
        line-height: 1.4;
        margin: 0 0 1rem;
    }

    .options {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }

    .option {
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
        text-align: left;
        padding: 0.7rem 0.85rem;
        border: 1px solid var(--border-subtle, #d7d7db);
        border-radius: 8px;
        background: var(--canvas, #fff);
        color: inherit;
        cursor: pointer;
        font-size: 0.98rem;
        transition:
            border-color 0.15s ease,
            background 0.15s ease;
    }

    .option:hover:not(:disabled) {
        border-color: var(--accent-card, #2d6cdf);
    }

    .option .key {
        font-weight: 700;
        min-width: 1.4em;
        color: var(--fg-subtle, #66676b);
    }

    .option.selected {
        border-color: var(--accent-card, #2d6cdf);
        background: var(--canvas-inset, #eef1f6);
    }

    .option.correct {
        border-color: #2e8b57;
        background: rgba(46, 139, 87, 0.12);
    }

    .option.wrong {
        border-color: var(--flag1-fg, #e07a5f);
        background: rgba(224, 122, 95, 0.12);
    }

    .option.muted {
        opacity: 0.6;
    }

    .feedback {
        border-radius: 8px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 1rem;
        background: rgba(224, 122, 95, 0.1);
    }

    .feedback.right {
        background: rgba(46, 139, 87, 0.1);
    }

    .feedback p {
        margin: 0.35rem 0 0;
        font-size: 0.92rem;
    }

    .controls {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
    }

    button {
        font-size: 0.95rem;
        padding: 0.55rem 1.1rem;
        border-radius: 8px;
        border: 1px solid transparent;
        cursor: pointer;
    }

    button.primary {
        background: var(--accent-card, #2d6cdf);
        color: #fff;
        font-weight: 600;
    }

    button.primary:disabled {
        opacity: 0.5;
        cursor: default;
    }

    button.ghost {
        background: transparent;
        border-color: var(--border-subtle, #d7d7db);
        color: var(--fg-subtle, #66676b);
    }

    .done h1 {
        color: var(--accent-card, #2d6cdf);
    }
</style>
