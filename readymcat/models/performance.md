# Performance model — one-page description

**Question it answers:** "When you actually sit exam-style questions, how often
are you right the first time?"

## What it is

The Performance score is **first-attempt accuracy** on ReadyMCAT's question
notetypes (`ReadyMCAT MCQ`, `FreeResponse`, `Passage`), computed from the review
log — the earliest graded review per question card, where Good/Easy counts as a
hit and Again/Hard as a miss. It is deliberately a _different signal_ from
Memory: Memory is recall of study cards; Performance is application on questions.

- **Inputs:** the first `revlog` row for each question card (never a re-attempt),
  read back through the shipping `points_at_stake_queue` backend.
- **Range:** a **Wilson 95% interval** (honest about small samples).

## Give-up rule

Performance is shown **only** with **≥ 30 first attempts**. Below that it reads
**"not enough data yet."**

## Held-out check + distinct-from-memory

Run: `just perf-heldout` (score) / `just perf-heldout --build-set` (author the
set) → `readymcat/eval/performance_heldout.{json,png}`.

The held-out set is reworded, exam-style **paraphrase/transfer** items (disjoint
wording from the authored bank, generated once and frozen). Scored through the
real engine on a synthetic-but-labelled cohort:

| metric                                   | value                             |
| ---------------------------------------- | --------------------------------- |
| held-out accuracy                        | **56.2%** [53.3%, 59.0%]          |
| first attempts                           | 1,200 (cutoff ≥ 30 cleared)       |
| memory ↔ performance correlation         | Pearson r = 0.59, Spearman = 0.55 |
| shared variance (r²)                     | 0.35                              |
| mean transfer gap (memory − performance) | +0.14                             |

**Finding:** Performance is **distinct from Memory** — they correlate (r=0.59)
but only share ~35% of variance, and application runs ~14 points below recall
(the expected transfer gap). If the two tracked perfectly, Performance would be
redundant; they do not. (Cohort outcomes are synthetic and labelled as such —
no human cohort exists yet; the architectural distinctness — different inputs,
different code path — holds regardless.)
