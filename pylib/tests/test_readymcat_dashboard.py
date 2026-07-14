# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the ReadyMCAT honest-scores dashboard data contract.

Covers the three scores the dashboard headlines, computed by the Rust
``PointsAtStakeService`` and exposed through the ``points_at_stake_queue``
backend method:

* **Memory** — mean FSRS recall, as a range (pre-existing; asserted via the
  seeded end-to-end path here).
* **Performance** — first-attempt accuracy on the ReadyMCAT question notetypes,
  read from the review log, with its own give-up rule.
* **Readiness** — a HEURISTIC 472–528 projection gated on BOTH memory and
  performance.

The final test proves the demo seeder populates all three headlessly, which is
the "see all three populated" path the desktop *Load demo data* action uses.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

from tests.shared import getEmptyCol

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relpath: str) -> Any:
    path = _REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bank = _load(
    "readymcat_build_question_bank_dash_test", "readymcat/tools/build_question_bank.py"
)
seeder = _load(
    "readymcat_seed_demo_dashboard_test", "readymcat/tools/seed_demo_dashboard.py"
)

# A tiny two-category taxonomy so the tests do not depend on the shipped file.
_TAXONOMY = {
    "version": 1,
    "aamc_categories": {
        "1A": {"name": "Proteins", "weight": 3.53},
        "1B": {"name": "Gene expression", "weight": 3.53},
    },
    "mappings": [
        {"deck_tag_or_subdeck": "#ReadyMCAT::AAMC::1A", "category": "1A"},
        {"deck_tag_or_subdeck": "#ReadyMCAT::AAMC::1B", "category": "1B"},
    ],
}


def _write_taxonomy(tmp_path: Path) -> str:
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(_TAXONOMY), encoding="utf-8")
    return str(path)


def _add_mcq(col, category: str, hit: bool, rev_id: int) -> int:
    """Add one MCQ note tagged to ``category`` with a single first-attempt
    review (Good when ``hit`` else Again). Returns the card id."""
    notetype = bank.ensure_notetype(col)
    deck_id = col.decks.id(bank.MCQ_DECK_NAME)
    note = col.new_note(notetype)
    for i in range(len(note.fields)):
        note.fields[i] = f"q{rev_id}"
    note.add_tag(bank.aamc_tag_for(category))
    col.add_note(note, deck_id)
    cid = note.cards()[0].id
    ease = bank.EASE_GOOD if hit else bank.EASE_AGAIN
    col.db.execute(
        "insert into revlog values (?,?,?,?,?,?,?,?,?)",
        rev_id,
        cid,
        -1,
        ease,
        10,
        1,
        2500,
        5000,
        1,
    )
    return cid


def test_performance_reads_first_attempt_accuracy_and_gates_readiness(tmp_path):
    """Performance is first-attempt accuracy on the question notetypes and has
    its own give-up rule; readiness stays hidden until memory ALSO qualifies."""
    col = getEmptyCol()
    tax_path = _write_taxonomy(tmp_path)
    base = int(time.time() * 1000)

    # 35 first attempts on 1A MCQs: 25 hits, 10 misses (accuracy 25/35).
    for i in range(35):
        _add_mcq(col, "1A", hit=(i < 25), rev_id=base + i)

    resp = col._backend.points_at_stake_queue(
        taxonomy_path=tax_path, deck_id=0, limit=0
    )

    # Performance clears its 30-attempt give-up rule and reports the accuracy.
    assert resp.performance.attempts == 35
    assert resp.performance.hits == 25
    assert abs(resp.performance.mean - 25 / 35) < 1e-9
    assert resp.performance.meets_data_threshold
    assert (
        resp.performance.range_low < resp.performance.mean < resp.performance.range_high
    )

    topic_1a = next(t for t in resp.performance.topics if t.category == "1A")
    assert (topic_1a.attempts, topic_1a.hits) == (35, 25)

    # Memory has only 35 graded reviews (< 200) so it abstains...
    assert not resp.meets_data_threshold
    # ...and readiness, which needs BOTH inputs, abstains too — but is still
    # honestly flagged as a heuristic.
    assert not resp.readiness.meets_data_threshold
    assert resp.readiness.heuristic

    col.close()


