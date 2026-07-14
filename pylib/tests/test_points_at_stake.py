# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Integration test for the ReadyMCAT points-at-stake backend message."""

from __future__ import annotations

import json
import os
import tempfile

from tests.shared import getEmptyCol

TAXONOMY = {
    "version": 1,
    "aamc_categories": {
        # high-yield topic
        "1B": {"name": "Cellular", "weight": 10.0},
        # low-yield topic
        "3A": {"name": "Behavior", "weight": 1.0},
    },
    # '#'-prefixed keys are TAG mappings (matched against a card's tags); see the
    # resolver in rslib/src/points_at_stake/mod.rs and build_taxonomy.py.
    "mappings": [
        {"deck_tag_or_subdeck": "#HighYield", "category": "1B"},
        {"deck_tag_or_subdeck": "#LowYield", "category": "3A"},
    ],
}


def _write_taxonomy() -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(TAXONOMY, f)
    return path


def _add_review_card(col, tag: str) -> int:
    note = col.newNote()
    note["Front"] = tag
    note["Back"] = "x"
    note.tags = [tag]
    col.addNote(note)
    return note.cards()[0].id


def test_points_at_stake_orders_by_points_and_returns_aggregation():
    col = getEmptyCol()
    taxonomy_path = _write_taxonomy()

    high = _add_review_card(col, "#HighYield")
    low = _add_review_card(col, "#LowYield")
    # turn both into due review cards
    col.db.execute("update cards set queue = 2, type = 2, due = -1, ivl = 10")

    resp = col._backend.points_at_stake_queue(
        taxonomy_path=taxonomy_path, deck_id=0, limit=0
    )

    # both due cards are ranked, highest points at stake first
    order = [c.card_id for c in resp.ranked_cards]
    assert order == [high, low]

    # points_at_stake == topic_weight * student_weakness for each card
    for card in resp.ranked_cards:
        assert (
            abs(card.points_at_stake - card.topic_weight * card.student_weakness) < 1e-9
        )
    # the high-yield topic genuinely outranks the low-yield one
    assert resp.ranked_cards[0].points_at_stake > resp.ranked_cards[1].points_at_stake
    assert resp.ranked_cards[0].category == "1B"
    assert resp.ranked_cards[1].category == "3A"

    # per-topic aggregation is returned for the dashboard
    topics = {t.category: t for t in resp.topics}
    assert set(topics) == {"1B", "3A"}
    assert topics["1B"].total_cards == 1
    assert topics["3A"].total_cards == 1

    # honest memory + coverage are present, and the give-up rule withholds a
    # score (far fewer than 200 graded reviews)
    assert resp.coverage.categories_total == 2
    assert resp.coverage.categories_covered == 2
    assert resp.memory.range_low <= resp.memory.range_high
    assert resp.meets_data_threshold is False

    col.close()
    os.unlink(taxonomy_path)


def test_points_at_stake_handles_untagged_cards():
    col = getEmptyCol()
    taxonomy_path = _write_taxonomy()

    tagged = _add_review_card(col, "#HighYield")
    note = col.newNote()
    note["Front"] = "no topic"
    note["Back"] = "x"
    col.addNote(note)
    untagged = note.cards()[0].id
    col.db.execute("update cards set queue = 2, type = 2, due = -1, ivl = 10")

    resp = col._backend.points_at_stake_queue(
        taxonomy_path=taxonomy_path, deck_id=0, limit=0
    )
    order = [c.card_id for c in resp.ranked_cards]
    # the untagged card carries no points and sorts last
    assert order == [tagged, untagged]
    untagged_card = resp.ranked_cards[1]
    assert untagged_card.category == ""
    assert untagged_card.points_at_stake == 0.0

    col.close()
    os.unlink(taxonomy_path)


def test_points_at_stake_boosts_struggling_cards():
    """Seam: a card tagged ReadyMCAT::struggling (a teach-on-miss correction that
    was missed again) is boosted so the corrected concept resurfaces first."""
    col = getEmptyCol()
    taxonomy_path = _write_taxonomy()

    normal = _add_review_card(col, "#HighYield")
    # a second high-yield card, additionally flagged struggling
    note = col.newNote()
    note["Front"] = "struggling"
    note["Back"] = "x"
    note.tags = ["#HighYield", "ReadyMCAT::struggling"]
    col.addNote(note)
    struggling = note.cards()[0].id
    col.db.execute("update cards set queue = 2, type = 2, due = -1, ivl = 10")

    resp = col._backend.points_at_stake_queue(
        taxonomy_path=taxonomy_path, deck_id=0, limit=0
    )
    ranked = {c.card_id: c for c in resp.ranked_cards}
    assert ranked[struggling].struggling is True
    assert ranked[normal].struggling is False
    # same topic => identical weakness/weight, but the struggling card is boosted
    assert ranked[struggling].student_weakness == ranked[normal].student_weakness
    assert ranked[struggling].topic_weight == ranked[normal].topic_weight
    assert ranked[struggling].points_at_stake > ranked[normal].points_at_stake
    # and therefore resurfaces first
    assert resp.ranked_cards[0].card_id == struggling

    col.close()
    os.unlink(taxonomy_path)
