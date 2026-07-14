// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

/* eslint
@typescript-eslint/no-explicit-any: "off",
 */

// ReadyMCAT multiple-choice reviewer + per-question teach-on-miss UI.
//
// When the desktop reviewer (qt/aqt/reviewer.py) shows a card that uses the
// "ReadyMCAT MCQ" note type, it calls `_mcqStart(payload)` with the question,
// its four options, the correct index, the explanation and the card's own
// guiding sub-questions. This module renders the interactive MCQ and drives the
// PRD flow, reporting outcomes to Python over bridgeCommand (Python owns
// grading into FSRS, tagging and logging):
//
//   answer correct first try  -> `mcq:first:correct:<i>`  -> explanation -> Continue
//   answer wrong              -> `mcq:first:wrong:<i>`    -> guiding ladder
//     each sub-question:  select -> reveal -> `mcq:sub:<rung>:<got|missed>`
//     ladder done         -> re-show the MAIN question
//       correct now       -> `mcq:reattempt:correct` (not mastered -> spaced)
//       wrong again       -> `mcq:reattempt:wrong`   (reveal + flag struggling)
//   Continue -> `mcq:continue`  (always ends gracefully; no loops)
//
// Retrieve-before-reveal: on a FIRST miss the correct option is NOT highlighted
// and the explanation is NOT shown — only the "start guiding questions" button.
// The answer stays hidden until the student has worked through the ladder. The
// one exception is a card with no authored ladder (`subquestions` empty): there
// is nothing to retrieve toward, so we fall back to the normal answer reveal
// rather than strand the student behind a button that can't do anything.

import { bridgeCommand } from "@tslib/bridgecommand";

import { firstUrl, hasLadder, makeButton as sharedMakeButton, qaEl, typeset } from "./readymcat_dom";

interface SubQuestion {
    stem: string;
    options: string[];
    correct_index: number;
    explanation: string;
}

interface McqPayload {
    question: string;
    options: string[];
    correctIndex: number;
    explanation: string;
    subtopic: string;
    source: string;
    subquestions: SubQuestion[];
}

let payload: McqPayload | null = null;
let ladderIndex = 0;

const STYLE_ID = "readymcat-mcq-style";

