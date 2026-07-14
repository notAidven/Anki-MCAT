# Memory model — one-page description

**Question it answers:** "How much of what you've studied will you still recall?"

## What it is

The Memory score is the student's **mean FSRS retrievability** (predicted
probability of recall _right now_) over their graded cards, aggregated per AAMC
content category and then weighted into one overall score. It is Anki's own
FSRS model — ReadyMCAT does not re-implement spacing. The value is read through
the same `extract_fsrs_retrievability` SQL function the reviewer uses, so the
dashboard reports exactly what the scheduler believes.

- **Inputs:** each card's FSRS memory state (stability, difficulty, decay) fitted
  from its review history, plus time elapsed since the last review.
- **Aggregation:** per-category mean recall → overall mean, surfaced with the
  per-category weakness that also drives the Points-at-Stake queue.
- **Range:** shown as a 95% interval, not a single number.

## Give-up rule (honest reporting)

Memory is shown **only** when there is enough data to mean anything:

- **≥ 200 graded reviews**, **and**
- **≥ 50% category coverage** (you've touched at least half the AAMC categories).

Below either threshold the card reads **"not enough data yet"** rather than a
falsely precise number.

## Calibration (is 80% really 80%?)

Run: `just calibrate` → `readymcat/eval/calibration.png` + `calibration.json`.
A one-step-ahead (held-out) reliability test on 3,521 synthetic reviews through
the real FSRS engine:

| metric            | value | reading                        |
| ----------------- | ----- | ------------------------------ |
| Brier score       | 0.152 | ≈ the base-rate Brier (0.145)  |
| log-loss          | 0.498 | —                              |
| ECE               | 0.081 | mean predicted-vs-observed gap |
| calibration slope | 0.22  | **< 1 → overconfident**        |

**Honest finding:** with global default FSRS parameters, the model is
**overconfident** on this deliberately non-FSRS synthetic population (high-
confidence bins overshoot: predicted 0.94 → observed 0.85). This is a stress
test, not real-cohort calibration. Per-user FSRS parameter optimization and a
real review log (replay with `just calibrate --collection <path>`) are expected
to tighten it; the harness is ready to produce that number the moment real data
exists.
