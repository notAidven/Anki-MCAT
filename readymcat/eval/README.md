# ReadyMCAT ladder-generation eval

This is the eval harness for ReadyMCAT's one AI feature: **runtime generation of
teach-on-miss ladders** (the guiding `{q,a}` sub-questions shown when a student
misses a card that has no authored ladder). Because it is AI, its quality is
measured here rather than assumed — and measured _before_ a student ever sees a
generated ladder.

It shares the exact production core (`../tools/ladder_gen.py`): the same prompt,
parser and guardrails that gate generation at runtime are what the eval scores,
so the harness can't drift from what ships.

## Run it

```bash
# Live: generate + judge with the OpenAI API (needs OPENAI_API_KEY in the env)
just eval

# Offline: deterministic stub generator + stub judge, no network call.
# Proves the whole pipeline end-to-end and is safe for CI.
just eval --stub

# Useful flags
just eval --limit 5                          # only the first 5 golden cards
just eval --report readymcat/eval/report.json  # write the full per-card report
just eval --bank subquestions.json           # authored ladder bank (baseline)
just eval --gen-model gpt-4o-mini --judge-model gpt-4o
```

Under the hood `just eval` runs `readymcat/eval/run_eval.py` (stdlib-only; it
loads the shared core `readymcat/tools/ladder_gen.py` by path).

## What it measures

For each card in the held-out golden set (`golden_set.json`) — each standing in
for a missed card with no authored ladder — the harness builds the grounded
prompt, generates a ladder, and scores three layers:

1. **Deterministic guardrails** — the exact validators from
   `../tools/ladder_gen.py` that gate generation at runtime, so the eval scores
   what actually ships:
   - **schema**: 2–4 well-formed `{q,a}` rungs;
   - **answer-leak**: the first rung must not restate the card's answer;
   - **source-grounding**: each sub-answer's content must trace back to the
     card's own material (question + answer + cited source).
2. **LLM-as-judge** — a stronger model scores each ladder 1–5 on a pedagogical
   rubric (does it scaffold toward the answer via retrieval, at one level,
   without giving it away, with every sub-answer correct and grounded?) and
   flags subtle leaks / factual errors / off-topic ladders a bag-of-words check
   cannot. The judge is sanity-checked against a couple of hand-labelled
   examples (reported as "judge calibration"). Offline (`--stub`) it is a
   deterministic validator-backed proxy so the whole run is reproducible.
3. **Beats-a-baseline** — the generated ladder is compared against the PRD's
   "keyword/vector baseline", implemented as **TF-IDF cosine retrieval** of the
   nearest _authored_ sub-question ladder from `subquestions.json`. The
   retrieved ladder is reused verbatim and scored on the missed card by the
   **same** guardrails + judge, so the comparison is apples-to-apples.

### Headline metrics (AI vs baseline, side-by-side)

- **accuracy** — the fraction of cards whose ladder passes **all** deterministic
  guardrails **and** the judge (score ≥ 4/5, no danger flagged). Only such
  ladders would ever be shown to a student.
- **wrong-answer rate** — the fraction whose ladder **leaks** the answer, is
  judged **factually wrong / not grounded (off-topic)**, or **fails to produce a
  usable ladder** at all — the dangerous failure mode teach-on-miss must avoid.

Both are computed identically for the AI generator and the retrieval baseline
and printed in one table (plus grounding, judge mean and head-to-head win-rate).
The full machine-readable numbers, per card, are written to `report.json`.

## Gates (honest-by-intent, tunable)

The run prints a PASS/FAIL per gate and exits non-zero if any fails:

| gate                         | bar                             |
| ---------------------------- | ------------------------------- |
| `schema_100pct`              | schema valid = 100%             |
| `no_answer_leak`             | answer-leak = 0%                |
| `grounding_ok`               | source-grounding ≥ 90%          |
| `judge_mean_ok`              | judge mean (generated) ≥ 3.5/5  |
| `ai_higher_accuracy`         | AI accuracy > baseline accuracy |
| `ai_lower_wrong_answer_rate` | AI wrong-answer < baseline      |
| `beats_baseline`             | win-rate vs baseline > 50%      |

These thresholds are MVP defaults (same spirit as the dashboard's give-up rule),
tunable in `run_eval.py`.

## Contamination / leakage

The generator prompt is **zero-shot** — it never receives a golden-set card as a
few-shot example — so there is no train/test leakage in the pipeline. The
held-out set is used only to score generation, and the baseline retrieves from
the authored bank (`subquestions.json`), which is disjoint from the held-out
set's identifiers.

## Files

- `golden_set.json` — held-out MCAT cards (B/B, C/P, P/S, CARS) as
  `(question, answer, source)` triples, each standing in for a missed card with
  no authored ladder.
- `run_eval.py` — the harness (deterministic checks + judge + TF-IDF retrieval
  baseline + accuracy/wrong-answer metrics + report).
- `report.json` — the captured machine-readable report from the latest run
  (its `mode` field stamps whether the numbers are `live` or `stub`).
- `../tools/ladder_gen.py` — the shared core (prompt, parser, validators, OpenAI
  call), used identically at runtime and here.
