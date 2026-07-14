# ReadyMCAT — Points-at-Stake Engine Change

## What it does

A new review-card ordering for the Anki scheduler:

> points_at_stake = topic_weight × student_weakness

- **topic_weight** — the card's topic share of the real MCAT, from AAMC's
  published content distribution (`taxonomy.json`).
- **student_weakness** — `1 − mean(FSRS recall probability)` aggregated across
  every card in that topic. Before enough reviews accumulate, this is blended
  with the **first-launch diagnostic prior** (a precision-weighted `decayed_weakness`
  that fades as real reviews exceed a pseudocount) so ordering is useful from
  session one. The blend affects **ordering only** — the honest memory aggregation
  and the dashboard scores use the pure FSRS value, never the prior.

Due cards are ordered so the highest-yield, weakest topics come first. Note the
value is computed **per topic**, so every due card in the same topic shares one
score and ties break by most-overdue-then-card-id; a card tagged
`ReadyMCAT::struggling` gets a 2× ranking boost. If **no `taxonomy.json` is found**
next to the collection (or in the media folder), the order **silently falls back
to the gathered due-date order** rather than erroring — so selecting the order on a
collection with no taxonomy is a no-op, not a failure. The same
computation also produces the per-topic mastery/weakness aggregation, an honest
(ranged) overall memory score, and an outline-coverage map that the desktop
dashboard consumes (obeying the give-up rule: no score until ≥200 graded reviews
**and** ≥50% topic coverage).

## Why this belongs in Rust (not Python or the GUI)

1. **One engine, two apps.** The Rust core (`rslib`) is shared by the desktop
   app (via `pylib`/`rsbridge`) and the iOS companion (via the `rsios`
   C-ABI, which is **built and shipping** — `RsiosFFI.xcframework`). Implementing
   the order in Rust ships it to _both_ from a single source of truth; a
   Python-only version could never reach iOS. (Note: the engine change is compiled
   into the iOS binary, but the phone does not yet **activate** the order — its
   bundled collection reviews in default order until it selects
   `ReviewCardOrder::PointsAtStake` and ships a `taxonomy.json`; that is a
   content/config step, not an engine change.)
2. **It runs during queue building over the whole collection.** Ordering is part
   of `rslib/src/scheduler/queue/builder`. Anki gathers and orders due cards in
   Rust/SQL for speed on tens of thousands of cards; doing this in Python would
   mean round-tripping the full due set across the FFI on every queue build.
3. **The engine had no concept of a "topic", exam value, or cross-card
   aggregation.** Existing orders (e.g. _retrievability ascending_) are pure
   SQL `ORDER BY` clauses that reason about one card at a time. Points-at-stake
   needs (a) tag → AAMC-category mapping and (b) weakness aggregated across all
   cards in a topic — neither of which SQL can express. The natural home for
   that new capability is the core, next to FSRS memory state.
4. **It feeds the rest of the product.** Teach-on-miss relies on spaced
   re-retrieval: a corrected concept's topic weakness rises, so the queue
   resurfaces it. Memory/coverage for the dashboard fall out of the same pass.

## How it's implemented

- Gathering still happens in SQL (a stable `Day` base order). The
  topic-aware re-ranking is applied in Rust after gathering, because it needs
  the per-topic aggregation. Aggregation is one pass over the collection joining
  `cards`→`notes` for tags and reusing the existing `extract_fsrs_retrievability`
  SQL function; ranking is a second, bounded pass over due review cards.
- Exposed via a **new protobuf service** so Python (and later Swift) can request
  the ranked queue + aggregation without going through the deck config.

### Proto message (new file `proto/anki/points_at_stake.proto`)

```
service PointsAtStakeService {
  rpc PointsAtStakeQueue(PointsAtStakeRequest) returns (PointsAtStakeResponse);
}
PointsAtStakeRequest { string taxonomy_path; int64 deck_id; uint32 limit; }
PointsAtStakeResponse {
  repeated RankedCard ranked_cards;   // card_id, category, topic_weight,
                                      // student_weakness, points_at_stake,
                                      // struggling
  repeated TopicMastery topics;       // per-AAMC-category mastery + weakness
  MemoryReport memory;                // mean + 95% range, graded_reviews/cards
  CoverageReport coverage;            // categories + weighted coverage
  bool meets_data_threshold;          // give-up rule
}
```

## Files touched

### New, fork-specific (additive — trivial to keep across upstream merges)

| File                                   | Purpose                                                           |
| -------------------------------------- | ----------------------------------------------------------------- |
| `proto/anki/points_at_stake.proto`     | New service + messages                                            |
| `rslib/src/points_at_stake/mod.rs`     | Taxonomy parse, aggregation, ranking, tests                       |
| `rslib/src/points_at_stake/service.rs` | `PointsAtStakeService` backend impl                               |
| `pylib/tests/test_points_at_stake.py`  | Python integration test                                           |
| `ts/routes/readymcat-dashboard/*`      | Svelte dashboard page                                             |
| `qt/aqt/readymcat.py`                  | Dashboard window                                                  |
| `taxonomy.json`                        | Real shared deck-tag → AAMC mapping (31 categories, 118 mappings) |

### Upstream files modified (with future-merge-difficulty estimate)

