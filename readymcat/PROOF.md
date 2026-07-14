# ReadyMCAT — Proof Checklist (Wednesday MVP)

> **Friday rubric?** See [`PROOF-FRIDAY.md`](PROOF-FRIDAY.md) — the consolidated
> Friday-deadline proof that maps every Friday requirement (desktop AI + eval,
> two-way sync, the three scores) to concrete in-repo evidence with real numbers.
> This file is the broader Wednesday-MVP capture list.

This is the capture checklist for the ReadyMCAT demo/handin. Two items are
**manual screen recordings** (the clean-machine install and the iOS Simulator
review) — the commands below produce the artifacts; you press record. As of this
writing the checklist is defined; the recordings and the `.dmg` are **not yet
captured/built** (see the status column at the end).

All commands run from the repository root (the `anki/` working tree).
Prerequisites: Rust via `rustup` on `PATH` (`source "$HOME/.cargo/env"`), Xcode
for iOS, and the git submodules initialised (`git submodule update --init`).

---

## 0. Record the exact commit

```bash
git rev-parse HEAD                       # commit hash
git log --oneline -8                     # recent history
git status                               # should be clean
git submodule status                     # ftl/* and qt/installer/* present
```

Paste the commit hash at the top of the demo doc/video description.

## 1. Clean build from source (desktop)

Proves it builds from scratch, not from a dirty cache.

```bash
./tools/clean                            # remove out/ build artifacts
just check                               # full build + lint + tests, must be green
just run                                 # launches ReadyMCAT (forked Anki) from source
```

Capture: terminal showing `just check` finishing green (green on the current
tree), then the app window.

## 2. Build the macOS .dmg installer

Proves a real installable artifact (Anki's Briefcase installer, unsigned for the
MVP — no Apple credentials required). **Not yet built from the current tree** —
the recipe below is how to produce it.

```bash
./tools/build-installer                  # = RELEASE=2 ./ninja installer (unsigned)
ls -lh out/installer/dist/               # the .dmg (and .pkg) land here
open out/installer/dist/                 # reveal in Finder
```

**Manual recording (clean machine):** on a second/clean macOS user account,
double-click the `.dmg`, drag **ReadyMCAT** to Applications, launch it, and show
it opening to the pre-loaded bank and grading one card (this also verifies the
bank provisions from the packaged app, not just from a source checkout). Record
the whole flow.

## 3. Pre-loaded bank + desktop review + teach-on-miss (the spiky feature)

```bash
just run
```

1. **Zero import.** On first launch the app provisions the bundled bank straight
   into a fresh collection — **1,075 cards** across four decks (`ReadyMCAT` = 414
   MCQ, `ReadyMCAT::Free Response` = 410, `ReadyMCAT::Passages` = 174 over 36
   passages, `ReadyMCAT::Passages::CARS` = 77 over 15 passages) — and drops
   `taxonomy.json`, `subquestions.json`, and `diagnostic_quiz.json` next to it.
   Capture the four decks and their counts.
2. Study any deck and answer a question wrong (an MCQ pick, a type-in, or a
   passage MCQ). The reviewer grades it **Again**.
3. Record: the **sub-question ladder** appears instead of the answer; self-mark
   each rung; the main question re-shows; on a second miss the full answer is
   revealed ("earned"), the resource link is surfaced, and the note is tagged
   `ReadyMCAT::struggling`.
4. Show `readymcat_teach_on_miss_log.jsonl` (next to the collection) recording
   the events.
5. Re-build the queue and show the struggling concept resurfaced near the top
   (points-at-stake boost).

## 4. First-launch diagnostic

```bash
just run     # first launch auto-opens the diagnostic; retake via Tools → ReadyMCAT Diagnostic
```

Capture: the short diagnostic administering the short mode — one item per category
drawn from the 37-item bank (i.e. 31 items) — spanning all 31 AAMC content
categories. It seeds the points-at-stake weakness prior and **never**
shows a score or writes the dashboard's memory/performance/readiness numbers (a
guardrail test enforces this).

