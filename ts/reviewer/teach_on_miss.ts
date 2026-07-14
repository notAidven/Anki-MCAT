// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

/* eslint
@typescript-eslint/no-explicit-any: "off",
 */

// ReadyMCAT teach-on-miss UI (the guiding ladder ONLY).
//
// When a basic card is missed (question-side "Stuck? work it out"), the Python
// reviewer (qt/aqt/reviewer.py) calls `_teachOnMissStart(payload)` instead of
// revealing the back. This module runs a short guiding ladder one rung at a
// time and reports each rung's outcome to Python over bridgeCommand. Python owns
// scheduling (relearning), tagging, and logging.
//
// When the ladder finishes, this module does NOT reconstruct the flashcard — a
// reconstruction never matched Anki's native render. It hands control back to
// Python with `tom:reshow`; the reviewer then re-displays the REAL card through
// its normal `_showQuestion`/`_showAnswer` path (so the post-ladder card is
// byte-for-byte the original Anki design) and drives the reveal + self-grade
// from the bottom bar. It stays retrieve-BEFORE-reveal: the card's real answer
// is not shown until the ladder is done.
//
// A ladder rung comes in one of two shapes and is rendered accordingly:
//   * Authored `{q, a}` rung (curated `subquestions.json`): attempt -> reveal
//     sub-answer -> self-mark (Got it / Missed it).
//   * AI-generated MCQ rung `{question, options, correctIndex, explanation}`:
//     the student WORKS IT OUT by choosing — select an option -> immediate
//     correct/incorrect feedback + a one-line explanation -> next rung. This
//     reuses the same interaction pattern as ts/reviewer/mcq.ts.
import { bridgeCommand } from "@tslib/bridgecommand";

import { qaEl, typeset } from "./readymcat_dom";

/** A curated reveal-and-self-mark rung (authored `subquestions.json`). */
interface AuthoredRung {
    q: string;
    a: string;
}

/** An AI-generated interactive multiple-choice rung. */
interface McqRung {
    question: string;
    options: string[];
    correctIndex: number;
    explanation: string;
}

type Rung = AuthoredRung | McqRung;

/** An MCQ rung is discriminated by its `options` array (authored rungs lack it). */
function isMcqRung(rung: Rung): rung is McqRung {
    return Array.isArray((rung as McqRung).options);
}

