// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

/* eslint
@typescript-eslint/no-explicit-any: "off",
 */

// ReadyMCAT free-response (type-in) reviewer + per-question teach-on-miss UI.
//
// When the desktop reviewer (qt/aqt/reviewer.py) shows a card that uses the
// "ReadyMCAT FreeResponse" note type, it calls `_frStart(payload)` with the
// prompt, the accepted answers / key terms used to auto-grade a typed answer,
// the model answer + explanation, and the card's own guiding sub-questions.
// Grading mirrors the canonical Python grader (see fr_grade.ts); this module
// renders the interactive item and reports outcomes to Python over
// bridgeCommand (Python owns grading into FSRS, tagging and logging):
//
//   answer correct first try  -> `fr:first:correct`  -> model + explanation -> Continue
//   answer wrong              -> `fr:first:wrong`     -> guiding ladder (type-in)
//     each sub-question:  submit -> reveal -> `fr:sub:<rung>:<got|missed>`
//     ladder done         -> re-ask the MAIN prompt
//       correct now       -> `fr:reattempt:correct` (not mastered -> spaced)
//       wrong again       -> `fr:reattempt:wrong`   (reveal + flag struggling)
//   Continue -> `fr:continue`  (always ends gracefully; no loops)

import { bridgeCommand } from "@tslib/bridgecommand";

import { gradeFreeResponse } from "./fr_grade";

declare const MathJax: any;

interface FrSubQuestion {
    stem: string;
    accepted_answers: string[];
    key_terms: string[];
    explanation: string;
}

interface FrPayload {
    prompt: string;
    acceptedAnswers: string[];
    keyTerms: string[];
    modelAnswer: string;
    explanation: string;
    subtopic: string;
    source: string;
    subquestions: FrSubQuestion[];
}

let payload: FrPayload | null = null;
let ladderIndex = 0;

const STYLE_ID = "readymcat-fr-style";

