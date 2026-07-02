<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<!--
    Small, reusable info affordance for ReadyMCAT app-native terms and stats.

    Reveals a styled popover explaining WHAT a term means and HOW it is measured.
    Opens on hover, on keyboard focus, and on click/tap (click pins it open for
    touch users). Dismisses on mouse-leave, blur, Escape, or an outside click.

    Accessibility:
      * the trigger is a real, keyboard-focusable <button>
      * it carries aria-expanded and points at the popover via aria-describedby
      * the popover is role="tooltip"

    Two trigger looks, both matching the dashboard's card/chip styling:
      * variant="text"  — the label (slotted) with a dotted underline + ⓘ glyph
      * variant="icon"  — just a small ⓘ button, to sit beside an existing label
-->
<script lang="ts" context="module">
    // Stable, unique ids without relying on Math.random (SSR-safe, no hydration
    // mismatch): one incrementing counter shared across all instances.
    let idCounter = 0;
</script>

<script lang="ts">
    import { onDestroy, tick } from "svelte";

    import type { GlossaryEntry } from "./glossary";

    /** The definition to explain. */
    export let entry: GlossaryEntry;
    /** Trigger appearance. "text" wraps a slotted label; "icon" is a lone ⓘ. */
    export let variant: "text" | "icon" = "text";

    const uid = `rmcat-tip-${++idCounter}`;

    let open = false;
    // Pinned = opened by click/tap; survives mouse-leave until an explicit
    // dismiss (outside click, Escape, blur). Plain hover/focus does not pin.
    let pinned = false;

    let rootEl: HTMLSpanElement;
    let triggerEl: HTMLButtonElement;
    let popEl: HTMLDivElement | null = null;

    let posTop = 0;
    let posLeft = 0;
    let listening = false;

    // Render the popover as a direct child of <body> so it can never be clipped
    // or out-stacked by the card/tile it lives in; positioning is fixed anyway.
    function portal(node: HTMLElement): { destroy(): void } {
        document.body.appendChild(node);
        return {
            destroy() {
                node.remove();
            },
        };
    }

    async function place(): Promise<void> {
        await tick();
        if (!triggerEl || !popEl) {
            return;
        }
        const r = triggerEl.getBoundingClientRect();
        const p = popEl.getBoundingClientRect();
        const gap = 8;
        const margin = 8;
        const vw = document.documentElement.clientWidth;
        const vh = document.documentElement.clientHeight;

        // Prefer below the trigger; flip above when it would overflow the bottom.
        let top = r.bottom + gap;
        if (top + p.height > vh - margin && r.top - gap - p.height >= margin) {
            top = r.top - gap - p.height;
        }
        // Centre on the trigger, then clamp inside the viewport.
        let left = r.left + r.width / 2 - p.width / 2;
        left = Math.min(Math.max(margin, left), vw - p.width - margin);

        posTop = Math.round(top);
        posLeft = Math.round(left);
    }

    function onGlobalPointerDown(event: PointerEvent): void {
        const target = event.target as Node;
        const inside =
            (rootEl && rootEl.contains(target)) || (popEl && popEl.contains(target));
        if (!inside) {
            close();
        }
    }
    function onReposition(): void {
        if (open) {
            void place();
        }
    }
    function startListening(): void {
        if (listening) {
            return;
        }
        listening = true;
        document.addEventListener("pointerdown", onGlobalPointerDown, true);
        window.addEventListener("scroll", onReposition, true);
        window.addEventListener("resize", onReposition);
    }
    function stopListening(): void {
        if (!listening) {
            return;
        }
        listening = false;
        document.removeEventListener("pointerdown", onGlobalPointerDown, true);
        window.removeEventListener("scroll", onReposition, true);
        window.removeEventListener("resize", onReposition);
    }

    function show(): void {
        open = true;
        startListening();
        void place();
    }
    function close(): void {
        open = false;
        pinned = false;
        stopListening();
    }

    function onEnter(): void {
        if (!open) {
            show();
        }
    }
    function onLeave(): void {
        if (!pinned) {
            close();
        }
    }
    function onFocus(): void {
        show();
    }
    function onBlur(event: FocusEvent): void {
        // Keep open if focus moved to something inside our own root.
        const next = event.relatedTarget as Node | null;
        if (next && rootEl && rootEl.contains(next)) {
            return;
        }
        close();
    }
    function onClick(): void {
        if (open && pinned) {
            close();
        } else {
            pinned = true;
            show();
        }
    }
    function onKeydown(event: KeyboardEvent): void {
        if (event.key === "Escape" && open) {
            event.preventDefault();
            event.stopPropagation();
            close();
            triggerEl?.focus();
        }
    }

    onDestroy(stopListening);
</script>

