# ReadyMCAT — results report

> **Start at [`SUBMISSION.md`](SUBMISSION.md)** — the single submission entry
> point (quickstart, a re-runnable verification table with freshly-measured
> numbers, the demo walkthrough, and the honest gaps). This report is the
> detailed results backing it.

Honest, reproducible results for the Sunday "prove it" bar. Every number below
is regenerable from this repo; commands are given per section. Where a cohort is
synthetic (no real students yet), it is **labelled synthetic** and the
limitation is stated. Results that did **not** work are reported in full
(§Honest limitations).

## 1. AI teach-on-miss ladder generation vs a simpler baseline

Run: `set -a; source .env.local; set +a; just eval --report readymcat/eval/report.json`
→ `readymcat/eval/report.json` (committed). The generator and every guardrail are
the **shipping MCQ** core (`readymcat/tools/ladder_gen.py`), so what is scored is
what ships; the baseline is the nearest authored ladder retrieved by TF-IDF,
reshaped into the **same MCQ form** (`authored_to_mcq`) so the side-by-side is
apples-to-apples.

| metric                     | ReadyMCAT AI (gpt-4o-mini + gpt-4o judge) | TF-IDF retrieval baseline |
| -------------------------- | ----------------------------------------- | ------------------------- |
| ladder accuracy            | **100%**                                  | 18.8%                     |
| wrong-answer rate          | **0%**                                    | 62.5%                     |
| source-grounding pass-rate | **100%** (mean 0.809)                     | 25% (mean 0.330)          |
| judge mean (1–5)           | **4.88**                                  | 2.69                      |
| win-rate (head-to-head)    | **75%**                                   | —                         |
| schema valid / answer-leak | 100% / 0%                                 | 100% / 0%                 |

_n = 16 held-out cards; judge calibration 100% (2 hand-labelled cases); **all 7
gates PASS**._

- **Beats the simpler method** (keyword/vector retrieval of the nearest authored
  ladder, scored in the identical MCQ form) on every metric — for a held-out card
  the baseline retrieves *another* concept's ladder, so it is off-topic /
  ungrounded (grounding 0.33, judge 2.69) where the generated ladder is grounded
  in the missed card (0.809).
- **Reproducible (live LLM, so it varies run-to-run):** across three back-to-back
  live runs on 2026-07-05 the **grounding gate held at 100% pass** (mean
  0.809–0.834), **win-rate 75%**, and **all 7 gates PASSED every run**; accuracy
  ranged 81.2–100% and wrong-answer 0–18.8% (n = 16 model-sampling noise). The
  committed `report.json` is the first of those runs.
- **Honest grounding note — an earlier MCQ run sat at 87.5%, under the strict 90%
  gate.** The short MCQ *explanations* introduced wording absent from the card's
  terse text, so the (unchanged) lexical grounding proxy scored two cards
  (hemoglobin cooperativity 0.42, Doppler 0.35) below the 0.5 per-ladder floor.
  The fix was a **generator** change, **not** a gate change: the prompt now
  requires the correct option + explanation to be worded in the card's own terms
  (a faithfulness improvement), which lifted those two cards to 0.73 / 0.74 and
  grounding to **100% pass / 0.809 mean without touching the grounding check or
  the 90% bar**.
- **Source-traceable:** every generated ladder is grounded on the note's `Source`
  field; a `grounding_score ≥ 0.5` per-ladder hard gate blocks ungrounded output.
- **The eval runs before students see anything** (accuracy + wrong-answer rate on
  a held-out golden set with a stated cutoff = passes all guardrails **and** a
  stronger judge scores ≥4 with no danger flag).
- **AI off still scores:** the three dashboard scores come from the Rust engine
  over the revlog, never the generator; with no key the reviewer behaves exactly
  as before generation existed (`just eval --stub`, `test_readymcat_dashboard.py`).

## 2. Memory model calibration

Run: `just calibrate` → `readymcat/eval/calibration.{png,json}`.
One-step-ahead (held-out) reliability on **3,535** synthetic reviews scored
through the **real FSRS engine** (seeded, reproducible).

| metric                        | value                   |
| ----------------------------- | ----------------------- |
| Brier                         | 0.140 (base-rate 0.135) |
| log-loss                      | 0.468                   |
| ECE / MCE                     | 0.066 / 0.178           |
| calibration slope / intercept | 0.24 / +1.16            |

**Honest finding — passes its gates, but overconfident where most confident.**
The run clears its three gates (`enough_predictions`, `ece_within_bound`,
`not_worse_than_base_rate` → PASS). Yet with global default FSRS parameters the
model is still **overconfident in its top bin** on this deliberately non-FSRS
synthetic population: it predicts 0.94 but observes 0.86 (calibration slope
0.24 ≪ 1). The reliability chart is the deliverable and the harness surfaces the
residual miscalibration; per-user FSRS optimization + a real review log
(`just calibrate --collection <path>`) are needed for a real-cohort number.

## 3. Performance model — held-out + distinct from memory

Run: `just perf-heldout` → `readymcat/eval/performance_heldout.{png,json}`.
Scored on reworded, exam-style **paraphrase/transfer** items (disjoint wording
from the bank) through the real engine.

