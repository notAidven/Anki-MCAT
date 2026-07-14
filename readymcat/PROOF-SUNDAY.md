# ReadyMCAT — Sunday PROOF (prove it, and ship both)

> **Start at [`SUBMISSION.md`](SUBMISSION.md)** — the single submission entry
> point (quickstart, a re-runnable verification table with freshly-measured
> numbers, the full demo walkthrough, and the honest gaps). This checklist is
> the requirement-by-requirement backing for it.

This is the consolidated **Sunday-deadline checklist** for ReadyMCAT: it maps every
Sunday requirement to concrete, in-repo evidence, and — where something is not done
yet — says exactly what is missing and how to finish it. It builds on the
Friday-deadline proof in [`PROOF-FRIDAY.md`](PROOF-FRIDAY.md) (desktop AI + held-out
eval, two-way sync, the three honest scores) and the Wednesday-MVP capture list in
[`PROOF.md`](PROOF.md); this document is scoped to _what the Sunday rubric asks for_.

- **Commit:** this file is added on `main` (base tree `73a5cb596`). Re-derive the
  commit that adds it with `git rev-parse HEAD`.
- **Repo:** public AGPL-3.0-or-later fork at
  [`github.com/notAidven/Anki-MCAT`](https://github.com/notAidven/Anki-MCAT),
  clone-and-run (`just run`).
- **Two apps, one engine:** a forked-Anki **desktop** app and a native **SwiftUI
  iOS** app, both driving the same Rust engine (`rslib`).
- Every "DONE/VERIFIED" row has an openable path. Every "PARTIAL/TO-DO" row says
  what is missing and a suggested approach, so nothing is dressed up as finished.

## The exact Sunday requirements (quoted from the spec)

From _Speedrun: A Desktop + Mobile Study App Built on Anki_, **"Due Sunday: prove
it, and ship both"**:

> **Models and evidence:**
>
> - Memory model is calibrated: a calibration chart and a score (Brier or log loss) on held-out reviews.
> - Performance model: accuracy on held-out exam-style questions.
> - Score mapping: your method written down, with a range.
> - Your study feature tested with three builds (see section 8), equal study time.
> - Honest reporting, including results that did not work.
>
> **Desktop and mobile:**
>
> - A packaged desktop installer and a packaged phone build (signed APK, or iOS via TestFlight or a sideload build).
> - Sync handles conflicts: if both devices review the same card offline, the merge is correct and documented.
> - Both apps run with AI off and still give a score.
>
> **Proof:**
>
> - The results report, the model descriptions, the Brainlift, and recordings of both builds installing and running on clean devices.

And from **"What to Hand In — Due Sunday 10:59 PM CT"** (section 12):

> - GitHub repo: a public AGPL-3.0-or-later fork with credit to Anki, your exam stated up front, build instructions for both apps, an architecture overview, the note on your Rust change, and the list of files you touched.
> - Demo video (3 to 5 minutes): a review session, your Rust change in action, a card synced from phone to desktop, the three scores with ranges, your AI features, and your test results.
> - Model descriptions: one short page each for the memory, performance, and readiness models, including the give-up rule.
> - Brainlift: As per Patrick's descriptions and class outline.

---

## What's actually left (updated — almost everything now landed)

The agent-doable Sunday items are **done and in-repo** (evidence in the tables
and detailed sections below, all synthesised in [`RESULTS.md`](RESULTS.md)):

1. ✅ **Memory calibration** — `just calibrate` → reliability chart
   [`eval/calibration.png`](eval/calibration.png) + Brier/log-loss/ECE
   [`eval/calibration.json`](eval/calibration.json) (§1.1).
2. ✅ **Desktop `.dmg` installer** — built:
   `out/installer/dist/anki-26.05-mac-apple.dmg` (~214 MB) (§2.1).
3. ✅ **Study-feature ablation** — `just ablation`, three builds at equal time,
   honest null reported (§1.4).
4. ✅ **Performance held-out / paraphrase validation** — `just perf-heldout`,
   distinct-from-memory quantified (§1.2).
5. ✅ **Same-card sync conflict** — `ios/scripts/verify-sync-conflict.sh` →
   [`../ios/docs/sync/conflict-evidence.json`](../ios/docs/sync/conflict-evidence.json) (§2.3).
6. ✅ **Consolidated results report** [`RESULTS.md`](RESULTS.md) + the crash test
   (kill mid-review ×20, zero corruption) `just crash-test` (§3.1).
7. ✅ **Model descriptions** — three standalone one-pagers
   [`models/`](models/) (§3.2).

**Genuinely left — these require the USER personally (Apple account + a camera):**

- ❌ **Packaged, _signed_ phone build** — everything is wired
  ([`../ios/docs/device-build.md`](../ios/docs/device-build.md)); the actual
  signed IPA/TestFlight build needs the user's Apple Developer account (§2.2).
- ❌ **Clean-device install/run recordings** (both apps) + the **phone→desktop
  sync recording** — the `.dmg` is built and the automated sync is verified; the
  recordings on clean devices are the user's to capture (§2.1/§2.2/§2.3).
- ❌ **Demo video (3–5 min)** — a precise shot-list is ready
  ([`DEMO-SUNDAY.md`](DEMO-SUNDAY.md)); the user records it (§3.4).

Everything else (score mapping, AI-off scores, the whole GitHub-repo hand-in, and
the Brainlift) was already done — see the tables.

---

## Sunday requirements checklist

Status legend: **✅ DONE** = built + evidence in-repo · **✅ VERIFIED** = an
automated run produced the artifact · **⚠️ PARTIAL** = partially there (what's
missing is noted) · **❌ TO-DO** = not built (what's needed + a suggested approach).
Section numbers (§) point to the detailed write-up below.

### Models and evidence

| # | Requirement                                                                         | Status      | Evidence / what's-left                                                                                                                                                                                                  |
| - | ----------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | Memory model **calibrated**: calibration chart + Brier/log-loss on held-out reviews | ✅ VERIFIED | `just calibrate` → [`eval/calibration.png`](eval/calibration.png) + [`eval/calibration.json`](eval/calibration.json): Brier 0.140, log-loss 0.468, ECE 0.066 on 3,535 held-out reviews; passes its gates but honestly flags top-bin overconfidence (§1.1). |
| 2 | Performance model: accuracy on **held-out** exam-style questions                    | ✅ VERIFIED | `just perf-heldout`: 56.2% [53.3–59.0%] over 1,200 held-out first attempts; distinct from memory (Pearson r=0.59, gap +0.14) (§1.2).                                                                                    |
| 3 | Score mapping: **method written down, with a range**                                | ✅ DONE     | PRD §"Honest scores" (readiness = 0.6·perf + 0.4·mem → 472–528, range-propagated) (§1.3).                                                                                                                               |
| 4 | Study feature tested with **three builds**, equal study time                        | ✅ VERIFIED | `just ablation`: ON/OFF/plain-Anki at equal time. Honest **null on retention** (ON 0.428 vs OFF 0.460); ON wins re-retrieval (0.560 vs 0.460) (§1.4).                                                                   |
| 5 | **Honest reporting**, including results that did not work                           | ✅ DONE     | PRD / brainlift / eval-README are candid about every gap (§1.5).                                                                                                                                                        |

### Desktop and mobile (shipping)

| # | Requirement                                                                         | Status      | Evidence / what's-left                                                                                                                                                                                             |
| - | ----------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 6 | **Packaged desktop installer** (macOS `.dmg`)                                       | ✅ VERIFIED | Built via `./tools/build-installer`: `out/installer/dist/anki-26.05-mac-apple.dmg` (~214 MB, unsigned). Clean-machine install _recording_ is the user's step (§2.1).                                               |
| 7 | **Packaged phone build** (signed APK / iOS TestFlight / sideload)                   | ⚠️ USER      | Everything wired ([`../ios/docs/device-build.md`](../ios/docs/device-build.md): universal xcframework, signing steps, TestFlight + sideload). The signed IPA needs the user's Apple account (§2.2).                |
| 8 | Sync **handles conflicts** (same card, both devices offline) — correct + documented | ✅ VERIFIED | `ios/scripts/verify-sync-conflict.sh` → [`../ios/docs/sync/conflict-evidence.json`](../ios/docs/sync/conflict-evidence.json): later-timestamp review wins, loser's revlog preserved, both devices converge (§2.3). |
| 9 | Both apps **run with AI off** and still give a score                                | ✅ VERIFIED | Friday-verified; scores come from the engine, never the generator (§2.4).                                                                                                                                          |

### Proof deliverables and docs

| #  | Requirement                                                                             | Status  | Evidence / what's-left                                                                                                                                                                                  |
| -- | --------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 10 | The **results report**                                                                  | ✅ DONE | [`RESULTS.md`](RESULTS.md) — every number (AI eval, calibration, held-out performance, ablation, sync round-trip + same-card conflict, crash, `.dmg`), honest incl. what did not work (§3.1).           |
| 11 | **Model descriptions**: one page each (memory / performance / readiness) + give-up rule | ✅ DONE | Three standalone one-pagers: [`models/memory.md`](models/memory.md), [`models/performance.md`](models/performance.md), [`models/readiness.md`](models/readiness.md), each with its give-up rule (§3.2). |
| 12 | **Brainlift**                                                                           | ✅ DONE | [`../docs/brainlift-mcat.md`](../docs/brainlift-mcat.md) (SPOVs, DOK tree, sources) (§3.3).                                                                                                             |
| 13 | **Recordings** of both builds installing + running on clean devices                     | ❌ USER | User step: `.dmg` is built (#6) and the signed-phone steps are ready (#7); the clean-device install/run recordings must be captured by the user (§2.1, §2.2).                                           |
| 14 | **Demo video (3–5 min)**                                                                | ❌ USER | User step: a precise shot-list/narration is ready in [`DEMO-SUNDAY.md`](DEMO-SUNDAY.md); the user records it (§3.4).                                                                                    |

### GitHub repo hand-in (section 12)

| #  | Requirement                                       | Status  | Evidence / what's-left                                                                                       |
| -- | ------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------ |
| 15 | Public **AGPL-3.0-or-later** fork, credit to Anki | ✅ DONE | [`../LICENSE`](../LICENSE) (AGPL-3.0 + BSD-3 portions); README credits Anki; pushed public (§4).             |
| 16 | **Exam stated up front**                          | ✅ DONE | [`../README.md`](../README.md) H1: "a study app for the **MCAT**" (§4).                                      |
| 17 | **Build instructions for both apps**              | ✅ DONE | README "Build & run (both apps)" + [`../ios/README.md`](../ios/README.md) (§4).                              |
| 18 | **Architecture overview**                         | ✅ DONE | README architecture mermaid + PRD "Tech stack" + [`../docs/architecture.md`](../docs/architecture.md) (§4).  |
| 19 | **Note on the Rust change**                       | ✅ DONE | [`../docs/readymcat-points-at-stake.md`](../docs/readymcat-points-at-stake.md) (why-in-Rust one-pager) (§4). |
| 20 | **List of files touched** (with merge difficulty) | ✅ DONE | Same doc, "Files touched" tables (§4).                                                                       |

---

## 1. Models and evidence

### 1.1 Memory-model calibration — ✅ VERIFIED

**Requirement.** A calibration chart plus a Brier (or log-loss) score on held-out
reviews: when the memory model says 80%, the student should recall ~80% of the time.

**Status — DONE.** `just calibrate` (→ [`eval/calibrate_memory.py`](eval/calibrate_memory.py))
scores the **shipping** FSRS model one-step-ahead on held-out reviews: for every
review after a card's first, the model is fit on the prior reviews (via the
`compute_memory_state` backend) and predicts that review (via the
`extract_fsrs_retrievability` SQL function the dashboard itself uses), then the
prediction is compared to the actual pass/fail. It writes a **reliability chart**
[`eval/calibration.png`](eval/calibration.png) and
[`eval/calibration.json`](eval/calibration.json): **Brier 0.140**, log-loss 0.468,
**ECE 0.066** over 3,535 held-out reviews, and it **passes its three gates**.
**Honest finding:** on a deliberately non-FSRS synthetic population the
default-parameter model is still **overconfident in its top bin** (predicts 0.94
/ observes 0.86; calibration slope ≈ 0.24) — reported, not hidden; a real-cohort
number needs a real review log (`just calibrate --collection PATH`).
The synthetic cohort is clearly labelled (no real review log exists yet).

**Suggested approach.** Score FSRS's predicted recall against held-out review
outcomes: bin predictions (e.g. deciles), plot observed-vs-predicted (reliability
diagram), and compute Brier + log-loss. Held-out outcomes have to come from
_somewhere_ a fresh collection lacks — so use accumulated real/demo review history,
or the synthetic bench deck's simulated reviews **labelled as synthetic**. Land it
as `readymcat/eval/calibrate_memory.py` + a `just calibrate` recipe that writes a
`calibration.json` and a chart, mirroring how [`eval/`](eval/) already works.

### 1.2 Performance model on held-out questions — ✅ VERIFIED

**Requirement.** Accuracy on held-out exam-style questions — and, per §7d of the
spec, the **paraphrase test** proving performance is a _distinct_ signal from memory.

**Status — DONE.** `just perf-heldout` (→
[`eval/performance_heldout.py`](eval/performance_heldout.py)) scores a **held-out,
reworded exam-style set** ([`eval/paraphrase_set.json`](eval/paraphrase_set.json) —
two paraphrase/transfer items per bank concept, disjoint wording) through the real
engine: **56.2% accuracy [53.3–59.0% Wilson], over 1,200 first attempts** (well past
the 30-attempt cutoff). It also runs the **paraphrase/distinctness test**: per
concept it compares memory recall (FSRS) against paraphrase accuracy and finds them
**distinct** — Pearson **r = 0.59** (r² ≈ 0.35 shared variance) with a **+0.14
transfer gap** (application below recall). Outcomes are a labelled synthetic cohort
(no human cohort yet); architectural distinctness (revlog first-attempts vs FSRS
state — different inputs/code path) is independent of that. The performance score's
method still ships as documented (Wilson 95%, give-up at 30) — see
[`../pylib/tests/test_readymcat_dashboard.py`](../pylib/tests/test_readymcat_dashboard.py).

**Suggested approach.** Take ~30 concepts; author 2 reworded, exam-style questions
each; compare per-concept recall against reworded-question accuracy **across
concepts**. If the two track too closely, report the coupling (performance is just
re-expressing memory). Report the gap either way — a null result is a real result.

### 1.3 Score mapping — ✅ DONE

**Requirement.** The readiness mapping written down, with a range.

**Evidence.** [`../docs/ReadyMCAT-PRD.md`](../docs/ReadyMCAT-PRD.md) §"Honest scores"
documents it end-to-end: readiness blends performance and memory into an ability
estimate (**0.6 performance + 0.4 memory**), maps it **linearly onto the real
472–528 scale**, **propagates both input ranges** into its own range, and **widens
the range** for the share of exam weight the bank does not yet cover — always
labelled a **heuristic, uncalibrated projection**, and shown only once _both_ memory
and performance clear their give-up thresholds. The contract is asserted in
[`../pylib/tests/test_readymcat_dashboard.py`](../pylib/tests/test_readymcat_dashboard.py)
(`test_seeded_demo_populates_all_three_scores`:
`472 <= readiness.range_low <= point <= range_high <= 528`). Calibrating that
mapping against real exam scores is out of scope by the spec's own §9 (graded as the
_bridge_, not a made-up final number) — and is flagged as such.

### 1.4 Study-feature ablation — ✅ VERIFIED (honest null)

**Requirement.** The chosen study feature tested with **three builds** at equal study
time: (1) full app, (2) feature off (ablation), (3) plain unmodified Anki.

**Status — DONE.** `just ablation` (→ [`eval/ablation.py`](eval/ablation.py)) runs the
**teach-on-miss** feature in all three builds at an **equal study-time budget**, with
the pre-registered primary metric (**corrected-concept re-retrieval rate**) stated up
front. Result (`eval/ablation.json`, `eval/ablation.png`), reported **honestly incl.
what did not work**:

- **NULL / negative on overall retention:** at equal time the ~22 s ladder means ON
  completes far fewer exposures (80 vs 148), so retention is **lower** — ON 0.428 vs
  OFF 0.460 vs plain 0.459.
- **Positive where designed:** ON wins the primary metric — corrected-concept
  **re-retrieval 0.560 vs 0.460** (+0.10) — and a sensitivity sweep shows ON beats
  OFF in **38%** of (ladder-cost × retrieval-benefit) settings.

This is a mechanistic simulation with stated effect sizes (not a human RCT); it also
summarises the live `readymcat_teach_on_miss_log.jsonl` instrumentation when present.

### 1.5 Honest reporting — ✅ DONE

**Requirement.** Honest reporting, including results that did not work.

**Evidence.** Honesty is the through-line of the write-ups, not an afterthought:
readiness is labelled **heuristic/uncalibrated** wherever it appears; the memory
range carries an explicit caveat that it is dispersion, **not** calibration error;
the paraphrase test and the ablation are named as **owed**; the `.dmg`, RSS
measurement, iOS device build, and same-card conflict test are all flagged as **not
done**; and the eval documents its **zero-shot / no-leakage** posture
([`eval/README.md`](eval/README.md) §"Contamination"). This checklist itself marks
six items ❌ rather than claiming them. What remains is to fold the _numbers_ from
§1.1 / §1.2 / §1.4 (including any that disappoint) into the results report once run.

---

## 2. Desktop and mobile (shipping)

### 2.1 Desktop installer (`.dmg`) — ✅ VERIFIED (built; recording is the user's step)

**Requirement.** A packaged desktop installer + a recording of it installing and
running on a clean machine.

**Status — BUILT.** `./tools/build-installer` (Anki's Briefcase installer under
[`../qt/installer`](../qt/installer)) produced the unsigned macOS `.dmg`:
**`out/installer/dist/anki-26.05-mac-apple.dmg` (~214 MB).** Rebuild + verify:

```bash
./tools/build-installer          # RELEASE=2 ./ninja installer (unsigned)
ls -lh out/installer/dist/       # anki-26.05-mac-apple.dmg
```

**Remaining (USER):** on a clean/second macOS account, screen-record double-clicking
the `.dmg`, dragging **ReadyMCAT** to Applications, launching, and grading one card
(this also proves the bank provisions from the packaged app). See
[`DEMO-SUNDAY.md`](DEMO-SUNDAY.md) for the shot list.

### 2.2 Packaged phone build — ⚠️ PREPPED (signing needs the user's Apple account)

**Requirement.** A packaged phone build — a signed APK, or iOS via TestFlight or a
sideload build — installing/running on a clean device.

**Status — everything wired; the signed build is the user's step.** The full,
exact recipe is in [`../ios/docs/device-build.md`](../ios/docs/device-build.md):
building the device slice, universal xcframework, signing in Xcode, and archiving a
signed `.ipa` for **TestFlight** or an **ad-hoc/sideload** install. This cannot be
completed in-repo because it requires the user's **Apple Developer account** — the
one genuinely user-blocked shipping item.

> **Grading hard-limit:** _"Either app does not run on a clean device: 50%
> maximum."_ This is the single highest-stakes remaining task — budget time for it.

**User steps (summary).** `xcodebuild -project ios/ReadyMCAT.xcodeproj -scheme
ReadyMCAT archive` → `-exportArchive`, then TestFlight or sideload; record it
launching on a physical device and running a review. (On-device sync also needs the
Mac's LAN IP + HTTPS — enable `rsios`'s already-wired `rustls` feature.)

### 2.3 Sync conflict handling — ✅ VERIFIED

**Requirement.** If both devices review the **same card** offline, the merge is
correct and documented.

**What's done.** Two-way sync is **verified working** on Anki's own protocol
([`PROOF-FRIDAY.md`](PROOF-FRIDAY.md) §2: `verify-sync.sh` → 12/12 identical revlog
ids, offline-then-reconnect). The conflict **rule is written down**:
[`../docs/ReadyMCAT-PRD.md`](../docs/ReadyMCAT-PRD.md) §"Two apps, one engine" —
_"the later review by timestamp wins, while the loser's review-log entry is preserved
so history is never silently dropped"_ — and the mechanics/limits are in
[`../ios/docs/sync/README.md`](../ios/docs/sync/README.md) §"Conflict handling"
(incremental syncs auto-reconcile by USN; a "keep this device's cards" toggle governs
the ambiguous full-sync case).

**Same-card conflict — now demonstrated.**
[`../ios/scripts/verify-sync-conflict.sh`](../ios/scripts/verify-sync-conflict.sh)
(driver [`../ios/scripts/sync_conflict.py`](../ios/scripts/sync_conflict.py)) makes
two clients start from one synced collection, then **both review the same card
offline** — A grades it Good at T1, B grades it Again at a later T2 — and sync
through the real `anki-sync-server`. Evidence
[`../ios/docs/sync/conflict-evidence.json`](../ios/docs/sync/conflict-evidence.json)
(all 8 checks pass): the **later-timestamp review wins** (both devices converge to
B's Again state, not A's earlier Good), the **loser's revlog row is preserved** (both
the Good and the Again survive on both devices), and the revlog id sets stay
identical. The existing `verify-sync.sh` still proves the different-card round trip
(12/12) with the real iOS Simulator.