<span class="rmcat-tip-root" bind:this={rootEl}>
    <button
        type="button"
        class="rmcat-tip"
        class:as-text={variant === "text"}
        class:as-icon={variant === "icon"}
        class:open
        bind:this={triggerEl}
        aria-expanded={open}
        aria-describedby={open ? uid : undefined}
        aria-label={variant === "icon" ? `About ${entry.title}` : undefined}
        title={variant === "icon" ? `About ${entry.title}` : undefined}
        on:mouseenter={onEnter}
        on:mouseleave={onLeave}
        on:focus={onFocus}
        on:blur={onBlur}
        on:click|stopPropagation={onClick}
        on:keydown={onKeydown}
    >
        {#if variant === "text"}<span class="rmcat-tip-label"><slot /></span>{/if}
        <span class="rmcat-tip-glyph" aria-hidden="true">
            <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
            >
                <circle cx="12" cy="12" r="9" />
                <circle cx="12" cy="8" r="1" fill="currentColor" stroke="none" />
                <line x1="12" y1="11.5" x2="12" y2="16.5" />
            </svg>
        </span>
    </button>

    {#if open}
        <div
            bind:this={popEl}
            use:portal
            id={uid}
            role="tooltip"
            class="rmcat-pop"
            style:top="{posTop}px"
            style:left="{posLeft}px"
        >
            <div class="rmcat-pop-title">{entry.title}</div>
            <p class="rmcat-pop-what">{entry.what}</p>
            {#if entry.how}
                <p class="rmcat-pop-line">
                    <span class="rmcat-pop-key">How</span>
                    {entry.how}
                </p>
            {/if}
            {#if entry.note}
                <p class="rmcat-pop-note">{entry.note}</p>
            {/if}
        </div>
    {/if}
</span>

<style lang="scss">
    .rmcat-tip-root {
        display: inline;
    }

    /* Trigger: an unstyled button that inherits the surrounding text look
       (so an uppercase eyebrow label stays uppercase, an inline term stays
       inline), plus a discoverable info affordance. */
    .rmcat-tip {
        display: inline;
        margin: 0;
        padding: 0;
        border: none;
        background: none;
        font: inherit;
        color: inherit;
        text-align: inherit;
        letter-spacing: inherit;
        text-transform: inherit;
        cursor: help;
    }

    .rmcat-tip.as-text .rmcat-tip-label {
        text-decoration: underline dotted;
        text-decoration-thickness: 1px;
        text-underline-offset: 0.15em;
    }

    .rmcat-tip-glyph {
        display: inline-flex;
        vertical-align: baseline;
        width: 0.9em;
        height: 0.9em;
        margin-left: 0.18em;
        translate: 0 0.1em;
        opacity: 0.55;
        transition: opacity 0.12s ease;
    }

    .rmcat-tip.as-icon {
        /* stand-alone icon sits a touch larger, with room from preceding text */
        margin-left: 0.3em;
        cursor: help;
    }

    .rmcat-tip.as-icon .rmcat-tip-glyph {
        width: 1em;
        height: 1em;
        margin-left: 0;
        translate: 0 0.12em;
    }

    .rmcat-tip-glyph svg {
        width: 100%;
        height: 100%;
    }

    .rmcat-tip:hover .rmcat-tip-glyph,
    .rmcat-tip:focus-visible .rmcat-tip-glyph,
    .rmcat-tip.open .rmcat-tip-glyph {
        opacity: 1;
        color: var(--accent-card, #2d6cdf);
    }

    .rmcat-tip:focus-visible {
        outline: 2px solid var(--accent-card, #2d6cdf);
        outline-offset: 2px;
        border-radius: 3px;
    }

    /* Popover: matches the dashboard card look. Rendered position:fixed so it
       escapes any card/tile overflow clipping and viewport edges. Explicitly
       resets text styling it would otherwise inherit from eyebrow/chip labels. */
    .rmcat-pop {
        position: fixed;
        z-index: 9999;
        width: max-content;
        max-width: 280px;
        padding: 0.6rem 0.7rem;
        background: var(--canvas-elevated, #fff);
        color: var(--fg, #1a1a1a);
        border: 1px solid var(--border-subtle, #d5d9e0);
        border-radius: var(--border-radius-medium, 10px);
        box-shadow: 0 8px 28px -10px
            color-mix(in srgb, var(--shadow-subtle, #000) 60%, transparent);
        text-align: left;
        text-transform: none;
        letter-spacing: normal;
        font-style: normal;
        font-weight: 400;
        font-size: 0.78rem;
        line-height: 1.42;
        white-space: normal;
    }

    .rmcat-pop-title {
        font-weight: 800;
        font-size: 0.8rem;
        margin-bottom: 0.2rem;
        color: var(--fg, #1a1a1a);
    }

    .rmcat-pop-what {
        margin: 0;
        color: var(--fg, #1a1a1a);
    }

    .rmcat-pop-line {
        margin: 0.35rem 0 0;
        color: var(--fg-subtle, #5b6472);
    }

    .rmcat-pop-key {
        font-weight: 700;
        color: var(--fg, #1a1a1a);
        margin-right: 0.15rem;
    }

    .rmcat-pop-note {
        margin: 0.4rem 0 0;
        padding-top: 0.4rem;
        border-top: 1px dashed var(--border-subtle, #d5d9e0);
        color: var(--fg-subtle, #5b6472);
        font-size: 0.74rem;
    }
</style>
