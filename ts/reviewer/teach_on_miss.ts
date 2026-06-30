// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

/* eslint
@typescript-eslint/no-explicit-any: "off",
 */

// ReadyMCAT teach-on-miss UI.
//
// When a card belonging to a curated high-value concept is graded "Again", the
// Python reviewer (qt/aqt/reviewer.py) calls `_teachOnMissStart(payload)` instead
// of revealing the back. This module runs the pre-authored guiding sub-question
// ladder one rung at a time (attempt -> reveal -> self-mark), then re-shows the
// MAIN question, and finally reports the outcome to Python over bridgeCommand.
// Python owns scheduling (relearning), tagging, and logging.

import { bridgeCommand } from "@tslib/bridgecommand";

declare const MathJax: any;

interface Rung {
    q: string;
    a: string;
}

interface TeachOnMissPayload {
    title: string;
    category: string;
    ladder: Rung[];
    mainQuestion: string;
    mainAnswer: string;
    resource: { label?: string; url?: string };
}

let payload: TeachOnMissPayload | null = null;
let rungIndex = 0;

const STYLE_ID = "readymcat-tom-style";

const CSS = `
#qa .tom-wrap{max-width:720px;margin:1.2em auto;text-align:left;line-height:1.5;}
#qa .tom-head{display:flex;align-items:center;gap:.6em;flex-wrap:wrap;
    padding-bottom:.6em;margin-bottom:1em;border-bottom:1px solid var(--border,#0003);}
#qa .tom-badge{font-size:.72em;font-weight:700;letter-spacing:.04em;
    text-transform:uppercase;padding:.25em .6em;border-radius:999px;
    background:var(--accent,#2186eb);color:#fff;white-space:nowrap;}
#qa .tom-title{font-weight:600;}
#qa .tom-step{margin-left:auto;font-size:.82em;opacity:.7;}
#qa .tom-card{border:1px solid var(--border,#0003);border-radius:10px;
    padding:1em 1.1em;margin:.8em 0;background:var(--canvas-elevated,#80808014);}
#qa .tom-label{font-size:.74em;font-weight:700;text-transform:uppercase;
    letter-spacing:.04em;opacity:.6;margin-bottom:.35em;}
#qa .tom-q{font-size:1.08em;font-weight:600;}
#qa .tom-a{margin-top:.2em;}
#qa .tom-hint{font-size:.85em;opacity:.65;margin:.5em 0;}
#qa .tom-row{display:flex;gap:.6em;flex-wrap:wrap;margin-top:.9em;}
#qa .tom-btn{cursor:pointer;font-size:.95em;font-weight:600;border-radius:8px;
    padding:.55em 1.1em;border:1px solid var(--border,#0004);
    background:var(--canvas,#8080801a);color:inherit;}
#qa .tom-btn:hover{filter:brightness(1.08);}
#qa .tom-btn.primary{background:var(--accent,#2186eb);color:#fff;border-color:transparent;}
#qa .tom-btn.good{background:#2e7d32;color:#fff;border-color:transparent;}
#qa .tom-btn.bad{background:#c62828;color:#fff;border-color:transparent;}
#qa .tom-note{border-radius:10px;padding:.9em 1.1em;margin:.9em 0;
    border-left:4px solid var(--accent,#2186eb);background:var(--canvas-elevated,#80808014);}
#qa .tom-note.struggle{border-left-color:#c62828;}
#qa .tom-note.spaced{border-left-color:#2e7d32;}
#qa .tom-res a{color:var(--accent,#2186eb);text-decoration:underline;cursor:pointer;}
#qa .tom-main{border:1px dashed var(--border,#0005);border-radius:10px;padding:1em;}
`;

function ensureStyle(): void {
    if (document.getElementById(STYLE_ID)) {
        return;
    }
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = CSS;
    document.head.appendChild(style);
}

function qaEl(): HTMLElement {
    return document.getElementById("qa")!;
}

async function typeset(el: HTMLElement): Promise<void> {
    try {
        if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
            if (MathJax.startup?.promise) {
                await MathJax.startup.promise;
            }
            MathJax.typesetClear?.();
            await MathJax.typesetPromise([el]);
        }
    } catch {
        // ignore math typesetting errors in the teach-on-miss overlay
    }
}

function makeButton(
    label: string,
    cls: string,
    onClick: () => void,
): HTMLButtonElement {
    const button = document.createElement("button");
    button.className = `tom-btn ${cls}`;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
}

function makeHeader(stepText: string): HTMLElement {
    const head = document.createElement("div");
    head.className = "tom-head";

    const badge = document.createElement("span");
    badge.className = "tom-badge";
    badge.textContent = "ReadyMCAT \u00b7 Teach-on-miss";

    const title = document.createElement("span");
    title.className = "tom-title";
    title.textContent = payload!.title;

    const step = document.createElement("span");
    step.className = "tom-step";
    step.textContent = stepText;

    head.append(badge, title, step);
    return head;
}

function newWrap(stepText: string): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "tom-wrap";
    wrap.appendChild(makeHeader(stepText));
    qaEl().replaceChildren(wrap);
    return wrap;
}