**Still open (USER):** the Friday **phone-review→desktop `.mov`** recording
([`PROOF-FRIDAY.md`](PROOF-FRIDAY.md) §3) — the automated proof is done; the
on-screen recording is the user's to capture.

### 2.4 Both apps run with AI off — ✅ VERIFIED

**Requirement.** Both apps run with AI off and still give a score.

**Evidence.** The three scores are computed by the Rust engine
(`PointsAtStakeService`) purely from the revlog, **independent of the generator** —
detailed in [`PROOF-FRIDAY.md`](PROOF-FRIDAY.md) §1.4. Desktop generation is off
unless `OPENAI_API_KEY` is set (`is_enabled()` in
[`../qt/aqt/readymcat_ladder_gen.py`](../qt/aqt/readymcat_ladder_gen.py)); iOS
generation is off unless the AI toggle + proxy URL are set. The engine test
[`../pylib/tests/test_readymcat_dashboard.py`](../pylib/tests/test_readymcat_dashboard.py)
computes all three scores with **no generation at all**, and `just eval --stub` runs
the whole pipeline offline. (Both apps also review the bundled bank fully offline.)

---

## 3. Proof deliverables and docs

### 3.1 Results report — ✅ DONE

[`RESULTS.md`](RESULTS.md) consolidates **every** number, honest about what did not
work: the AI-ladder eval ([`eval/report.json`](eval/report.json), summarized in
[`PROOF-FRIDAY.md`](PROOF-FRIDAY.md) §1.3), the speed benchmark (`just bench`), the
**calibration** numbers (§1.1), the **performance held-out** numbers (§1.2), the
**ablation** result (§1.4, an honest null), the **sync** round-trip + same-card
conflict (§2.3), the **crash test** (below), and the **`.dmg`** (§2.1). Its "Honest
limitations" section explicitly calls out the ablation null and the calibration
overconfidence.

