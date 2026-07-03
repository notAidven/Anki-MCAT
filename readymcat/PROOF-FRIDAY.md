# ReadyMCAT — Friday PROOF

This is the consolidated **Friday-deadline proof** for ReadyMCAT: it maps every
Friday requirement to concrete, in-repo evidence and quotes the real numbers and
file paths that back each claim. It complements the Wednesday-MVP capture list in
[`PROOF.md`](PROOF.md) and the feature/architecture write-up in
[`README.md`](README.md); this document is scoped to _what the Friday rubric
asks for_.

- **Commit:** `dfa73e701` (branch this proof is captured on: `readymcat-friday-proof`,
  branched from `main`). Re-derive with `git rev-parse HEAD`.
- **Two apps, one engine:** a forked-Anki **desktop** app and a native **SwiftUI
  iOS** app, both driving the same Rust engine (`rslib`).
- **One AI feature:** runtime generation of teach-on-miss "ladders" — measured,
  not assumed, by a held-out eval (`readymcat/eval/`).
- Numbers below are read verbatim from
  [`readymcat/eval/report.json`](eval/report.json) (stamped `"mode": "live"`) and
  the sync evidence under [`../ios/docs/sync/`](../ios/docs/sync/). Nothing here is
  fabricated; every figure has a path you can open.

---

## Friday requirements checklist

Status legend: **DONE** = built + evidence in-repo · **VERIFIED** = an automated
run produced the captured artifact · **ACTION REQUIRED** = a manual screen
recording the user still needs to capture (commands provided).

