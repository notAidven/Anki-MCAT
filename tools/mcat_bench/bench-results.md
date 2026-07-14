# ReadyMCAT — Speed & limits benchmark (§10)

_Self-contained, re-runnable evidence for the rubric §10 targets. Every number below is measured by `tools/mcat_bench` on a synthetic 50,000-card deck built on the shared Rust engine._

- **Generated:** 2026-07-06T01:02:29Z
- **Host:** macos / aarch64 (12 logical CPUs)
- **Deck:** 50000 cards, 200 review cards in the built queue
- **One command:** `just bench`

## Latency (p50 / p95 / worst)

| Action | p50 | p95 | worst | Target (p95) | Verdict |
|---|--:|--:|--:|--:|:--|
| Queue build (points-at-stake) | 78.695 ms | 80.117 ms | 80.580 ms | — | — |
| Button press (grade ack) | 0.091 ms | 0.175 ms | 20.122 ms | < 50 ms | ✅ PASS |
| Next card after grading | 0.007 ms | 0.010 ms | 0.032 ms | < 100 ms | ✅ PASS |
| Dashboard load (per-topic mastery) | 54.618 ms | 55.472 ms | 55.659 ms | < 1000 ms | ✅ PASS |
| Dashboard refresh (scores recompute) | 53.820 ms | 54.533 ms | 55.606 ms | < 500 ms | ✅ PASS |
| Cold start (spawn → first queue ready) | 100 ms | 102 ms | 102 ms | < 2000 ms | ✅ PASS |

## Sync (Anki's own protocol)

_Anki's own sync protocol against an in-process anki-sync-server on loopback; EXCLUDES WAN latency (measures engine + protocol work only)._

| Sync operation | Value | Target | Verdict |
|---|--:|--:|:--|
| Full upload of 50k collection (16.1 MB) | 345 ms | < 5000 ms | ✅ PASS |
| Incremental normal_sync p95 (20 review deltas pushed) | 6.479 ms | < 5000 ms | ✅ PASS |

## Memory (50k-card collection)

- **Stated ceiling:** 512 MB
- **Peak RSS holding+operating 50k:** 216 MB — ✅ within limit
- **Peak RSS across full run** (incl. loopback sync + 2nd collection): 216 MB


## What's measured / caveats

- All desktop numbers are measured on the same on-disk 50k synthetic deck built by this binary.
- dashboard_load = per-topic mastery (aggregation + ranking); dashboard_refresh = the full memory+performance+readiness recompute (PointsAtStakeService).
- cold_start times a fresh child process from spawn to first study queue ready (points-at-stake rerank included).
- sync is measured over a loopback in-process server and therefore excludes real network latency.

_Machine-readable numbers: `tools/mcat_bench/bench-results.json`._