**Crash test (SIGKILL ×20, zero corruption) — ✅ VERIFIED.** `just crash-test`
(→ [`eval/crash_durability.py`](eval/crash_durability.py)) hard-**SIGKILLs the engine
20×** — each kill fired the instant a review is committed — on a **throwaway**
collection (never the real profile). Result
[`eval/crash_durability.json`](eval/crash_durability.json): **0 corruption events**
(every reopen `pragma integrity_check = ok`) and **0 lost committed reviews** (the
revlog count is exactly 1 → 20 across all 20 kills — every committed review survived
its crash, none double-counted).

### 3.2 Model descriptions — ✅ DONE

Three **standalone one-pagers** now exist, each ≤1 page (inputs → method → range →
**give-up rule** → known caveats): [`models/memory.md`](models/memory.md),
[`models/performance.md`](models/performance.md), and
[`models/readiness.md`](models/readiness.md). They mirror the PRD §"Honest scores":

- **Memory** — mean per-card FSRS recall, aggregated per AAMC topic, shown as a range
  with a confidence chip; give-up: hidden until **200 graded reviews and 50%
  coverage**.
- **Performance** — first-attempt accuracy on the ReadyMCAT notetypes, Wilson 95%
  interval; give-up: hidden until **30 first attempts**.
- **Readiness** — heuristic 472–528 projection (0.6·perf + 0.4·mem), range-
  propagated; give-up: shown only once **both** memory and performance qualify.