def test_later_reviews_do_not_change_first_attempt_verdict(tmp_path):
    """Only a card's FIRST graded review counts toward performance."""
    col = getEmptyCol()
    tax_path = _write_taxonomy(tmp_path)
    base = int(time.time() * 1000)

    # A single card missed on the first attempt, then aced repeatedly later.
    cid = _add_mcq(col, "1A", hit=False, rev_id=base)
    for later in range(1, 4):
        col.db.execute(
            "insert into revlog values (?,?,?,?,?,?,?,?,?)",
            base + later * 1000,
            cid,
            -1,
            bank.EASE_GOOD,
            10,
            1,
            2500,
            5000,
            1,
        )

    resp = col._backend.points_at_stake_queue(
        taxonomy_path=tax_path, deck_id=0, limit=0
    )
    assert resp.performance.attempts == 1
    assert resp.performance.hits == 0  # the first attempt was a miss

    col.close()


def test_seeded_demo_populates_all_three_scores():
    """End-to-end: the demo seeder makes Memory, Performance AND Readiness all
    render populated (past every give-up threshold) — the headless equivalent of
    the desktop *Load demo data* action, so all three show real numbers."""
    col = getEmptyCol()
    stats = seeder.seed_demo_data(col, log=lambda *_a, **_k: None)

    assert stats.taxonomy_path, "seeder should have located taxonomy.json"
    assert stats.questions_created >= 30

    resp = col._backend.points_at_stake_queue(
        taxonomy_path=stats.taxonomy_path, deck_id=0, limit=0
    )

    # Memory populated.
    assert resp.meets_data_threshold
    assert resp.memory.range_low < resp.memory.range_high
    assert resp.memory.graded_reviews >= seeder_min_reviews()

    # Performance populated.
    assert resp.performance.meets_data_threshold
    assert resp.performance.attempts >= 30
    assert 0.0 < resp.performance.mean < 1.0
    assert resp.performance.range_low < resp.performance.range_high

    # Readiness populated, on the real scale, and honestly flagged heuristic.
    assert resp.readiness.meets_data_threshold
    assert resp.readiness.heuristic
    assert 472 <= resp.readiness.range_low <= resp.readiness.point
    assert resp.readiness.point <= resp.readiness.range_high <= 528

    # The seeder's own self-check agrees all three are populated.
    assert stats.meets_threshold
    assert stats.performance_meets
    assert stats.readiness_meets

    col.close()


def test_remove_demo_data_purges_synthetic_reviews_for_a_clean_slate():
    """Clearing demo data must delete the synthetic REVIEWS too, not just the
    notes. Anki keeps revlog history when cards are deleted, so leaving those
    orphaned rows would keep the dashboard past its give-up threshold while
    Memory has zero real graded cards — a misleading 0%. This is the safe
    "back to real-data-only" path a user runs on an existing profile."""
    col = getEmptyCol()
    stats = seeder.seed_demo_data(col, log=lambda *_a, **_k: None)
    tax = stats.taxonomy_path

    # Seeded: all three scores populated, well past every give-up threshold.
    seeded = col._backend.points_at_stake_queue(taxonomy_path=tax, deck_id=0, limit=0)
    assert seeded.meets_data_threshold
    assert seeded.memory.graded_reviews >= seeder_min_reviews()
    assert col.db.scalar("select count() from revlog") > 0

    removed = seeder.remove_demo_data(col)
    assert removed > 0

    # No demo notes AND no synthetic reviews survive (every review was synthetic,
    # created on a demo card, so the whole revlog is gone).
    assert col.find_notes(f"tag:{seeder.DEMO_TAG}") == []
    assert col.db.scalar("select count() from revlog") == 0
    # No orphaned rows pointing at deleted cards.
    assert (
        col.db.scalar(
            "select count() from revlog where cid not in (select id from cards)"
        )
        == 0
    )

    # The dashboard honestly returns to "not enough data yet".
    cleared = col._backend.points_at_stake_queue(taxonomy_path=tax, deck_id=0, limit=0)
    assert not cleared.meets_data_threshold
    assert cleared.memory.graded_reviews == 0
    assert cleared.performance.attempts == 0
    assert not cleared.readiness.meets_data_threshold

    col.close()


def seeder_min_reviews() -> int:
    # Memory give-up threshold mirrored on the Rust side (GIVE_UP_MIN_REVIEWS).
    return 200