const CSS = `
#qa .rmfr-wrap{max-width:720px;margin:1.2em auto;text-align:left;line-height:1.5;}
#qa .rmfr-head{display:flex;align-items:center;gap:.6em;flex-wrap:wrap;
    padding-bottom:.6em;margin-bottom:1em;border-bottom:1px solid var(--border,#0003);}
#qa .rmfr-badge{font-size:.72em;font-weight:700;letter-spacing:.04em;
    text-transform:uppercase;padding:.25em .6em;border-radius:999px;
    background:var(--accent,#2186eb);color:#fff;white-space:nowrap;}
#qa .rmfr-title{font-weight:600;}
#qa .rmfr-step{margin-left:auto;font-size:.82em;opacity:.7;}
#qa .rmfr-card{border:1px solid var(--border,#0003);border-radius:10px;
    padding:1em 1.1em;margin:.4em 0 1em;background:var(--canvas-elevated,#80808014);}
#qa .rmfr-stem{font-size:1.08em;font-weight:600;}
#qa .rmfr-input{width:100%;box-sizing:border-box;font-size:1em;margin:.6em 0 .2em;
    padding:.6em .7em;border-radius:9px;border:1px solid var(--border,#0004);
    background:var(--canvas,#8080800f);color:inherit;}
#qa .rmfr-input:focus{outline:none;border-color:var(--accent,#2186eb);
    box-shadow:0 0 0 1px var(--accent,#2186eb) inset;}
#qa .rmfr-input.correct{border-color:#2e7d32;background:#2e7d3222;}
#qa .rmfr-input.wrong{border-color:#c62828;background:#c6282822;}
#qa .rmfr-row{display:flex;gap:.6em;flex-wrap:wrap;margin-top:.9em;}
#qa .rmfr-btn{cursor:pointer;font-size:.95em;font-weight:600;border-radius:8px;
    padding:.55em 1.1em;border:1px solid var(--border,#0004);
    background:var(--canvas,#8080801a);color:inherit;}
#qa .rmfr-btn:hover:not(:disabled){filter:brightness(1.08);}
#qa .rmfr-btn:disabled{opacity:.45;cursor:default;}
#qa .rmfr-btn.primary{background:var(--accent,#2186eb);color:#fff;border-color:transparent;}
#qa .rmfr-label{font-size:.74em;font-weight:700;text-transform:uppercase;
    letter-spacing:.04em;opacity:.6;margin-bottom:.35em;}
#qa .rmfr-verdict{font-weight:700;margin:.6em 0 .2em;}
#qa .rmfr-verdict.correct{color:#2e7d32;}
#qa .rmfr-verdict.wrong{color:#c62828;}
#qa .rmfr-explanation{border-radius:10px;padding:.9em 1.1em;margin:.9em 0;
    border-left:4px solid var(--accent,#2186eb);background:var(--canvas-elevated,#80808014);}
#qa .rmfr-note{border-radius:10px;padding:.9em 1.1em;margin:.9em 0;
    border-left:4px solid var(--accent,#2186eb);background:var(--canvas-elevated,#80808014);}
#qa .rmfr-note.struggle{border-left-color:#c62828;}
#qa .rmfr-note.spaced{border-left-color:#2e7d32;}
#qa .rmfr-model{margin:.4em 0;}
#qa .rmfr-accepted{margin:.2em 0;font-size:.9em;opacity:.85;}
#qa .rmfr-res{margin:.4em 0 .2em;}
#qa .rmfr-res a{color:var(--accent,#2186eb);text-decoration:underline;cursor:pointer;}
#qa .rmfr-subtopic{margin-top:.8em;font-size:.78em;opacity:.6;
    text-transform:uppercase;letter-spacing:.04em;}
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
        // ignore math typesetting errors in the free-response overlay
    }
}

function makeButton(
    label: string,
    cls: string,
    onClick: () => void,
): HTMLButtonElement {
    const button = document.createElement("button");
    button.className = `rmfr-btn ${cls}`;
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
}

function newWrap(title: string, stepText: string): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "rmfr-wrap";

    const head = document.createElement("div");
    head.className = "rmfr-head";
    const badge = document.createElement("span");
    badge.className = "rmfr-badge";
    badge.textContent = "ReadyMCAT";
    const titleEl = document.createElement("span");
    titleEl.className = "rmfr-title";
    titleEl.textContent = title;
    const step = document.createElement("span");
    step.className = "rmfr-step";
    step.textContent = stepText;
    head.append(badge, titleEl, step);

    wrap.appendChild(head);
    qaEl().replaceChildren(wrap);
    return wrap;
}

interface QuestionConfig {
    title: string;
    step: string;
    stem: string;
    accepted: string[];
    keyTerms: string[];
    submitLabel: string;
    afterSubmit: (value: string, correct: boolean, wrap: HTMLElement) => void;
}

function renderFrQuestion(config: QuestionConfig): void {
    const wrap = newWrap(config.title, config.step);

    const card = document.createElement("div");
    card.className = "rmfr-card";
    const stem = document.createElement("div");
    stem.className = "rmfr-stem";
    stem.innerHTML = config.stem;
    card.appendChild(stem);

    const input = document.createElement("input");
    input.className = "rmfr-input";
    input.type = "text";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.placeholder = "Type your answer, then submit";
    card.appendChild(input);
    wrap.appendChild(card);

    let submitted = false;
    const submit = (): void => {
        if (submitted) {
            return;
        }
        submitted = true;
        input.disabled = true;
        submitBtn.disabled = true;
        submitBtn.remove();
        const correct = gradeFreeResponse(
            input.value,
            config.accepted,
            config.keyTerms,
        );
        input.classList.add(correct ? "correct" : "wrong");
        const verdict = document.createElement("div");
        verdict.className = `rmfr-verdict ${correct ? "correct" : "wrong"}`;
        verdict.textContent = correct ? "Correct" : "Not quite";
        card.appendChild(verdict);
        config.afterSubmit(input.value, correct, wrap);
    };

    const submitBtn = makeButton(config.submitLabel, "primary", submit);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            submit();
        }
    });

    const row = document.createElement("div");
    row.className = "rmfr-row";
    row.appendChild(submitBtn);
    wrap.appendChild(row);

    void typeset(wrap);
    input.focus();
}

function showAccepted(wrap: HTMLElement, accepted: string[]): void {
    const clean = (accepted ?? []).filter((a) => {
        const low = a.trim().toLowerCase();
        return low && !low.startsWith("tolerance") && !low.startsWith("unit");
    });
    if (clean.length === 0) {
        return;
    }
    const box = document.createElement("div");
    box.className = "rmfr-accepted";
    box.innerHTML = `<b>Accepted:</b> ${clean.slice(0, 6).join(" · ")}`;
    wrap.appendChild(box);
}

function showExplanation(
    wrap: HTMLElement,
    label: string,
    text: string,
): void {
    if (!text) {
        return;
    }
    const box = document.createElement("div");
    box.className = "rmfr-explanation";
    const heading = document.createElement("div");
    heading.className = "rmfr-label";
    heading.textContent = label;
    const body = document.createElement("div");
    body.innerHTML = text;
    box.append(heading, body);
    wrap.appendChild(box);
    void typeset(box);
}

function showModel(wrap: HTMLElement): void {
    if (!payload || !payload.modelAnswer) {
        return;
    }
    const box = document.createElement("div");
    box.className = "rmfr-model";
    box.innerHTML = `<b>Model answer.</b> ${payload.modelAnswer}`;
    wrap.appendChild(box);
    void typeset(box);
}

function addNote(
    wrap: HTMLElement,
    kind: "spaced" | "struggle",
    html: string,
): void {
    const note = document.createElement("div");
    note.className = `rmfr-note ${kind}`;
    note.innerHTML = html;
    wrap.appendChild(note);
}

function addProceed(wrap: HTMLElement, label: string, onClick: () => void): void {
    const row = document.createElement("div");
    row.className = "rmfr-row";
    row.appendChild(makeButton(label, "primary", onClick));
    wrap.appendChild(row);
}

function addContinue(wrap: HTMLElement): void {
    addProceed(wrap, "Continue", () => bridgeCommand("fr:continue"));
}

function firstUrl(text: string): string | null {
    const match = text.match(/https?:\/\/[^\s"'<>)]+/);
    return match ? match[0] : null;
}

function addResource(wrap: HTMLElement): void {
    if (!payload || !firstUrl(payload.source)) {
        return;
    }
    const res = document.createElement("div");
    res.className = "rmfr-res";
    const link = document.createElement("a");
    link.textContent = "\u2192 Needs content review: open the source for this item";
    link.href = "#";
    link.addEventListener("click", (event) => {
        event.preventDefault();
        bridgeCommand("fr:resource");
    });
    res.appendChild(link);
    wrap.appendChild(res);
}

function startMainFirst(): void {
    if (!payload) {
        return;
    }
    renderFrQuestion({
        title: payload.subtopic || "MCAT free response",
        step: "Free response",
        stem: payload.prompt,
        accepted: payload.acceptedAnswers,
        keyTerms: payload.keyTerms,
        submitLabel: "Submit answer",
        afterSubmit: (_value, correct, wrap) => {
            bridgeCommand(`fr:first:${correct ? "correct" : "wrong"}`);
            if (correct) {
                showModel(wrap);
                showExplanation(wrap, "Explanation", payload!.explanation);
                addContinue(wrap);
            } else {
                // PRD: on a miss, DON'T hand over the answer. Rebuild it with
                // the item's own guiding sub-questions (retrieval, not reading).
                addNote(
                    wrap,
                    "spaced",
                    "<strong>Not quite.</strong> Rather than just showing the answer, "
                        + "let's rebuild it with a few guiding questions.",
                );
                addProceed(wrap, "Start guiding questions", () => startLadder());
            }
        },
    });
}

function startLadder(): void {
    ladderIndex = 0;
    renderLadderRung();
}

function renderLadderRung(): void {
    if (!payload) {
        return;
    }
    if (ladderIndex >= payload.subquestions.length) {
        reshowMain();
        return;
    }
    const total = payload.subquestions.length;
    const sub = payload.subquestions[ladderIndex];
    const rung = ladderIndex;
    renderFrQuestion({
        title: "Guiding question",
        step: `Guiding question ${rung + 1} of ${total}`,
        stem: sub.stem,
        accepted: sub.accepted_answers,
        keyTerms: sub.key_terms || [],
        submitLabel: "Check",
        afterSubmit: (_value, correct, wrap) => {
            bridgeCommand(`fr:sub:${rung}:${correct ? "got" : "missed"}`);
            if (!correct) {
                showAccepted(wrap, sub.accepted_answers);
            }
            showExplanation(wrap, correct ? "Correct" : "Explanation", sub.explanation);
            const last = rung >= total - 1;
            addProceed(
                wrap,
                last ? "Back to the prompt" : "Next guiding question",
                () => {
                    ladderIndex = rung + 1;
                    renderLadderRung();
                },
            );
        },
    });
}

function reshowMain(): void {
    if (!payload) {
        return;
    }
    renderFrQuestion({
        title: payload.subtopic || "MCAT free response",
        step: "Back to the original prompt",
        stem: payload.prompt,
        accepted: payload.acceptedAnswers,
        keyTerms: payload.keyTerms,
        submitLabel: "Submit answer",
        afterSubmit: (_value, correct, wrap) => {
            bridgeCommand(`fr:reattempt:${correct ? "correct" : "wrong"}`);
            finishReattempt(wrap, correct);
        },
    });
}

function finishReattempt(wrap: HTMLElement, correct: boolean): void {
    if (correct) {
        addNote(
            wrap,
            "spaced",
            "<strong>Not mastered yet.</strong> Getting it right seconds after the "
                + "scaffold isn't readiness. This card is scheduled for spaced "
                + "re-retrieval \u2014 you'll need to recall it again in a later "
                + "session for it to count.",
        );
        showModel(wrap);
        showExplanation(wrap, "Explanation", payload ? payload.explanation : "");
    } else {
        addNote(
            wrap,
            "struggle",
            "<strong>Here's the full answer \u2014 earned through real "
                + "retrieval.</strong> This card is flagged as struggling and "
                + "scheduled for aggressive early re-retrieval; it returns fresh "
                + "next session.",
        );
        if (payload) {
            showAccepted(wrap, payload.acceptedAnswers);
        }
        showModel(wrap);
        showExplanation(wrap, "Explanation", payload ? payload.explanation : "");
        addResource(wrap);
    }
    addContinue(wrap);
}

export function _frStart(data: FrPayload): void {
    ensureStyle();
    payload = data;
    ladderIndex = 0;
    startMainFirst();
}