| #  | Requirement                                                            | Status          | Evidence (path)                                                                                                                                                                                                                                                                                                                               |
| -- | ---------------------------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | Desktop AI note: what was built, why, what was skipped                 | DONE            | [`docs/ReadyMCAT-PRD.md`](../docs/ReadyMCAT-PRD.md) §"Runtime ladder generation: the AI feature"; [`eval/README.md`](eval/README.md); summarized in [§1.1](#11-ai-note)                                                                                                                                                                       |
| 2  | Source traceability: each generated ladder grounded in a named source  | DONE            | [`readymcat/tools/ladder_gen.py`](tools/ladder_gen.py) (`CardContext`, `grounding_score`, prompt); [§1.2](#12-source-traceability)                                                                                                                                                                                                            |
| 3  | Eval: accuracy + wrong-answer rate on held-out set, with the cutoff    | DONE (live)     | [`eval/report.json`](eval/report.json) `"mode":"live"`; [§1.3](#13-eval-accuracy-wrong-answer-rate-and-the-cutoff)                                                                                                                                                                                                                            |
| 4  | Baseline = TF-IDF retrieval of the nearest authored ladder             | DONE            | [`eval/report.json`](eval/report.json) `baseline` field; [`eval/run_eval.py`](eval/run_eval.py); [§1.3](#13-eval-accuracy-wrong-answer-rate-and-the-cutoff)                                                                                                                                                                                   |
| 5  | AI-vs-baseline side-by-side + gates + how to reproduce                 | DONE            | [`eval/report.json`](eval/report.json); [`eval/README.md`](eval/README.md); [§1.3](#13-eval-accuracy-wrong-answer-rate-and-the-cutoff)                                                                                                                                                                                                        |
| 6  | Score-with-AI-off: the 3 scores work with generation disabled          | DONE            | [`pylib/tests/test_readymcat_dashboard.py`](../pylib/tests/test_readymcat_dashboard.py); [`qt/aqt/readymcat_ladder_gen.py`](../qt/aqt/readymcat_ladder_gen.py) `is_enabled()`; [§1.4](#14-score-with-ai-off)                                                                                                                                  |
| 7  | Two-way sync, no lost / double-counted reviews                         | VERIFIED        | [`ios/docs/sync/verify-run.log`](../ios/docs/sync/verify-run.log); identical [`phone-revlog-ids.txt`](../ios/docs/sync/phone-revlog-ids.txt) / [`desktop-revlog-ids.txt`](../ios/docs/sync/desktop-revlog-ids.txt); [`ios/scripts/verify-sync.sh`](../ios/scripts/verify-sync.sh); [§2.1](#21-two-way-sync-no-lost-or-double-counted-reviews) |
| 8  | Offline review, then sync on reconnect                                 | VERIFIED        | [`ios/docs/sync/verify-run.log`](../ios/docs/sync/verify-run.log) step 5; [§2.2](#22-offline-review-then-sync-on-reconnect)                                                                                                                                                                                                                   |
| 9  | Phone shows the 3 scores with ranges + give-up                         | DONE            | [`ios/docs/sync/phone-dashboard-3scores.png`](../ios/docs/sync/phone-dashboard-3scores.png); [`ios/docs/02-dashboard.png`](../ios/docs/02-dashboard.png); [`ios/docs/10-dashboard-populated.png`](../ios/docs/10-dashboard-populated.png); [§2.3](#23-phone-shows-the-three-scores-with-ranges--give-up)                                      |
| 10 | Proof: eval numbers + baseline comparison                              | DONE            | [§1.3](#13-eval-accuracy-wrong-answer-rate-and-the-cutoff)                                                                                                                                                                                                                                                                                    |
| 11 | Proof: **recording** of a phone review appearing on desktop after sync | ACTION REQUIRED | Capture steps in [§3](#3-the-recording-phone-review--desktop-after-sync); artifact placeholder below                                                                                                                                                                                                                                          |
| 12 | Build & run for both apps                                              | DONE            | [§4](#4-build--run)                                                                                                                                                                                                                                                                                                                           |

---

## 1. Desktop AI

ReadyMCAT has exactly **one** runtime AI feature: when a student misses a card
that has **no authored teach-on-miss ladder** (an imported deck or their own
cards), the desktop app generates a short, source-grounded ladder of guiding
`{q, a}` sub-questions at runtime so the retrieval-first correction reaches every
card, not just the pre-loaded bank. Everything else in the app (the bank, the
diagnostic, the three scores) runs with **no model calls**.

### 1.1 AI note

_Summarized from [`docs/ReadyMCAT-PRD.md`](../docs/ReadyMCAT-PRD.md)
§"Runtime ladder generation: the AI feature" and [`eval/README.md`](eval/README.md)._

**What was built.** A dependency-free generation core,
[`readymcat/tools/ladder_gen.py`](tools/ladder_gen.py) (prompt + parser +
guardrail validators + a stdlib-`urllib` OpenAI call), shared **verbatim** by the
desktop runtime host [`qt/aqt/readymcat_ladder_gen.py`](../qt/aqt/readymcat_ladder_gen.py)
and the eval harness — so what ships is exactly what is scored. The reviewer
([`qt/aqt/reviewer.py`](../qt/aqt/reviewer.py)) runs generation on a background
thread behind a brief "building guiding questions…" state, caches each validated
ladder per-note in `readymcat_generated_ladders.json`, and then hands it to the
**same** `_teachOnMissStart` flow that renders authored ladders.

**Why.** ReadyMCAT's spiky point of view is that a wrong-answer explanation is
passive reading; the fix is to make the student _retrieve_ the correction through
guiding sub-questions. Authored ladders ship on every bundled card, but that only
covers ReadyMCAT's own bank. Runtime generation closes the gap the PRD flagged as
the #1 next step so teach-on-miss works on _any_ deck.

**What was skipped (honest scope).** Generation runs on **both desktop and iOS**;
on iOS it is routed through a **server-side proxy** (a Cloudflare Worker,
`ios/backend/openai-proxy`) so **no OpenAI key ships on the phone** — the key is a
server secret and the device holds only a non-secret proxy URL and a low-value
app token. There is **no other runtime AI**: no generated
flashcards, no chatbot. Generation is **off entirely** when no `OPENAI_API_KEY` is
present. The guardrails are **lexical proxies** (honest heuristics, not a
calibrated model), and their thresholds are named constants the calibration work
will tune. The generator **never writes** the dashboard's memory / performance /
readiness scores — the same honesty firewall the diagnostic respects (see
[§1.4](#14-score-with-ai-off)).

### 1.2 Source traceability

Every generated ladder is grounded in a **named source** carried by the card
itself, enforced in [`readymcat/tools/ladder_gen.py`](tools/ladder_gen.py):

- **The grounding material is explicit.** `CardContext` collects the card's
  `question`, `answer`/explanation, and its `Source` field into one
  `grounding_text`; `has_source` records whether the card cited a real source (else
  generation is flagged **"card-only"**, grounded on the answer text alone). The
  desktop host `build_context()` reads the note's `Source` field to populate it.
- **The prompt forbids ungrounded facts.** `build_messages()` instructs the model:
  _"Every sub-answer must be grounded ONLY in the provided material — do not
  introduce facts that are not supported by it,"_ and the first rung must not give
  away the answer.
- **A deterministic grounding gate blocks un-traceable ladders before they are
  ever shown.** `grounding_score()` computes, per rung, the fraction of the
  sub-answer's content words that trace back to the card's own material; a ladder
  passes only when the mean is ≥ `GROUNDING_MIN` (0.5). `validate_ladder()` makes
  schema + no-answer-leak + grounding **hard gates** (`ValidationResult.passed`),
  so a ladder shown to a student is always well-formed, retrieval-first, and
  traceable to a named source.

This is the same grounding check the eval reports as `groundingMean` /
`groundingPassRate` below, so the traceability claim is _measured_, not asserted.

### 1.3 Eval: accuracy, wrong-answer rate, and the cutoff

The harness ([`readymcat/eval/run_eval.py`](eval/run_eval.py)) runs the shared
generation core over a **held-out golden set** of **16** MCAT cards spanning all
four sections (B/B, C/P, P/S, CARS) — each standing in for a missed card with no
authored ladder — and scores three layers: the deterministic guardrails (schema /
answer-leak / grounding), an **LLM-as-judge** (1–5 pedagogical rubric, danger
flags), and a **beats-a-baseline** comparison. The captured numbers are read
verbatim from [`readymcat/eval/report.json`](eval/report.json), stamped
`"mode": "live"` (`genModel: gpt-4o-mini`, `judgeModel: gpt-4o`, n = **16**).

**The cutoff.** A card counts toward **accuracy** only when its ladder passes
**all** deterministic guardrails **and** the judge (score **≥ 4/5** with no danger
flag) — i.e. only ladders good enough to actually show a student. **Wrong-answer
rate** is the dangerous failure mode: the fraction of ladders that leak the
answer, are judged factually wrong / off-topic (not grounded), or fail to produce
a usable ladder at all.

#### AI vs baseline (side-by-side)

| Metric                                                   | AI (generated)    | Baseline (TF-IDF retrieval) |
| -------------------------------------------------------- | ----------------- | --------------------------- |
| Accuracy (passes guardrails + judge cutoff)              | **0.875** (87.5%) | 0.25 (25%)                  |
| Wrong-answer rate (leak / wrong / off-topic / no ladder) | **0.062** (6.2%)  | 0.5 (50%)                   |
| Source-grounding mean                                    | **0.73**          | 0.33                        |
| Grounding pass-rate                                      | **0.938** (93.8%) | 0.25 (25%)                  |
| Judge mean (1–5)                                         | **4.625**         | 3.062                       |
| Schema pass-rate                                         | 1.0 (100%)        | 1.0 (100%)                  |
| Answer-leak rate                                         | 0.0               | 0.0                         |
| Win-rate vs baseline (head-to-head)                      | **0.688** (68.8%) | —                           |

_(n = 16 held-out cards; judge calibration `agreement = 1.0` over 2 hand-labelled
cases.)_

#### Baseline

The baseline is the PRD's "keyword/vector baseline", implemented as **TF-IDF
cosine retrieval of the nearest _authored_ sub-question ladder** from
[`../subquestions.json`](../subquestions.json). `report.json` records it exactly:
`"baseline": "TF-IDF retrieval of nearest authored ladder (subquestions.json)"`.
The retrieved ladder is reused verbatim and scored on the missed card by the
**same** guardrails + judge, so the comparison is apples-to-apples. Because the
authored bank is disjoint from the held-out set's identifiers and the generator
prompt is **zero-shot**, there is no train/test leakage.

#### Gates (all PASS on the live run)

`report.json` → `gates.passed: true`, with every gate green:

| Gate                         | Bar                            | Result |
| ---------------------------- | ------------------------------ | ------ |
| `schema_100pct`              | schema valid = 100%            | PASS   |
| `no_answer_leak`             | answer-leak = 0%               | PASS   |
| `grounding_ok`               | source-grounding ≥ 90%         | PASS   |
| `judge_mean_ok`              | judge mean (generated) ≥ 3.5/5 | PASS   |
| `ai_higher_accuracy`         | AI accuracy > baseline         | PASS   |
| `ai_lower_wrong_answer_rate` | AI wrong-answer < baseline     | PASS   |
| `beats_baseline`             | win-rate vs baseline > 50%     | PASS   |

#### Reproduce

```bash
just eval           # LIVE: generate + judge via the OpenAI API (needs OPENAI_API_KEY)
just eval --stub    # OFFLINE: deterministic stub generator + stub judge, no network (CI-safe)

# write the full per-card report shown above:
just eval --report readymcat/eval/report.json
```

`just eval` runs `readymcat/eval/run_eval.py`, which loads the shared core
`readymcat/tools/ladder_gen.py` by path, so the eval can never drift from what
ships. The run prints the PASS/FAIL gate table and exits non-zero if any gate
fails.

### 1.4 Score-with-AI-off

The three headline scores are computed by the Rust engine
(`PointsAtStakeService`, exposed via the `points_at_stake_queue` backend method)
purely from the review log — **entirely independent of the AI generator**:

- **Memory** — mean FSRS recall, shown as a range with a confidence chip; hidden
  until 200 graded reviews + 50% coverage.
- **Performance** — first-attempt accuracy on the ReadyMCAT question notetypes,
  read from the revlog; hidden until 30 attempts.
- **Readiness** — a heuristic 472–528 projection gated on BOTH memory and
  performance, always labelled "heuristic".

**The design proves independence two ways:**

1. **The generator is fully optional.** `is_enabled()` in
   [`qt/aqt/readymcat_ladder_gen.py`](../qt/aqt/readymcat_ladder_gen.py) returns
   `False` when `READYMCAT_DISABLE_LADDER_GEN` is set **or** no `OPENAI_API_KEY` is
   present — _"When False the reviewer behaves exactly as before generation
   existed."_ The scores are computed on this same no-generation path.
2. **A test computes all three scores with no generation at all.**
   [`pylib/tests/test_readymcat_dashboard.py`](../pylib/tests/test_readymcat_dashboard.py)
   seeds reviews directly and asserts the engine produces all three scores with
   ranges and give-up rules, without ever invoking `ladder_gen`:
   - `test_performance_reads_first_attempt_accuracy_and_gates_readiness` — 35 seeded
     first attempts (25 hits) → `performance.mean == 25/35`, and readiness/memory
     correctly **abstain** below their thresholds.
   - `test_later_reviews_do_not_change_first_attempt_verdict` — only a card's first
     graded review counts toward performance.
   - `test_seeded_demo_populates_all_three_scores` — the demo seeder pushes past
     every give-up threshold so Memory, Performance **and** Readiness all render
     populated, with `472 <= readiness.range_low <= point <= range_high <= 528`.

The PRD states the firewall directly: the generator _"never writes the dashboard's
memory / performance / readiness scores."_ So the three scores work identically
whether or not the AI feature is on.

---

## 2. Mobile

### 2.1 Two-way sync (no lost or double-counted reviews)

Sync is built **entirely on Anki's own collection-sync protocol and self-hostable
sync server** (`rslib/src/sync/**`), not a custom sync. Reusing Anki's protocol is
what guarantees correctness: every review is a `revlog` row keyed by its
epoch-millisecond id and reconciled by USN, so the server can neither lose nor
duplicate one. The iOS `SyncManager` drives the same `rslib` sync client through
the `rsios` FFI; the "desktop" side is the same `anki.collection.Collection` API
the Qt app uses. Full architecture: [`ios/docs/sync/README.md`](../ios/docs/sync/README.md).

**The no-loss / no-double-count proof is the revlog id sets being identical on both
ends.** [`ios/scripts/verify-sync.sh`](../ios/scripts/verify-sync.sh) runs the whole
round-trip automatically and asserts it; the captured transcript
[`ios/docs/sync/verify-run.log`](../ios/docs/sync/verify-run.log) ends with:

```
OK: revlog id sets IDENTICAL on phone & desktop: 12 rows, 12 unique (no loss, no double-count)
==== SYNC ROUND-TRIP VERIFIED ====
```

Both [`phone-revlog-ids.txt`](../ios/docs/sync/phone-revlog-ids.txt) and
[`desktop-revlog-ids.txt`](../ios/docs/sync/desktop-revlog-ids.txt) contain the
**same 12 ids** (byte-identical files):

```
1783010216967   1783010216974   1783010218691
1783010216969   1783010218689   1783010221142
1783010216970   1783010218690   1783010221144
1783010216972                   1783010221145
                                1783010221147
```

The round-trip the log records: phone full-upload → desktop full-download
(shared lineage, revlog 0) → **phone reviews 5, syncs; desktop pulls → both == 5**
→ **desktop reviews 3, syncs; phone pulls → both == 8** → offline batch (below) →
**both == 12**. Server-side confirmation that the iOS client really drove Anki's
protocol is in [`server-ios-requests.log`](../ios/docs/sync/server-ios-requests.log):
lines tagged `client="26.05,46374f93,ios"` hitting `/sync/meta`, `/sync/upload`,
`/sync/start`, `/sync/applyChanges`, `/sync/chunk`, `/sync/finish`.

### 2.2 Offline review then sync on reconnect

Step 5 of the same verified run
([`verify-run.log`](../ios/docs/sync/verify-run.log)): the phone **reviews 4 cards
offline** (pointed at an unreachable endpoint), a sync attempt **fails gracefully
with no data loss**, then it reconnects and syncs — and the desktop pulls all of
them, landing both sides at **12**:

```
>> 5) phone reviews 4 OFFLINE, sync fails gracefully, then reconnects
OK: offline reviews synced after reconnect
```

The script asserts `phone_revlog == 12` **both** immediately after the offline
reviews and after the failed sync attempt — proving the failed attempt lost
nothing — before the reconnect sync carries them to the desktop.

### 2.3 Phone shows the three scores with ranges + give-up

The native iOS app renders the same three honest scores, each **as a range with a
confidence level** and each **hidden behind an explicit give-up rule** until there
is enough evidence:

- [`ios/docs/02-dashboard.png`](../ios/docs/02-dashboard.png) — a fresh collection:
  all three read **"Not enough data" / "Needs evidence"**, with the thresholds
  spelled out (Memory: "Hidden until 200 graded reviews and 50% coverage",
  Reviews 0/200; Performance: "hidden until 30 attempts", Attempts 0/30;
  Readiness: "heuristic · 472–528", projected only once Memory and Performance
  qualify).
- [`ios/docs/sync/phone-dashboard-3scores.png`](../ios/docs/sync/phone-dashboard-3scores.png)
  — **after sync**, the same three cards now reflect the synced review count
  (Reviews **12**/200, Attempts **12**/30) while still honestly abstaining until the
  thresholds are met — proving the scores update from the synced revlog.
- [`ios/docs/10-dashboard-populated.png`](../ios/docs/10-dashboard-populated.png) —
  the populated state, showing the three scores rendered with their ranges once
  past the give-up thresholds.

The give-up ("needs evidence") behaviour is the same one enforced by the engine
test in [§1.4](#14-score-with-ai-off), so the phone UI and the tested backend
contract agree.

---

## 3. The recording (phone review → desktop after sync)

This is the one artifact that must be **manually screen-recorded** — an automated
script cannot capture a screen recording of two live apps. Everything needed to
produce it is scripted; you press record.

> **Video artifact:** `ios/docs/sync/phone-review-appears-on-desktop.mov`
> _(placeholder — record and drop the file here, then link it from this line)._

### How to capture the recording

**Option A — record the automated round-trip (simplest, deterministic).** Start
the self-hosted server, then screen-record the verifier driving the Simulator +
headless desktop client end-to-end:

```bash
# terminal 1 — self-hosted Anki sync server on localhost (127.0.0.1:27701)
export PATH="$HOME/.cargo/bin:$PATH"
ios/scripts/sync-server.sh

# terminal 2 — start your screen recording (QuickTime ⌘⌥R, or `xcrun simctl io booted recordVideo out.mov`),
# then run the end-to-end proof against the iOS Simulator:
ios/scripts/verify-sync.sh "iPhone 17 Pro"
```

Record the terminal through to `==== SYNC ROUND-TRIP VERIFIED ====` alongside the
booted Simulator. This captures a phone review syncing up and the desktop client
pulling it (and the reverse), with the identical-revlog assertion on screen.

**Option B — record the two live apps (most convincing visually).**

1. Start the server: `ios/scripts/sync-server.sh`.
2. Launch the iOS app in the Simulator (`ios/scripts/run-sim.sh "iPhone 17 Pro"`),
   open its **Sync** tab (see [`phone-sync-tab.png`](../ios/docs/sync/phone-sync-tab.png)),
   enter `http://127.0.0.1:27701/` + `rmcat`/`rmcat`, and log in.
3. Point the desktop app at the same server (Preferences → Syncing → self-hosted
   URL, or `SYNC_ENDPOINT=http://127.0.0.1:27701/ just run`).
4. **Record:** answer/grade a card **on the phone** → tap **Sync now** → sync the
   **desktop** → show the phone's review now present on the desktop (revlog count
   or the card's updated state). Use a throwaway server profile — do **not** point
   at anyone's real Anki account.

---

## 4. Build & run

### Desktop (forked Anki)

```bash
export PATH="$HOME/.cargo/bin:$PATH"    # rustup toolchain on PATH
git submodule update --init             # ftl/* and qt/installer/* templates
just run                                # build from source + launch ReadyMCAT
# full lint + build + tests (must be green):
just check
```

First launch provisions the bundled bank (**1,075 cards** across four decks) with
**zero import** and opens the diagnostic; teach-on-miss and the honest-scores
dashboard are reachable from the study flow and Tools menu. See [`README.md`](README.md)
and [`PROOF.md`](PROOF.md) for the full desktop capture list.

### iOS (SwiftUI + shared Rust engine)

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cd ios
./scripts/build-rust.sh                 # cross-compile rslib -> RsiosFFI.xcframework
./scripts/run-sim.sh                    # build the SwiftUI app + boot it in the Simulator
# or open ios/ReadyMCAT.xcodeproj in Xcode and Run on a Simulator target
```

`build-rust.sh` builds `rsios` for `aarch64-apple-ios-sim` and packages the
`.xcframework`; `run-sim.sh` compiles the Swift app (no `.xcodeproj` needed),
bundles the collection + sidecars, and installs/launches it on the Simulator.

---

## 5. Verify these numbers yourself

```bash
# eval numbers quoted in §1.3 (live run):
python -c "import json; a=json.load(open('readymcat/eval/report.json'))['aggregate']; print(a)"
grep '"mode"' readymcat/eval/report.json          # -> "mode": "live"

# sync proof in §2 (must be byte-identical, 12 rows):
diff ios/docs/sync/phone-revlog-ids.txt ios/docs/sync/desktop-revlog-ids.txt && echo IDENTICAL
wc -l ios/docs/sync/phone-revlog-ids.txt          # -> 12
tail -n 3 ios/docs/sync/verify-run.log            # -> ==== SYNC ROUND-TRIP VERIFIED ====
```

All paths in this document are relative to the repository root
(`/Users/evacab/Desktop/Anki-MCAT/anki`, i.e. the `anki/` working tree).