interface TeachOnMissPayload {
    title: string;
    category: string;
    ladder: Rung[];
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
#qa .tom-options{display:flex;flex-direction:column;gap:.5em;margin:.4em 0 0;}
#qa .tom-option{display:flex;gap:.7em;align-items:flex-start;cursor:pointer;
    text-align:left;font-size:.98em;border-radius:9px;padding:.7em .9em;
    border:1px solid var(--border,#0004);background:var(--canvas,#8080800f);color:inherit;}
#qa .tom-option:hover:not(:disabled){filter:brightness(1.06);}
#qa .tom-option.selected{border-color:var(--accent,#2186eb);
    box-shadow:0 0 0 1px var(--accent,#2186eb) inset;}
#qa .tom-option.correct{border-color:#2e7d32;background:#2e7d3222;}
#qa .tom-option.wrong{border-color:#c62828;background:#c6282822;}
#qa .tom-option:disabled{cursor:default;opacity:1;}
#qa .tom-letter{font-weight:700;opacity:.7;min-width:1.3em;}
#qa .tom-opt-text{flex:1;}
#qa .tom-explanation{border-radius:10px;padding:.9em 1.1em;margin:.9em 0;
    border-left:4px solid var(--accent,#2186eb);background:var(--canvas-elevated,#80808014);}
#qa .tom-row{display:flex;gap:.6em;flex-wrap:wrap;margin-top:.9em;}
#qa .tom-btn{cursor:pointer;font-size:.95em;font-weight:600;border-radius:8px;
    padding:.55em 1.1em;border:1px solid var(--border,#0004);
    background:var(--canvas,#8080801a);color:inherit;}
#qa .tom-btn:hover{filter:brightness(1.08);}
#qa .tom-btn.primary{background:var(--accent,#2186eb);color:#fff;border-color:transparent;}
#qa .tom-btn.good{background:#2e7d32;color:#fff;border-color:transparent;}
#qa .tom-btn.bad{background:#c62828;color:#fff;border-color:transparent;}
#qa .tom-loading{display:flex;flex-direction:column;align-items:center;gap:.7em;text-align:center;}
#qa .tom-spinner{width:26px;height:26px;border-radius:50%;
    border:3px solid var(--border,#0003);border-top-color:var(--accent,#2186eb);
    animation:tom-spin .8s linear infinite;}
@keyframes tom-spin{to{transform:rotate(360deg);}}
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
        // Ladder done: hand back to Python, which re-shows the REAL card through
        // the normal reviewer render path (byte-for-byte the original Anki card)
        // and drives the reveal + self-grade from the bottom bar.
        bridgeCommand("tom:reshow");
        return;
    }
    const rung = payload.ladder[rungIndex];
    if (isMcqRung(rung)) {
        renderMcqRung(rung);
    } else {
        renderAuthoredRung(rung);
    }
}

// Authored rung (curated `subquestions.json`): retrieve, then reveal + self-mark.
function renderAuthoredRung(rung: AuthoredRung): void {
    const wrap = newWrap(`Guiding question ${rungIndex + 1} of ${payload!.ladder.length}`);

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

// AI-generated MCQ rung: select an option -> feedback + explanation -> next.
// Mirrors the interaction pattern of ts/reviewer/mcq.ts's guiding rungs, but
// reports over the shared `tom:*` protocol (Python maps got/missed to logging).
function renderMcqRung(rung: McqRung): void {
    const total = payload!.ladder.length;
    const rungAt = rungIndex;
    const wrap = newWrap(`Guiding question ${rungAt + 1} of ${total}`);

    const card = document.createElement("div");
    card.className = "tom-card";
    const stem = document.createElement("div");
    stem.className = "tom-q";
    // AI-generated ladder content is untrusted (the model's input includes
    // user-imported card text): render it as plain text, never HTML.
    stem.textContent = rung.question;
    card.appendChild(stem);
    wrap.appendChild(card);

    let selected = -1;
    let submitted = false;
    const optButtons: HTMLButtonElement[] = [];

    const checkBtn = makeButton("Check", "primary", () => {
        if (submitted || selected < 0) {
            return;
        }
        submitted = true;
        checkBtn.remove();
        const correct = selected === rung.correctIndex;
        optButtons.forEach((button, index) => {
            button.disabled = true;
            if (index === rung.correctIndex) {
                button.classList.add("correct");
            }
            if (index === selected && !correct) {
                button.classList.add("wrong");
            }
        });
        bridgeCommand(`tom:mark:${correct ? "got" : "missed"}:${rungAt}`);
        showRungExplanation(wrap, correct, rung.explanation);
        const last = rungAt >= total - 1;
        const proceed = document.createElement("div");
        proceed.className = "tom-row";
        proceed.appendChild(
            makeButton(
                last ? "Back to the question" : "Next guiding question",
                "primary",
                () => {
                    rungIndex = rungAt + 1;
                    renderRung();
                },
            ),
        );
        wrap.appendChild(proceed);
    });
    checkBtn.disabled = true;

    const list = document.createElement("div");
    list.className = "tom-options";
    rung.options.forEach((option, index) => {
        const button = document.createElement("button");
        button.className = "tom-option";
        button.type = "button";
        const letter = document.createElement("span");
        letter.className = "tom-letter";
        letter.textContent = String.fromCharCode(65 + index);
        const text = document.createElement("span");
        text.className = "tom-opt-text";
        // Untrusted AI-generated option text -> plain text only, never HTML.
        text.textContent = option;
        button.append(letter, text);
        button.addEventListener("click", () => {
            if (submitted) {
                return;
            }
            selected = index;
            optButtons.forEach((other, otherIndex) => {
                other.classList.toggle("selected", otherIndex === index);
            });
            checkBtn.disabled = false;
        });
        optButtons.push(button);
        list.appendChild(button);
    });
    wrap.appendChild(list);

    const row = document.createElement("div");
    row.className = "tom-row";
    row.appendChild(checkBtn);
    wrap.appendChild(row);

    void typeset(wrap);
}

function showRungExplanation(
    wrap: HTMLElement,
    correct: boolean,
    text: string,
): void {
    if (!text) {
        return;
    }
    const box = document.createElement("div");
    box.className = "tom-explanation";
    const label = document.createElement("div");
    label.className = "tom-label";
    label.textContent = correct ? "Correct" : "Explanation";
    const body = document.createElement("div");
    body.className = "tom-a";
    // Untrusted AI-generated explanation text -> plain text only, never HTML.
    body.textContent = text;
    box.append(label, body);
    wrap.appendChild(box);
    void typeset(box);
}

function revealRung(wrap: HTMLElement, rung: AuthoredRung): void {
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

export function _teachOnMissStart(data: TeachOnMissPayload): void {
    ensureStyle();
    payload = data;
    rungIndex = 0;
    renderRung();
}

// Shown while a ladder is being generated at runtime (the AI feature) for a
// card that has no authored ladder. The Python reviewer calls this before
// kicking off background generation, then calls `_teachOnMissStart` with the
// generated ladder when it arrives (or falls back to a normal reschedule).
export function _teachOnMissLoading(): void {
    ensureStyle();
    const wrap = document.createElement("div");
    wrap.className = "tom-wrap";

    const head = document.createElement("div");
    head.className = "tom-head";
    const badge = document.createElement("span");
    badge.className = "tom-badge";
    badge.textContent = "ReadyMCAT \u00b7 Teach-on-miss";
    head.appendChild(badge);
    wrap.appendChild(head);

    const card = document.createElement("div");
    card.className = "tom-card tom-loading";
    const spinner = document.createElement("div");
    spinner.className = "tom-spinner";
    const label = document.createElement("div");
    label.className = "tom-q";
    label.textContent = "Building your guiding questions\u2026";
    const hint = document.createElement("div");
    hint.className = "tom-hint";
    hint.textContent = "Generating a short retrieval ladder from this card.";
    card.append(spinner, label, hint);
    wrap.appendChild(card);

    qaEl().replaceChildren(wrap);
}
