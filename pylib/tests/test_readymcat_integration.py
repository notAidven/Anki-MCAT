# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""End-to-end reconciliation for the pre-loaded ReadyMCAT decks.

A brand-new user gets MCQ + free-response + passage cards with zero import, and
every one of them — regardless of content type — is tagged
``#ReadyMCAT::AAMC::<cat>`` so it feeds the same points-at-stake queue, coverage
map and honest dashboard. These tests are the headless first-launch smoke test
and the guarantee that the tags resolve through ``taxonomy.json`` across all
three content types.
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
TOTAL_COUNT = MCQ_COUNT + FR_COUNT + PASSAGE_COUNT  # 998


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
    """The zero-import deck a new user gets contains all three content types."""
    col = getEmptyCol()
    stats = bank.provision_all(col)

    assert stats["mcq"].notes_created == MCQ_COUNT
    assert stats["free_response"].notes_created == FR_COUNT
    assert stats["passage"].notes_created == PASSAGE_COUNT

    # all three decks exist (the FR/passage sub-decks under the ReadyMCAT deck)
    assert col.decks.by_name(bank.MCQ_DECK_NAME) is not None
    assert col.decks.by_name(bank.FR_DECK_NAME) is not None
    assert col.decks.by_name(bank.PASSAGE_DECK_NAME) is not None

    # one card per item / question, and nothing else in the collection
    assert len(col.find_notes(f'"note:{bank.MCQ_NOTETYPE_NAME}"')) == MCQ_COUNT
    assert len(col.find_notes(f'"note:{bank.FR_NOTETYPE_NAME}"')) == FR_COUNT
    assert len(col.find_notes(f'"note:{bank.PASSAGE_NOTETYPE_NAME}"')) == PASSAGE_COUNT
    assert col.card_count() == TOTAL_COUNT
    col.close()


def test_provision_all_is_idempotent():
    col = getEmptyCol()
    bank.provision_all(col)
    second = bank.provision_all(col)
    assert all(stat.already_present for stat in second.values())
    assert col.card_count() == TOTAL_COUNT  # nothing duplicated on relaunch
    col.close()


def test_all_content_categories_is_the_union():
    categories = bank.all_content_categories()
    # the three banks cover the same 31 AAMC content categories
    assert len(categories) == 31
    assert categories == sorted(_expected_category_card_counts())


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
    assert sum(t.total_cards for t in resp.topics) == TOTAL_COUNT
    col.close()