const CSS = `
#qa .rmcq-wrap{max-width:720px;margin:1.2em auto;text-align:left;line-height:1.5;}
#qa .rmcq-head{display:flex;align-items:center;gap:.6em;flex-wrap:wrap;
    padding-bottom:.6em;margin-bottom:1em;border-bottom:1px solid var(--border,#0003);}
#qa .rmcq-badge{font-size:.72em;font-weight:700;letter-spacing:.04em;
    text-transform:uppercase;padding:.25em .6em;border-radius:999px;
    background:var(--accent,#2186eb);color:#fff;white-space:nowrap;}
#qa .rmcq-title{font-weight:600;}
#qa .rmcq-step{margin-left:auto;font-size:.82em;opacity:.7;}
#qa .rmcq-card{border:1px solid var(--border,#0003);border-radius:10px;
    padding:1em 1.1em;margin:.4em 0 1em;background:var(--canvas-elevated,#80808014);}
#qa .rmcq-stem{font-size:1.08em;font-weight:600;}
#qa .rmcq-options{display:flex;flex-direction:column;gap:.5em;margin:.4em 0;}
#qa .rmcq-option{display:flex;gap:.7em;align-items:flex-start;cursor:pointer;
    text-align:left;font-size:.98em;border-radius:9px;padding:.7em .9em;
    border:1px solid var(--border,#0004);background:var(--canvas,#8080800f);color:inherit;}
#qa .rmcq-option:hover:not(:disabled){filter:brightness(1.06);}
#qa .rmcq-option.selected{border-color:var(--accent,#2186eb);
    box-shadow:0 0 0 1px var(--accent,#2186eb) inset;}
#qa .rmcq-option.correct{border-color:#2e7d32;background:#2e7d3222;}
#qa .rmcq-option.wrong{border-color:#c62828;background:#c6282822;}
#qa .rmcq-option:disabled{cursor:default;opacity:1;}
#qa .rmcq-letter{font-weight:700;opacity:.7;min-width:1.3em;}
#qa .rmcq-opt-text{flex:1;}
#qa .rmcq-row{display:flex;gap:.6em;flex-wrap:wrap;margin-top:.9em;}
#qa .rmcq-btn{cursor:pointer;font-size:.95em;font-weight:600;border-radius:8px;
    padding:.55em 1.1em;border:1px solid var(--border,#0004);
    background:var(--canvas,#8080801a);color:inherit;}
#qa .rmcq-btn:hover:not(:disabled){filter:brightness(1.08);}
#qa .rmcq-btn:disabled{opacity:.45;cursor:default;}
#qa .rmcq-btn.primary{background:var(--accent,#2186eb);color:#fff;border-color:transparent;}
#qa .rmcq-label{font-size:.74em;font-weight:700;text-transform:uppercase;
    letter-spacing:.04em;opacity:.6;margin-bottom:.35em;}
#qa .rmcq-explanation{border-radius:10px;padding:.9em 1.1em;margin:.9em 0;
    border-left:4px solid var(--accent,#2186eb);background:var(--canvas-elevated,#80808014);}
#qa .rmcq-note{border-radius:10px;padding:.9em 1.1em;margin:.9em 0;
    border-left:4px solid var(--accent,#2186eb);background:var(--canvas-elevated,#80808014);}
#qa .rmcq-note.struggle{border-left-color:#c62828;}
#qa .rmcq-note.spaced{border-left-color:#2e7d32;}
#qa .rmcq-res{margin:.4em 0 .2em;}
#qa .rmcq-res a{color:var(--accent,#2186eb);text-decoration:underline;cursor:pointer;}
#qa .rmcq-subtopic{margin-top:.8em;font-size:.78em;opacity:.6;
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

function makeButton(
    label: string,
    cls: string,
    onClick: () => void,
): HTMLButtonElement {
    return sharedMakeButton("rmcq", label, cls, onClick);
}

function newWrap(title: string, stepText: string): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "rmcq-wrap";

    const head = document.createElement("div");
    head.className = "rmcq-head";
    const badge = document.createElement("span");
    badge.className = "rmcq-badge";
    badge.textContent = "ReadyMCAT";
    const titleEl = document.createElement("span");
    titleEl.className = "rmcq-title";
    titleEl.textContent = title;
    const step = document.createElement("span");
    step.className = "rmcq-step";
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
    options: string[];
    correctIndex: number;
    submitLabel: string;
    // Whether to visually reveal the correct option after submit, given whether
    // the student's own choice was correct. Defaults to always revealing (used
    // by the guiding rungs and the post-ladder re-attempt). The first attempt
    // overrides it to keep the correct option HIDDEN on a miss when a guiding
    // ladder is available (retrieve-before-reveal).
    revealCorrect?: (correct: boolean) => boolean;
    afterSubmit: (chosen: number, correct: boolean, wrap: HTMLElement) => void;
}

function renderMcqQuestion(config: QuestionConfig): void {
    const wrap = newWrap(config.title, config.step);

    const card = document.createElement("div");
    card.className = "rmcq-card";
    const stem = document.createElement("div");
    stem.className = "rmcq-stem";
    stem.innerHTML = config.stem;
    card.appendChild(stem);
    wrap.appendChild(card);

    let selected = -1;
    let submitted = false;
    const optButtons: HTMLButtonElement[] = [];

    const submitBtn = makeButton(config.submitLabel, "primary", () => {
        if (submitted || selected < 0) {
            return;
        }
        submitted = true;
        submitBtn.disabled = true;
        submitBtn.remove();
        const correct = selected === config.correctIndex;
        const revealCorrect = config.revealCorrect
            ? config.revealCorrect(correct)
            : true;
        optButtons.forEach((button, index) => {
            button.disabled = true;
            if (index === config.correctIndex && revealCorrect) {
                button.classList.add("correct");
            }
            if (index === selected && !correct) {
                button.classList.add("wrong");
            }
        });
        config.afterSubmit(selected, correct, wrap);
    });
    submitBtn.disabled = true;

    const list = document.createElement("div");
    list.className = "rmcq-options";
    config.options.forEach((option, index) => {
        const button = document.createElement("button");
        button.className = "rmcq-option";
        button.type = "button";
        const letter = document.createElement("span");
        letter.className = "rmcq-letter";
        letter.textContent = String.fromCharCode(65 + index);
        const text = document.createElement("span");
        text.className = "rmcq-opt-text";
        text.innerHTML = option;
        button.append(letter, text);
        button.addEventListener("click", () => {
            if (submitted) {
                return;
            }
            selected = index;
            optButtons.forEach((other, otherIndex) => {
                other.classList.toggle("selected", otherIndex === index);
            });
            submitBtn.disabled = false;
        });
        optButtons.push(button);
        list.appendChild(button);
    });
    wrap.appendChild(list);

    const row = document.createElement("div");
    row.className = "rmcq-row";
    row.appendChild(submitBtn);
    wrap.appendChild(row);

    void typeset(wrap);
}

function showExplanation(
    wrap: HTMLElement,
    correct: boolean,
    text?: string,
): void {
    const explanation = text ?? (payload ? payload.explanation : "");
    if (!explanation) {
        return;
    }
    const box = document.createElement("div");
    box.className = "rmcq-explanation";
    const label = document.createElement("div");
    label.className = "rmcq-label";
    label.textContent = correct ? "Correct" : "Explanation";
    const body = document.createElement("div");
    body.innerHTML = explanation;
    box.append(label, body);
    wrap.appendChild(box);
    void typeset(box);
}

function addNote(
    wrap: HTMLElement,
    kind: "spaced" | "struggle",
    html: string,
): void {
    const note = document.createElement("div");
    note.className = `rmcq-note ${kind}`;
    note.innerHTML = html;
    wrap.appendChild(note);
}

function addProceed(wrap: HTMLElement, label: string, onClick: () => void): void {
    const row = document.createElement("div");
    row.className = "rmcq-row";
    row.appendChild(makeButton(label, "primary", onClick));
    wrap.appendChild(row);
}

function addContinue(wrap: HTMLElement): void {
    addProceed(wrap, "Continue", () => bridgeCommand("mcq:continue"));
}

function addResource(wrap: HTMLElement): void {
    if (!payload || !firstUrl(payload.source)) {
        return;
    }
    const res = document.createElement("div");
    res.className = "rmcq-res";
    const link = document.createElement("a");
    link.textContent = "\u2192 Needs content review: open the source for this question";
    link.href = "#";
    link.addEventListener("click", (event) => {
        event.preventDefault();
        bridgeCommand("mcq:resource");
    });
    res.appendChild(link);
    wrap.appendChild(res);
}

function startMainFirst(): void {
    if (!payload) {
        return;
    }
    const ladderAvailable = hasLadder(payload.subquestions);
    renderMcqQuestion({
        title: payload.subtopic || "MCAT question",
        step: "Multiple choice",
        stem: payload.question,
        options: payload.options,
        correctIndex: payload.correctIndex,
        submitLabel: "Submit answer",
        // Keep the correct option hidden on a miss when we can teach instead.
        revealCorrect: (correct) => correct || !ladderAvailable,
        afterSubmit: (chosen, correct, wrap) => {
            bridgeCommand(`mcq:first:${correct ? "correct" : "wrong"}:${chosen}`);
            if (correct) {
                showExplanation(wrap, true);
                addContinue(wrap);
            } else if (ladderAvailable) {
                // PRD: on a miss, DON'T reveal the correct option or the
                // explanation. Show only the button that starts the card's own
                // guiding sub-questions (retrieval, not reading); the answer
                // stays hidden until the student works through them.
                addNote(
                    wrap,
                    "spaced",
                    "<strong>Not quite.</strong> Rather than just showing the answer, "
                        + "let's rebuild it with a few guiding questions.",
                );
                addProceed(wrap, "Start guiding questions", () => startLadder());
            } else {
                // No guiding ladder authored for this card: never strand the
                // student behind a button that can't do anything — fall back to
                // the normal answer reveal so they still get the correction.
                showExplanation(wrap, false);
                addResource(wrap);
                addContinue(wrap);
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
    renderMcqQuestion({
        title: "Guiding question",
        step: `Guiding question ${rung + 1} of ${total}`,
        stem: sub.stem,
        options: sub.options,
        correctIndex: sub.correct_index,
        submitLabel: "Check",
        afterSubmit: (_chosen, correct, wrap) => {
            bridgeCommand(`mcq:sub:${rung}:${correct ? "got" : "missed"}`);
            showExplanation(wrap, correct, sub.explanation);
            const last = rung >= total - 1;
            addProceed(
                wrap,
                last ? "Back to the question" : "Next guiding question",
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
    renderMcqQuestion({
        title: payload.subtopic || "MCAT question",
        step: "Back to the original question",
        stem: payload.question,
        options: payload.options,
        correctIndex: payload.correctIndex,
        submitLabel: "Submit answer",
        afterSubmit: (_chosen, correct, wrap) => {
            bridgeCommand(`mcq:reattempt:${correct ? "correct" : "wrong"}`);
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
        showExplanation(wrap, true);
    } else {
        addNote(
            wrap,
            "struggle",
            "<strong>Here's the full explanation \u2014 earned through real "
                + "retrieval.</strong> This card is flagged as struggling and "
                + "scheduled for aggressive early re-retrieval; it returns fresh "
                + "next session.",
        );
        showExplanation(wrap, false);
        addResource(wrap);
    }
    addContinue(wrap);
}

export function _mcqStart(data: McqPayload): void {
    ensureStyle();
    payload = data;
    ladderIndex = 0;
    startMainFirst();
}
