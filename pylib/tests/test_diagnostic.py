# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Integration tests for the ReadyMCAT introductory-diagnostic backend service.

Covers the RPC surface end to end (serve bank -> score+seed -> read -> clear),
the README's worked FC1 example through the real service, and — most importantly
— the HONESTY guardrail: the diagnostic prior seeds card *ordering* only and must
never move the dashboard's honest numbers (per-topic weakness/mastery, coverage,
the ranged memory score), which come purely from FSRS state.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from anki import diagnostic_pb2 as pb
from tests.shared import getEmptyCol

REAL_BANK = (
    Path(__file__).resolve().parents[2]
    / "readymcat"
    / "diagnostic"
    / "diagnostic_quiz.json"
)

# Two equally *plausible* topics but different exam weight, so that without a
# prior the heavier topic (3A) leads, and a diagnostic prior can flip the order.
TAXONOMY = {
    "version": 1,
    "aamc_categories": {
        "1B": {"name": "Cellular", "weight": 5.0},
        "3A": {"name": "Behavior", "weight": 6.0},
    },
    "mappings": [
        {"deck_tag_or_subdeck": "#Cellular", "category": "1B"},
        {"deck_tag_or_subdeck": "#Behavior", "category": "3A"},
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


def _resp(item_id: str, category: str, correct: bool) -> pb.DiagnosticResponse:
    return pb.DiagnosticResponse(
        item_id=item_id,
        category=category,
        chosen="A" if correct else "B",
        answered=True,
        correct=correct,
        difficulty="medium",
    )


def test_quiz_bank_loads_short_and_extended():
    """The bundled bank serves full breadth in short mode and every item in
    extended mode."""
    assert REAL_BANK.is_file(), f"missing bundled diagnostic bank at {REAL_BANK}"
    col = getEmptyCol()

    short = col._backend.get_diagnostic_quiz(quiz_path=str(REAL_BANK), mode="short")
    assert short.present
    # short = one item per AAMC category (full breadth, minimum length).
    assert len(short.items) == 31
    assert len({it.category for it in short.items}) == 31

    extended = col._backend.get_diagnostic_quiz(
        quiz_path=str(REAL_BANK), mode="extended"
    )
    assert extended.present
    assert len(extended.items) == 37

    # with no explicit path and no bank next to the (temp) collection, absence
    # is reported honestly (present == False) rather than fabricated. This is
    # exactly the signal the qt first-launch check relies on.
    missing = col._backend.get_diagnostic_quiz(quiz_path="", mode="short")
    assert missing.present is False

    col.close()


def test_worked_fc1_example_via_backend():
    """README Part 3 "Worked example (FC1)": simple beta-binomial, mu0=0.5,
    kappa=6. 1A 1/2, 1B 0/2, 1C 2/2, 1D 0/2."""
    col = getEmptyCol()
    req = pb.DiagnosticResponses(
        responses=[
            _resp("DQ-1A-01", "1A", True),
            _resp("DQ-1A-02", "1A", False),
            _resp("DQ-1B-01", "1B", False),
            _resp("DQ-1B-02", "1B", False),
            _resp("DQ-1C-01", "1C", True),
            _resp("DQ-1C-02", "1C", True),
            _resp("DQ-1D-01", "1D", False),
            _resp("DQ-1D-02", "1D", False),
        ],
        mode="short",
        mu0=0.5,
        kappa=6.0,
        disable_difficulty=True,
        disable_pooling=True,
    )
    prior = col._backend.score_and_seed_diagnostic(req)
    assert prior.present
    by_cat = {c.category: c for c in prior.categories}

    # exact values from the README table
    assert abs(by_cat["1A"].weakness - 0.50) < 1e-9
    assert by_cat["1A"].band == "partial"
    assert abs(by_cat["1B"].weakness - 0.625) < 1e-9
    assert by_cat["1B"].band == "gap"
    assert abs(by_cat["1C"].weakness - 0.375) < 1e-9
    assert by_cat["1C"].band == "partial"
    assert abs(by_cat["1D"].weakness - 0.625) < 1e-9
    assert by_cat["1D"].band == "gap"
    # README: "the prior is humble by construction" — even 0/2 never hits 1.0
    assert by_cat["1B"].weakness < 0.65

    col.close()


def test_diagnostic_prior_seeds_ordering_not_dashboard():
    """GUARDRAIL (honesty rule): seeding a diagnostic prior changes only the
    points-at-stake *ordering*. The dashboard's honest per-topic weakness,
    coverage and memory range are computed from FSRS state alone and must be
    byte-for-byte identical before and after the prior is written."""
    col = getEmptyCol()
    taxonomy_path = _write_taxonomy()

    card_1b = _add_review_card(col, "#Cellular")
    card_3a = _add_review_card(col, "#Behavior")
    # make both due review cards with NO FSRS memory state
    col.db.execute("update cards set queue = 2, type = 2, due = -1, ivl = 10")

    def snapshot():
        return col._backend.points_at_stake_queue(
            taxonomy_path=taxonomy_path, deck_id=0, limit=0
        )

    before = snapshot()
    # without a prior, the heavier topic (3A, weight 6) leads; both unstudied
    order_before = [c.card_id for c in before.ranked_cards]
    assert order_before == [card_3a, card_1b]
    assert all(not c.seeded_by_prior for c in before.ranked_cards)
    topics_before = {t.category: t for t in before.topics}

    # seed a prior that says 1B is weak (0/2) and 3A is strong (2/2)
    req = pb.DiagnosticResponses(
        responses=[
            _resp("DQ-1B-01", "1B", False),
            _resp("DQ-1B-02", "1B", False),
            _resp("DQ-3A-01", "3A", True),
            _resp("DQ-3A-02", "3A", True),
        ],
        mode="short",
        mu0=0.5,
        kappa=6.0,
        disable_difficulty=True,
        disable_pooling=True,
    )
    col._backend.score_and_seed_diagnostic(req)

    after = snapshot()

    # --- GUARDRAIL: the honest dashboard numbers are unchanged ---------------
    assert before.memory.mean == after.memory.mean
    assert before.memory.range_low == after.memory.range_low
    assert before.memory.range_high == after.memory.range_high
    assert before.memory.graded_cards == after.memory.graded_cards
    assert before.memory.graded_reviews == after.memory.graded_reviews
    assert before.coverage.categories_total == after.coverage.categories_total
    assert before.coverage.categories_covered == after.coverage.categories_covered
    assert before.coverage.weighted_fraction == after.coverage.weighted_fraction
    assert before.meets_data_threshold == after.meets_data_threshold
    topics_after = {t.category: t for t in after.topics}
    for cat, t_before in topics_before.items():
        t_after = topics_after[cat]
        assert t_before.student_weakness == t_after.student_weakness
        assert t_before.mean_retrievability == t_after.mean_retrievability
        assert t_before.graded_cards == t_after.graded_cards
        assert t_before.total_cards == t_after.total_cards
        assert t_before.topic_weight == t_after.topic_weight

    # --- but ORDERING is now seeded by the prior: the diagnostic-weak 1B leads
    order_after = [c.card_id for c in after.ranked_cards]
    assert order_after == [card_1b, card_3a]

    ranked = {c.card_id: c for c in after.ranked_cards}
    r_1b = ranked[card_1b]
    assert r_1b.seeded_by_prior is True
    # the card still reports the HONEST FSRS weakness (matches the dashboard)...
    assert r_1b.fsrs_weakness == topics_after["1B"].student_weakness
    # ...while the weakness used for ordering is the prior's (no reviews => w_fsrs=0)
    assert abs(r_1b.prior_weakness - 0.625) < 1e-9
    assert abs(r_1b.student_weakness - 0.625) < 1e-9
    assert abs(r_1b.points_at_stake - r_1b.topic_weight * r_1b.student_weakness) < 1e-9

    col.close()
    os.unlink(taxonomy_path)


def test_prior_persists_and_clears_via_backend():
    col = getEmptyCol()
    assert col._backend.get_diagnostic_prior().present is False

    req = pb.DiagnosticResponses(
        responses=[_resp("DQ-2A-01", "2A", True)],
        mode="short",
    )
    col._backend.score_and_seed_diagnostic(req)

    loaded = col._backend.get_diagnostic_prior()
    assert loaded.present is True
    assert loaded.mode == "short"
    assert any(c.category == "2A" for c in loaded.categories)

    col._backend.clear_diagnostic_prior()
    assert col._backend.get_diagnostic_prior().present is False
    # clearing again is a safe no-op
    col._backend.clear_diagnostic_prior()

    col.close()