**Done.** The spec asked for **one short page each**; the three cards above deliver
exactly that, and each now also links its validation harness (`just calibrate`,
`just perf-heldout`) and latest numbers.

### 3.3 Brainlift — ✅ DONE

[`../docs/brainlift-mcat.md`](../docs/brainlift-mcat.md) — owner, purpose, in/out of
scope, the two spiky points of view (treated as claims to test), the DOK knowledge
tree, and a full sources list — kept in lock-step with the PRD.

### 3.4 Demo video (3–5 min) — ❌ USER (shot-list ready)

A precise **shot list + narration** is ready in [`DEMO-SUNDAY.md`](DEMO-SUNDAY.md),
covering everything the spec requires: a review session; the **Rust change in
action** (points-at-stake ordering — high-yield weak-topic cards first, and a
`ReadyMCAT::struggling` card jumping its topic-mates); a card **synced from phone to
desktop**; the **three scores with ranges**; the **AI feature** (teach-on-miss ladder
generated on a missed authorless card); and the **test results** (`just check`,
`just eval`, `just calibrate`, `just perf-heldout`, `just ablation`, `just bench`).
The recording itself is the user's to capture (screen + camera), reusing the `.dmg`
install clip (§2.1) and the signed-phone clip (§2.2).

---

## 4. GitHub repo hand-in — ✅ DONE

