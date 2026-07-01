# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""End-to-end reconciliation for the pre-loaded ReadyMCAT decks.

A brand-new user gets MCQ + free-response + passage + CARS cards with zero
import. Every AAMC content item — regardless of content type — is tagged
``#ReadyMCAT::AAMC::<cat>`` so it feeds the same points-at-stake queue, coverage
map and honest dashboard. CARS is the skills section: it is present in the
collection but has NO AAMC category, so it must be cleanly IGNORED by the
points-at-stake aggregation rather than counted or errored on. These tests are
the headless first-launch smoke test and the guarantee that the tags resolve
through ``taxonomy.json`` across all AAMC content types while CARS is ignored.
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from tests.shared import getEmptyCol

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILDER_PATH = _REPO_ROOT / "readymcat" / "tools" / "build_question_bank.py"

# Bundled deck totals by content type (one card per item / question).
MCQ_COUNT = 414
FR_COUNT = 410
PASSAGE_COUNT = 174
# The AAMC-resolvable total: every one of these resolves to an AAMC category and
# feeds the points-at-stake queue / coverage map / dashboard.
TOTAL_COUNT = MCQ_COUNT + FR_COUNT + PASSAGE_COUNT  # 998
# CARS is the skills section: present in the collection but with NO AAMC
# category, so it is NOT part of TOTAL_COUNT (it must be ignored by the queue).
CARS_COUNT = 77
# Everything actually in the collection after a full first-launch provision.
COLLECTION_COUNT = TOTAL_COUNT + CARS_COUNT  # 1075


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "readymcat_build_question_bank_test", _BUILDER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bank = _load_builder()


def _expected_category_card_counts() -> Counter:
    expected: Counter = Counter()
    for item in bank.merge_source_banks():
        expected[str(item["aamc_category"])] += 1
    for item in bank.merge_fr_source_banks():
        expected[str(item["aamc_category"])] += 1
    for passage in bank.merge_passage_source_banks():
        for question in passage["questions"]:
            expected[bank._passage_question_category(passage, question)] += 1
    return expected


# --- headless first-launch smoke -------------------------------------------


def test_provision_all_first_launch_loads_every_content_type():
    """The zero-import deck a new user gets contains all four content types
    (MCQ + free-response + passage + CARS)."""
    col = getEmptyCol()
    stats = bank.provision_all(col)

    assert stats["mcq"].notes_created == MCQ_COUNT
    assert stats["free_response"].notes_created == FR_COUNT
    assert stats["passage"].notes_created == PASSAGE_COUNT
    assert stats["cars"].notes_created == CARS_COUNT

    # every deck exists (FR/passage sub-decks under ReadyMCAT; CARS under Passages)
    assert col.decks.by_name(bank.MCQ_DECK_NAME) is not None
    assert col.decks.by_name(bank.FR_DECK_NAME) is not None
    assert col.decks.by_name(bank.PASSAGE_DECK_NAME) is not None
    assert col.decks.by_name(bank.CARS_PASSAGE_DECK_NAME) is not None

    # one card per item / question across every content type
    assert len(col.find_notes(f'"note:{bank.MCQ_NOTETYPE_NAME}"')) == MCQ_COUNT
    assert len(col.find_notes(f'"note:{bank.FR_NOTETYPE_NAME}"')) == FR_COUNT
    # passage note type is shared by AAMC passages + CARS
    assert (
        len(col.find_notes(f'"note:{bank.PASSAGE_NOTETYPE_NAME}"'))
        == PASSAGE_COUNT + CARS_COUNT
    )
    assert (
        len(col.find_notes(f'deck:"{bank.CARS_PASSAGE_DECK_NAME}"')) == CARS_COUNT
    )
    assert col.card_count() == COLLECTION_COUNT
    col.close()


def test_provision_all_is_idempotent():
    col = getEmptyCol()
    bank.provision_all(col)
    second = bank.provision_all(col)
    assert all(stat.already_present for stat in second.values())
    assert col.card_count() == COLLECTION_COUNT  # nothing duplicated on relaunch
    col.close()


