# Design: AI-generated teach-on-miss ladders

Date: 2026-07-02
Status: implemented (desktop)

## Problem

ReadyMCAT's core feature (SPOV 1) is teach-on-miss: on a wrong answer, instead
of revealing the explanation, walk the student through guiding `{q,a}`
sub-questions so they _retrieve_ the correction. The bundled bank ships those
sub-questions authored by hand, but that only covers ReadyMCAT's own cards.
The assignment requires an **AI feature with an eval harness**, and the PRD's
#1 "next step" was exactly this: generate the ladder at runtime so teach-on-miss
also works on imported/community decks and the student's own cards.

## Decisions

- **Feature**: generate the teach-on-miss `{q,a}` ladder at runtime for a
  missed card that has no authored ladder ("System A" — the tag/`{q,a}` path,
  which is where imported/classic cards land), reusing the existing
  teach-on-miss reviewer unchanged.
- **Model runtime**: OpenAI API (the user has a key), called over stdlib
  `urllib` — no third-party dependency, and injectable so tests stay offline.
- **Trigger**: lazy on first miss, then cached per note, so a card is generated
  once and every later miss is instant (keeps the p95 next-card target intact).
- **Eval**: hybrid — deterministic guardrails + LLM-as-judge + beats-a-baseline
  over a held-out golden set.
- **Scope**: desktop-only, Python-only. No new Rust module or proto service and
  no iOS path, because (a) iOS only reviews the fully-authored bundled bank, so
  generation would almost never fire there today, and (b) desktop teach-on-miss
  is driven from Python, so no `mediasrv` endpoint is needed either. This keeps
  the "one real Rust engine change" story intact.

## Architecture

Single source of truth in a dependency-free core, wrapped by a thin desktop
host, consumed by both the reviewer and the eval harness:

- `readymcat/tools/ladder_gen.py` (core, stdlib-only): grounded prompt builder,
  completion parser, guardrail validators (schema / answer-leak / grounding),
  and an injectable `openai_chat`. The **guardrails ARE the eval checks**.
- `qt/aqt/readymcat_ladder_gen.py` (desktop host): builds a `CardContext` from
  the note, performs the OpenAI call with one retry, validates, and caches the
  result in a per-note sidecar `readymcat_generated_ladders.json`. Enabled only
  when `OPENAI_API_KEY` is set (opt-out via `READYMCAT_DISABLE_LADDER_GEN`).
- `qt/aqt/reviewer.py`: on a miss with no authored concept, checks the cache,
  else generates on a background thread (`taskman`, `uses_collection=False`)
  behind a "building guiding questions…" state, then runs the existing
  `_teachOnMissStart` flow — or falls back to a normal reschedule if disabled /
  failed / guardrails not met. A generated ladder is wrapped in a `Concept`, so
  self-marking, `ReadyMCAT::struggling` tagging, scheduling and points-at-stake
  resurfacing all run unchanged.
- `ts/reviewer/teach_on_miss.ts`: adds `_teachOnMissLoading()` (spinner overlay).
- `readymcat/eval/` + `just eval`: the harness and held-out golden set.

Data flow: miss → cache hit? → run; else (key present) → background generate →
guardrails → cache + run, or graceful fallback.

## Guardrails

Every generated ladder must pass before it is shown: valid schema (2–4 `{q,a}`),
no blatant answer-leak in the first rung, and source-grounding of each
sub-answer in the card's material. Fail → one retry → graceful fallback (never
traps the student). The generator never writes the memory/performance/readiness
scores (the same honesty firewall the diagnostic respects).

## Eval

`just eval` (live) / `just eval --stub` (offline) scores the generator over
`readymcat/eval/golden_set.json`: deterministic guardrails (reused verbatim) +
an LLM-judge on a pedagogical rubric (calibrated against hand labels) + a
win-rate against a naive baseline. Gates: schema 100%, leak 0%, grounding ≥ 90%,
judge mean ≥ 3.5/5, win-rate > 50%. Zero-shot prompt ⇒ no train/test leakage.
See `readymcat/eval/README.md`.

## Instrumentation & honest scope

- `ladder_generated` events (with the validation outcome) are logged distinctly
  from authored `ladder_started`, so the corrected-concept re-retrieval ablation
  can eventually compare generated vs authored vs answer-only.
- **Deferred**: extending generation to iOS (native Swift path calling the same
  core); the full longitudinal ablation. Other runtime AI (generated flashcards,
  chatbot) remains out of scope.

## Verification

`ruff` + `mypy` clean on all changed Python (core, host, `run_eval`,
`reviewer.py`); 14 offline unit tests pass in `pylib/tests/`; `eslint` clean on
the TS; `just eval --stub` passes end-to-end offline. Full `just check`
(whole-tree rebuild) is the final gate.

## Files

New: `readymcat/tools/ladder_gen.py`, `qt/aqt/readymcat_ladder_gen.py`,
`readymcat/eval/{run_eval.py,golden_set.json,README.md}`,
`pylib/tests/test_readymcat_ladder_gen.py`.
Edited: `qt/aqt/reviewer.py`, `ts/reviewer/{teach_on_miss.ts,index.ts}`,
`justfile`, `docs/ReadyMCAT-PRD.md`, `docs/brainlift-mcat.md`.