| metric               | value                        |
| -------------------- | ---------------------------- |
| held-out accuracy    | **56.2%** [53.3%, 59.0%]     |
| first attempts       | 1,200 (cutoff ≥ 30 cleared)  |
| memory ↔ performance | Pearson r = 0.59, r² = 0.35  |
| mean transfer gap    | +0.14 (memory − performance) |

**Finding:** performance is a **signal distinct from memory** — correlated but
sharing only ~35% variance, application ~14 pts below recall. (Cohort outcomes
synthetic; architectural distinctness — different inputs/code path — is
independent of that.)

## 4. Study-feature ablation (teach-on-miss, equal study time)

Run: `just ablation` → `readymcat/eval/ablation.{png,json}`.
Three arms at an **equal time budget**, 300 simulated students.

| arm                     | retention | re-retrieval (corrected concepts) |
| ----------------------- | --------- | --------------------------------- |
| A — teach-on-miss ON    | 0.428     | **0.560**                         |
| B — OFF (reveal answer) | **0.460** | 0.460                             |
| C — plain Anki          | 0.459     | 0.459                             |

**Honest finding — NULL / negative on the primary retention metric.** At equal
time the ladder's ~22s cost means ON completes far fewer exposures (80 vs 148),
so overall retention is **lower** (−0.032 vs OFF). ON _does_ win where it's
designed to — corrected-concept **re-retrieval +0.099** — and a sensitivity sweep
shows ON beats OFF in **38%** of (ladder-cost × retrieval-benefit) settings. This
is a mechanistic simulation with stated effect sizes, not a human RCT.

## 5. Sync (two-way round trip + same-card conflict)

Run: `bash ios/scripts/verify-sync.sh "iPhone 17 Pro"` (round trip) and
`bash ios/scripts/verify-sync-conflict.sh` (same-card conflict).

- **Round-trip verified:** phone→desktop (5) + desktop→phone (3) + offline-review-
  then-reconnect (4) → revlog id sets **byte-identical on both sides: 12 rows /
  12 unique** (no loss, no double-count). Rides Anki's own sync protocol via a
  self-hosted `anki-sync-server`.
- **Same-card offline conflict — VERIFIED** (`ios/scripts/verify-sync-conflict.sh`
  → `ios/docs/sync/conflict-evidence.json`). Two clients start from one synced
  collection, then BOTH review the **same card** offline: A grades it **Good** at
  T1, B grades it **Again** at a later T2. After syncing through the real
  `anki-sync-server`, the merge follows the documented rule exactly:
  - **later review by timestamp wins** — both devices converge to B's later
    (Again) card state, _not_ A's earlier Good (`winner_is_later_timestamp` +
    `loser_state_not_final`);
  - **loser's review is preserved** — both revlog rows survive on both devices
    (the earlier Good **and** the later Again), history never dropped;
  - both devices **converge** to one identical card record and identical revlog
    id sets. All 8 checks pass; this uses the shared Rust sync engine the iOS and
    desktop apps both drive (no custom logic).

## 6. Durability / crash test

Run: `just crash-test` (or `--kills N`) → `readymcat/eval/crash_durability.json`.

For each of 20 iterations a child engine opens a **throwaway** collection, commits
one review, and is **SIGKILL-ed the instant it commits** (no chance to clean up —
the "pulled the plug" case); the parent then reopens and checks integrity + that
the committed review survived. Never touches the real "User 1" profile.

| metric                                              | result     |
| --------------------------------------------------- | ---------- |
| hard kills (SIGKILL)                                | **20**     |
| corruption events (SQLite `pragma integrity_check`) | **0**      |
| lost-committed-review events                        | **0**      |
| revlog rows (exact, across all kills)               | 1 → **20** |

**Finding:** every reopen passed `integrity_check = ok`, and the revlog count was
exactly **1 → 20** across the 20 kills — each committed review survived its crash,
none lost, none double-counted. Durability rests on SQLite's atomic commit; the
test confirms an abrupt kill right after commit never corrupts the collection nor
drops the committed review.

## 7. Shipping

- **macOS `.dmg` — BUILT.** `./tools/build-installer` produced
  `out/installer/dist/anki-26.05-mac-apple.dmg` (**~214 MB**, unsigned). The
  clean-machine _install recording_ is the one remaining desktop step for the
  user (drag-to-Applications, launch, grade one card).
- **Signed phone build:** requires the user's Apple account — full steps in
  [`ios/docs/device-build.md`](../ios/docs/device-build.md). This is the
  highest-stakes remaining item (an app that does not run on a clean device caps
  the grade at 50%).

## Honest limitations (what did not work / is not done)

1. **Memory calibration passes its ECE gate but stays overconfident in the top
   bin** — on the synthetic stress test (§2) it predicts 0.94 / observes 0.86.
   Needs real data / per-user FSRS fitting for a real-cohort number.
2. **Teach-on-miss ablation is a null** on retention at equal time (§4) — reported,
   not hidden.
3. **Synthetic cohorts** — calibration (§2) and performance (§3) use labelled
   synthetic populations; no human cohort exists yet.
4. **User-only artifacts remain:** the signed phone build + clean-device install
   recordings + the demo-video recording (shot list in `readymcat/DEMO-SUNDAY.md`)
   require the user's Apple account and a camera.