def test_provision_all_tops_up_cars_on_a_pre_cars_profile():
    """A profile provisioned before CARS existed (MCQ + FR + AAMC passages only)
    gains exactly the CARS cards on next launch via provision_all, and nothing
    else is duplicated."""
    col = getEmptyCol()
    bank.provision_collection(col)
    bank.provision_free_response(col)
    bank.provision_passages(col)
    pre_cars = col.card_count()
    assert pre_cars == TOTAL_COUNT
    assert bank.has_all_cars_notes(col) is False

    stats = bank.provision_all(col)
    # the AAMC content types were already present; only CARS was added
    assert stats["mcq"].already_present is True
    assert stats["free_response"].already_present is True
    assert stats["passage"].already_present is True
    assert stats["cars"].already_present is False
    assert stats["cars"].notes_created == CARS_COUNT
    assert col.card_count() == COLLECTION_COUNT

    # and a further relaunch duplicates nothing
    again = bank.provision_all(col)
    assert all(stat.already_present for stat in again.values())
    assert col.card_count() == COLLECTION_COUNT
    col.close()


def test_all_content_categories_is_the_union():
    categories = bank.all_content_categories()
    # the three AAMC banks cover the same 31 AAMC content categories
    assert len(categories) == 31
    assert categories == sorted(_expected_category_card_counts())
    # CARS is a skills section with no content category, so it is NOT included —
    # this is what keeps a bogus "CARS" taxonomy mapping from being created.
    assert "CARS" not in categories


# --- reconciliation: every content type resolves through taxonomy -----------


def test_all_content_resolves_through_taxonomy_end_to_end():
    col = getEmptyCol()
    bank.provision_all(col)

    categories = bank.all_content_categories()
    taxonomy = {
        "version": 1,
        "aamc_categories": {c: {"name": c, "weight": 1.0} for c in categories},
        "mappings": bank.taxonomy_mappings_for_categories(categories),
    }
    fd, taxonomy_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as handle:
        json.dump(taxonomy, handle)

    try:
        resp = col._backend.points_at_stake_queue(
            taxonomy_path=taxonomy_path, deck_id=0, limit=0
        )
    finally:
        os.unlink(taxonomy_path)

    expected = _expected_category_card_counts()
    resolved = {t.category: t.total_cards for t in resp.topics if t.total_cards > 0}
    # per-category totals reflect MCQ + free-response + passage together
    assert resolved == dict(expected)
    assert resp.coverage.categories_covered == len(categories)
    # The queue aggregates ONLY the AAMC-resolvable cards (TOTAL_COUNT), even
    # though the collection also holds CARS_COUNT CARS cards. CARS carries no
    # AAMC category (its #ReadyMCAT::CARS tag has no mapping) so it resolves to
    # no topic and is ignored — never counted, never an error.
    assert sum(t.total_cards for t in resp.topics) == TOTAL_COUNT
    assert col.card_count() == COLLECTION_COUNT
    assert "CARS" not in {t.category for t in resp.topics}
    col.close()


def test_cars_is_ignored_by_points_at_stake():
    """Even a CARS-only collection produces an empty points-at-stake aggregation:
    a card with no AAMC category (and no taxonomy mapping) is dropped, never
    counted or errored on. This is the dashboard/queue "gracefully ignore CARS"
    guarantee in isolation."""
    col = getEmptyCol()
    cars_stats = bank.provision_cars_passages(col)
    assert cars_stats.notes_created == CARS_COUNT
    assert col.card_count() == CARS_COUNT

    categories = bank.all_content_categories()
    taxonomy = {
        "version": 1,
        "aamc_categories": {c: {"name": c, "weight": 1.0} for c in categories},
        "mappings": bank.taxonomy_mappings_for_categories(categories),
    }
    fd, taxonomy_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as handle:
        json.dump(taxonomy, handle)

    try:
        resp = col._backend.points_at_stake_queue(
            taxonomy_path=taxonomy_path, deck_id=0, limit=0
        )
    finally:
        os.unlink(taxonomy_path)

    # no CARS card is attributed to any topic
    assert sum(t.total_cards for t in resp.topics) == 0
    assert resp.coverage.categories_covered == 0
    col.close()