Every section-12 repo requirement is satisfied in-tree:

| Hand-in item                          | Where                                                                                                                          |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Public AGPL-3.0-or-later fork         | [`../LICENSE`](../LICENSE) — AGPL-3.0-or-later (+ BSD-3 portions); pushed at `github.com/notAidven/Anki-MCAT`                  |
| Credit to Anki                        | [`../README.md`](../README.md) §"Content, licensing & credits" (forks + credits Anki)                                          |
| Exam stated up front                  | [`../README.md`](../README.md) H1 — "a desktop + mobile study app for the **MCAT**"                                            |
| Build instructions for both apps      | [`../README.md`](../README.md) §"Build & run (both apps)" + [`../ios/README.md`](../ios/README.md)                             |
| Architecture overview                 | [`../README.md`](../README.md) architecture mermaid + [`../docs/architecture.md`](../docs/architecture.md) + PRD §"Tech stack" |
| Note on the Rust change (why in Rust) | [`../docs/readymcat-points-at-stake.md`](../docs/readymcat-points-at-stake.md) §"Why this belongs in Rust"                     |
| List of files touched (merge risk)    | [`../docs/readymcat-points-at-stake.md`](../docs/readymcat-points-at-stake.md) §"Files touched"                                |

---

## 5. Verify these claims yourself

