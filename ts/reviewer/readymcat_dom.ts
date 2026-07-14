// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

/* eslint
@typescript-eslint/no-explicit-any: "off",
 */

// Small DOM primitives shared by the ReadyMCAT reviewer overlays (mcq.ts,
// fr.ts, passage.ts and teach_on_miss.ts). Each overlay renders into the
// reviewer's #qa element, typesets any MathJax in it, and (for the three
// question overlays) builds prefixed action buttons and pulls the first link
// out of a card's Source. Those helpers were previously copy-pasted into each
// overlay; keeping them here means one definition to reason about — the
// produced DOM is byte-for-byte the same as before, just no longer duplicated.

declare const MathJax: any;

/** The reviewer's question/answer container the overlays render into. */
export function qaEl(): HTMLElement {
    return document.getElementById("qa")!;
}

/** Typeset any MathJax inside `el`, ignoring (non-fatal) typesetting errors. */
export async function typeset(el: HTMLElement): Promise<void> {
    try {
        if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
            if (MathJax.startup?.promise) {
                await MathJax.startup.promise;
            }
            MathJax.typesetClear?.();
            await MathJax.typesetPromise([el]);
        }
    } catch {
        // ignore math typesetting errors in the overlay
    }
}

/** First external http(s) link in some text, or null (used for Source links). */
export function firstUrl(text: string): string | null {
    const match = text.match(/https?:\/\/[^\s"'<>)]+/);
    return match ? match[0] : null;
}

/**
 * Whether a graded question card has a guiding sub-question ladder to run.
 *
 * ReadyMCAT withholds the answer on a first miss and offers the guiding
 * ladder instead (retrieve-before-reveal). That is only safe when a ladder
 * actually exists: with no rungs there is nothing to retrieve toward, so the
 * reviewer must fall back to the normal answer reveal rather than strand the
 * student behind a "start guiding questions" button that can't do anything.
 * For MCQ/free-response/passage cards the ladder is the note's own embedded
 * `Subquestions` (built into the card), so availability is simply whether that
 * list is non-empty.
 */
export function hasLadder(subquestions: unknown): boolean {
    return Array.isArray(subquestions) && subquestions.length > 0;
}

/**
 * A reviewer action button. `prefix` is the overlay's CSS class prefix (e.g.
 * "rmcq"), so the button gets the overlay's own `<prefix>-btn` styling; `cls`
 * is the variant ("primary" / "good" / "bad" / …). Always a type="button" so it
 * never submits an enclosing form.
 */
export function makeButton(
    prefix: string,
    label: string,
    cls: string,
    onClick: () => void,
): HTMLButtonElement {
    const button = document.createElement("button");
    button.className = `${prefix}-btn ${cls}`;
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
}