| File                                       | Change                                                     | Merge difficulty                                                                                         |
| ------------------------------------------ | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `proto/anki/deck_config.proto`             | +1 enum value `REVIEW_CARD_ORDER_POINTS_AT_STAKE = 13`     | **Very low** — additive enum value                                                                       |
| `rslib/proto/src/lib.rs`                   | +1 `protobuf!(points_at_stake, …)` line                    | **Very low**                                                                                             |
| `rslib/proto/python.rs`                    | +1 import in generated-header list                         | **Very low**                                                                                             |
| `rslib/src/lib.rs`                         | +1 `pub mod points_at_stake;`                              | **Very low**                                                                                             |
| `rslib/src/storage/card/mod.rs`            | +1 match arm in `review_order_sql`                         | **Low** — isolated arm                                                                                   |
| `rslib/src/scheduler/fsrs/simulator.rs`    | add variant to the "not implemented" arm                   | **Low** — only conflicts if upstream edits that match                                                    |
| `rslib/src/scheduler/queue/builder/mod.rs` | guarded re-rank call + one helper method in `build_queues` | **Medium** — `build_queues` is a hot path; a small, guarded insertion but the most likely conflict point |
| `ts/routes/deck-options/choices.ts`        | +1 dropdown entry                                          | **Low**                                                                                                  |
| `qt/aqt/webview.py`                        | +1 `AnkiWebViewKind`, +1 API-access list entry             | **Low**                                                                                                  |
| `qt/aqt/mediasrv.py`                       | +1 entry in `is_sveltekit_page`                            | **Very low**                                                                                             |
| `qt/aqt/main.py`                           | Tools-menu action + handler                                | **Low**                                                                                                  |

**Overall:** low. Almost everything is additive new files; the only change inside
a core hot function is the small guarded re-rank insertion in `build_queues`.

## Tests, build & dashboard

- Rust unit tests (`rslib/src/points_at_stake/mod.rs`): `::`-path-prefix
  matching, tag-over-subdeck / longest-prefix category resolution, per-topic
  weakness aggregation, ranking correctness on a fixture, the struggling-tag
  priority boost, and the empty/untagged-topic edge case. Run with
  `just test-rust`.
- Python integration test (`pylib/tests/test_points_at_stake.py`): calls the new
  backend message and asserts the order + aggregation. Run with `just test-py`.
- Full gate: `just check`.
- Dashboard: **Tools → ReadyMCAT Dashboard** (desktop). It reads `taxonomy.json`
  next to the collection, or an explicit path. Undo and collection integrity are
  unaffected: the change only reorders the in-memory due queue and never mutates
  cards.

## Seam reconciliations (integration branch)

When the engine, content, and iOS branches were merged onto
`readymcat-integration`, two seams were reconciled:

1. **Taxonomy resolver ↔ the real `taxonomy.json`.** The engine branch shipped a
   stub `taxonomy.json` and a first-match-wins resolver with `*`/`?` globs. The
   content branch shipped the real `taxonomy.json` plus the reference resolver
   `readymcat/tools/build_taxonomy.py::resolve_category`. The merge keeps the
   **real** `taxonomy.json` and rewrites `Taxonomy::category_for` in
   `rslib/src/points_at_stake/mod.rs` to match the reference exactly:
   `#`-prefixed mappings are tags (matched against the card's tags), the rest are
   subdecks (matched against the deck name); **tags win over subdecks**, and the
   **longest `::`-path-prefix wins** (no globbing; case-sensitive). The Rust
   `is_path_prefix`/`longer` helpers are line-for-line equivalents of the Python
   `is_path_prefix` and the strict-`>` longest-prefix tie-break.

2. **`ReadyMCAT::struggling` ↔ points-at-stake.** The teach-on-miss reviewer
   tags a note `ReadyMCAT::struggling` when a corrected concept is missed again.
   `rank_due_cards` now detects that tag and multiplies the card's points at
   stake by `STRUGGLING_PRIORITY_BOOST` (2.0), so the corrected concept
   resurfaces ahead of its peers in both the live study queue (the
   `PointsAtStake` review order) and the dashboard's ranked list. The boost is a
   **ranking-only** concern: the honest memory/weakness aggregation is left
   untouched so the dashboard's scores stay honest. The proto `RankedCard` gains
   a `struggling` flag so clients can show why a card was prioritised.

## Integration notes for other workstreams

- **Taxonomy (deck workstream):** the real `taxonomy.json` matches the schema
  (`version`, `aamc_categories: {id: {name, weight}}`,
  `mappings: [{deck_tag_or_subdeck, category}]`). **Resolution rule** (see
  _Seam reconciliations_ below): a `deck_tag_or_subdeck` starting with `#` is a
  **tag** mapping (matched against the card's tags); any other value is a
  **subdeck** mapping (matched against the card's deck name). Tag mappings win
  over subdeck mappings, and within each kind the longest (most specific)
  `::`-path-prefix wins. Matching is case-sensitive and path-boundary aware (so
  `Biochem` matches `Biochem::Enzymes` but not `Biochemistry`). Place the file
  next to `collection.anki2`.
- **iOS workstream:** call `PointsAtStakeService.PointsAtStakeQueue` over the
  shared protobuf API for the ranked queue; set a deck's review order to
  `REVIEW_CARD_ORDER_POINTS_AT_STAKE` to have the live study queue use it.