```bash
# repo hand-in facts
head -3 LICENSE                                   # AGPL-3.0-or-later
head -1 README.md                                 # exam (MCAT) stated up front
ls docs/readymcat-points-at-stake.md docs/brainlift-mcat.md docs/architecture.md

# AI-off scores + the shipped AI eval (Friday, still green)
just eval --stub                                  # whole pipeline offline, no network
python -c "import json;print(json.load(open('readymcat/eval/report.json'))['aggregate'])"

# sync verified: round-trip (Friday) + same-card conflict (this session)
tail -n 3 ios/docs/sync/verify-run.log            # ==== SYNC ROUND-TRIP VERIFIED ====
tail -n 3 ios/docs/sync/conflict-run.log          # ==== SAME-CARD SYNC CONFLICT VERIFIED ====

# the model evals + their artifacts now exist and are regenerable
just --list | grep -E 'calibrate|perf-heldout|ablation|crash-test'
python -c "import json;print(json.load(open('readymcat/eval/calibration.json'))['brier'])"      # §1.1
python -c "import json;print(json.load(open('readymcat/eval/performance_heldout.json'))['overall_performance'])"  # §1.2
python -c "import json;print(json.load(open('readymcat/eval/crash_durability.json'))['all_passed'])"  # §3.1

# the desktop installer is built
ls -lh out/installer/dist/                        # anki-26.05-mac-apple.dmg (~214 MB)  §2.1
```

All paths in this document are relative to `readymcat/` (the repository root is the
`anki/` working tree, `/Users/evacab/Desktop/Anki-MCAT/anki`).