function renderRung(): void {
    if (!payload) {
        return;
    }
    if (rungIndex >= payload.ladder.length) {
        renderMain();
        return;
    }
    const rung = payload.ladder[rungIndex];
    const wrap = newWrap(`Guiding question ${rungIndex + 1} of ${payload.ladder.length}`);

    const card = document.createElement("div");
    card.className = "tom-card";
    const label = document.createElement("div");
    label.className = "tom-label";
    label.textContent = "Try to answer this first";
    const question = document.createElement("div");
    question.className = "tom-q";
    question.textContent = rung.q;
    card.append(label, question);
    wrap.appendChild(card);

    const hint = document.createElement("div");
    hint.className = "tom-hint";
    hint.textContent = "Retrieve it yourself, then reveal the answer.";
    wrap.appendChild(hint);

    const row = document.createElement("div");
    row.className = "tom-row";
    row.appendChild(
        makeButton("Reveal sub-answer", "primary", () => revealRung(wrap, rung)),
    );
    wrap.appendChild(row);
}

function revealRung(wrap: HTMLElement, rung: Rung): void {
    // remove the reveal row + hint, show the answer and self-mark buttons
    wrap.querySelector(".tom-row")?.remove();
    wrap.querySelector(".tom-hint")?.remove();

    const answer = document.createElement("div");
    answer.className = "tom-card";
    const label = document.createElement("div");
    label.className = "tom-label";
    label.textContent = "Sub-answer";
    const text = document.createElement("div");
    text.className = "tom-a";
    text.textContent = rung.a;
    answer.append(label, text);
    wrap.appendChild(answer);

    const prompt = document.createElement("div");
    prompt.className = "tom-hint";
    prompt.textContent = "Did you retrieve this correctly?";
    wrap.appendChild(prompt);

    const row = document.createElement("div");
    row.className = "tom-row";
    row.appendChild(makeButton("Got it", "good", () => markRung(true)));
    row.appendChild(makeButton("Missed it", "bad", () => markRung(false)));
    wrap.appendChild(row);
}

function markRung(got: boolean): void {
    bridgeCommand(`tom:mark:${got ? "got" : "missed"}:${rungIndex}`);
    rungIndex += 1;
    renderRung();
}

function renderMain(): void {
    if (!payload) {
        return;
    }
    const wrap = newWrap("Back to the original question");

    const intro = document.createElement("div");
    intro.className = "tom-hint";
    intro.textContent = "Now attempt the original card again, with the scaffolding fresh.";
    wrap.appendChild(intro);

    const main = document.createElement("div");
    main.className = "tom-main";
    main.innerHTML = payload.mainQuestion;
    wrap.appendChild(main);
    void typeset(main);

    const row = document.createElement("div");
    row.className = "tom-row";
    row.appendChild(makeButton("Show answer", "primary", () => revealMain(wrap)));
    wrap.appendChild(row);
}

function revealMain(wrap: HTMLElement): void {
    if (!payload) {
        return;
    }
    wrap.querySelector(".tom-row")?.remove();

    const answer = document.createElement("div");
    answer.className = "tom-main";
    answer.innerHTML = payload.mainAnswer;
    wrap.appendChild(answer);
    void typeset(answer);

    const prompt = document.createElement("div");
    prompt.className = "tom-hint";
    prompt.textContent = "Did you recall the original card correctly this time?";
    wrap.appendChild(prompt);

    const row = document.createElement("div");
    row.className = "tom-row";
    row.appendChild(
        makeButton("I recalled it correctly", "good", () => finishMain(wrap, true)),
    );
    row.appendChild(
        makeButton("I missed it again", "bad", () => finishMain(wrap, false)),
    );
    wrap.appendChild(row);
}

function finishMain(wrap: HTMLElement, correct: boolean): void {
    if (!payload) {
        return;
    }
    bridgeCommand(`tom:result:${correct ? "correct" : "wrong"}`);
    wrap.querySelector(".tom-row")?.remove();
    wrap.querySelector(".tom-hint")?.remove();

    const note = document.createElement("div");
    if (correct) {
        note.className = "tom-note spaced";
        note.innerHTML = "<strong>Not mastered yet.</strong> Getting it right seconds after the "
            + "scaffold isn't readiness. This concept is scheduled for spaced "
            + "re-retrieval \u2014 you'll need to recall it again in a later session "
            + "for it to count.";
    } else {
        note.className = "tom-note struggle";
        note.innerHTML = "<strong>Here's the full answer \u2014 earned through real retrieval.</strong> "
            + "This concept is flagged as struggling and scheduled for aggressive early "
            + "re-retrieval; it'll return fresh next session.";
        const url = payload.resource?.url;
        if (url) {
            const res = document.createElement("div");
            res.className = "tom-res";
            res.style.marginTop = ".6em";
            const label = payload.resource?.label || "Review this concept";
            const link = document.createElement("a");
            link.textContent = `\u2192 Needs content review: ${label}`;
            link.addEventListener("click", (event) => {
                event.preventDefault();
                bridgeCommand("tom:resource");
            });
            res.appendChild(link);
            note.appendChild(res);
        }
    }
    wrap.appendChild(note);

    const row = document.createElement("div");
    row.className = "tom-row";
    row.appendChild(
        makeButton("Continue", "primary", () => bridgeCommand("tom:continue")),
    );
    wrap.appendChild(row);
}

export function _teachOnMissStart(data: TeachOnMissPayload): void {
    ensureStyle();
    payload = data;
    rungIndex = 0;
    renderRung();
}