## 5. Honest-memory dashboard

```bash
just run     # then: Tools → ReadyMCAT Dashboard
# optional: Tools → Load ReadyMCAT demo data (SYNTHETIC) to preview before 200 real reviews
```

Capture: per-topic mastery/weakness, the memory score shown **as a range** with a
confidence chip, the coverage map, and — before 200 graded reviews / 50%
coverage — the explicit "not enough data yet" give-up state. The demo seeder
(`readymcat/tools/seed_demo_dashboard.py`) populates clearly-labeled synthetic
reviews so the view can be previewed without hundreds of real ones.

## 6. iOS Simulator review (shared engine)

Proves the same Rust engine runs on the phone — in the engine's **default** queue
order (points-at-stake is a desktop-side ordering and is not switched on for iOS
yet).

```bash
cd ios
./scripts/build-rust.sh                  # cross-compile rslib -> RsiosFFI.xcframework
./scripts/run-sim.sh                     # build & boot the SwiftUI app in the Simulator
# or open ios/ReadyMCAT.xcodeproj in Xcode and Run on a Simulator target
```

**Manual recording (Simulator):** record a real review session — fetch a card,
reveal, grade — running on the shared engine in the iOS Simulator.

## 7. Tests (engine + integration)

```bash
just check                               # clippy, mypy, ruff, eslint, svelte,
                                         # typescript, vitest, rust tests, pytest,
                                         # minilints — all green
# focused engine + points-at-stake tests:
just test-rust
just test-py
```

Capture: green output. The points-at-stake Rust tests
(`rslib/src/points_at_stake/mod.rs`) cover path-prefix matching, tag-over-subdeck
resolution, weakness aggregation, ranking, and the struggling boost; the Python
integration test (`pylib/tests/test_points_at_stake.py`) calls the new backend
message and checks order, aggregation, and the struggling boost. Diagnostic
scoring and mediasrv endpoint registration (`pointsAtStakeQueue`,
`getDiagnosticQuiz`, `scoreAndSeedDiagnostic`) are covered by their own tests.

## 8. Benchmark (reliability/speed)

```bash
just bench                               # synthetic 50,000-card deck
# options: just bench --cards 50000 --iters 50 --grade-iters 1000
```

Capture: the printed p50/p95/worst table for queue building (points-at-stake),
button press (grade ack), next card, and the dashboard per-topic mastery query,
with PASS/FAIL against the PRD targets (button < 50 ms p95, next card < 100 ms
p95, dashboard < 1 s p95). On the synthetic 50k deck the current build **meets
every target with wide margin** (button-press p95 ≈ 0.1 ms, next-card p95 ≈ 0.01
ms, dashboard p95 ≈ 45 ms).

---

### Artifacts summary

| Proof                          | Command                                  | Output                     | Status                             |
| ------------------------------ | ---------------------------------------- | -------------------------- | ---------------------------------- |
| Commit                         | `git rev-parse HEAD`                     | hash                       | —                                  |
| Clean build                    | `just check`                             | green log                  | green                              |
| Installer (.dmg)               | `./tools/build-installer`                | `out/installer/dist/*.dmg` | not yet built from this tree       |
| Desktop review + teach-on-miss | `just run`                               | screen recording           | recording pending                  |
| Diagnostic                     | `just run` (first launch)                | screen recording           | recording pending                  |
| Dashboard                      | `just run` → Tools → ReadyMCAT Dashboard | screenshot                 | recording pending                  |
| iOS review (default order)     | `ios/scripts/run-sim.sh`                 | screen recording (manual)  | engine verified; recording pending |
| Tests                          | `just check`                             | green log                  | green                              |
| Benchmark                      | `just bench`                             | p50/p95/worst table        | targets met (measured)             |
