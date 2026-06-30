# ReadyMCAT — Proof Checklist (Wednesday MVP)

This is the capture checklist for the ReadyMCAT demo/handin. Two items are
**manual screen recordings** (the clean‑machine install and the iOS Simulator
review) — the commands below produce the artifacts; you press record.

All commands run from the repository root (the `anki/` working tree) on the
`readymcat-integration` branch. Prerequisites: Rust via `rustup` on `PATH`
(`source "$HOME/.cargo/env"`), Xcode for iOS, and the git submodules initialised
(`git submodule update --init`).

---

## 0. Record the exact commit

```bash
git rev-parse HEAD                       # integration commit hash
git log --oneline -8                     # merge + seam + finishing-wave history
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

Capture: terminal showing `just check` finishing green, then the app window.

## 2. Build + install the macOS .dmg

Proves a real installable artifact (Anki's Briefcase installer, unsigned for the
MVP — no Apple credentials required).

```bash
./tools/build-installer                  # = RELEASE=2 ./ninja installer (unsigned)
ls -lh out/installer/dist/               # the .dmg (and .pkg) land here
open out/installer/dist/                 # reveal in Finder
```

**Manual recording (clean machine):** on a second/clean macOS user account,
double‑click the `.dmg`, drag **ReadyMCAT** to Applications, launch it, and show
it opening a deck and grading one card. Record the whole flow.

## 3. Desktop review + teach‑on‑miss (the spiky feature)

```bash
just run
```

1. Import the Aidan deck (`File → Import`, `Aidan_.apkg`) and place
   `taxonomy.json` + `subquestions.json` next to the collection (or in the repo
   root for `just run`).
2. Study the deck. On a card belonging to a curated concept, grade **Again**.
3. Record: the **sub‑question ladder** appears instead of the answer; self‑mark
   each rung; the main question re‑shows; on a second miss the full answer is
   revealed ("earned"), the resource link is surfaced, and the note is tagged
   `ReadyMCAT::struggling`.
4. Show `readymcat_teach_on_miss_log.jsonl` (next to the collection) recording
   the events.
5. Re‑build the queue and show the struggling concept resurfaced near the top
   (points‑at‑stake boost).

## 4. Honest‑memory dashboard

```bash
just run     # then: Tools → ReadyMCAT Dashboard
```

Capture: per‑topic mastery/weakness, the memory score shown **as a range**, the
coverage map, and — before 200 graded reviews / 50% coverage — the explicit
"not enough data yet" give‑up state.

## 5. iOS Simulator review (shared engine)

Proves the same Rust engine runs on the phone with the points‑at‑stake order.

```bash
cd ios
./scripts/build-rust.sh                  # cross-compile rslib -> rsios.xcframework
./scripts/run-sim.sh                     # build & boot the SwiftUI app in the Simulator
# or open ios/ReadyMCAT.xcodeproj in Xcode and Run on a Simulator target
```

**Manual recording (Simulator):** record a real review session — fetch a card,
reveal, grade — running on the shared engine in the iOS Simulator.

## 6. Tests (engine + integration)

```bash
just check                               # clippy, mypy, ruff, eslint, svelte,
                                         # typescript, vitest, rust tests, pytest,
                                         # minilints — all green
# focused engine + points-at-stake tests:
just test-rust
just test-py
```

Capture: green output. The points‑at‑stake Rust tests
(`rslib/src/points_at_stake/mod.rs`) cover path‑prefix matching, tag‑over‑subdeck
resolution, weakness aggregation, ranking, and the struggling boost; the Python
integration test (`pylib/tests/test_points_at_stake.py`) calls the new backend
message and checks order, aggregation, and the struggling boost.

## 7. Benchmark (reliability/speed)

```bash
just bench                               # synthetic 50,000-card deck
# options: just bench --cards 50000 --iters 50 --grade-iters 1000
```

Capture: the printed p50/p95/worst table for queue building (points‑at‑stake),
button press (grade ack), next card, and the dashboard per‑topic mastery query,
with PASS/FAIL against the PRD targets (button < 50 ms p95, next card < 100 ms
p95, dashboard < 1 s p95).

---

### Artifacts summary

| Proof | Command | Output |
| --- | --- | --- |
| Commit | `git rev-parse HEAD` | hash |
| Clean build | `just check` | green log |
| Installer | `./tools/build-installer` | `out/installer/dist/*.dmg` |
| Desktop review + teach‑on‑miss | `just run` | screen recording |
| Dashboard | `just run` → Tools → ReadyMCAT Dashboard | screenshot |
| iOS review | `ios/scripts/run-sim.sh` | screen recording (manual) |
| Tests | `just check` | green log |
| Benchmark | `just bench` | p50/p95/worst table |
