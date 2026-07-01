# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the pre-loaded ReadyMCAT MCQ deck.

Covers the three things the MCQ rework hinges on:

* the **bank builder** — the three section banks merge into one validated,
  414-item canonical bank, and build into a tagged MCQ note type / deck;
* **MCQ grading** — the correct/incorrect -> Good/Again FSRS mapping and the
  reviewer payload derived from a note's fields;
* **per-question teach-on-miss** — each card's own sub-questions parse into a
  clean ladder, and the outcome logic (spaced vs. struggling) is correct;

plus the reconciliation guarantee that the ``#ReadyMCAT::AAMC::<cat>`` tags
resolve through ``taxonomy.json`` so the pre-loaded deck feeds the
points-at-stake queue / coverage map end to end.
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


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "readymcat_build_question_bank_test", _BUILDER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bank = _load_builder()


# --- bank builder -----------------------------------------------------------


def test_merge_source_banks_is_valid_and_complete():
    items = bank.merge_source_banks()
    assert len(items) == 414
    # ids are globally unique
    ids = [it["id"] for it in items]
    assert len(set(ids)) == len(ids)
    # every item is schema-valid (4 options, correct_index in 0..3)
    for item in items:
        assert bank.validate_item(item) == []
    # metadata document reflects the merge
    document = bank.build_bank_document(items)
    assert document["count"] == 414
    assert document["note_type"] == bank.MCQ_NOTETYPE_NAME
    assert len(document["aamc_categories"]) == 31
    assert document["subquestion_count"] == sum(
        len(it.get("subquestions") or []) for it in items
    )


def test_ensure_notetype_shape():
    col = getEmptyCol()
    notetype = bank.ensure_notetype(col)
    assert notetype["name"] == bank.MCQ_NOTETYPE_NAME
    field_names = [f["name"] for f in notetype["flds"]]
    assert field_names == list(bank.MCQ_FIELDS)
    # one template => one card per note
    assert len(notetype["tmpls"]) == 1
    # idempotent: calling again returns the same note type, not a duplicate
    again = bank.ensure_notetype(col)
    assert again["id"] == notetype["id"]
    assert len(col.models.by_name(bank.MCQ_NOTETYPE_NAME)["tmpls"]) == 1
    col.close()


def test_build_notes_tags_by_aamc_category():
    col = getEmptyCol()
    items = bank.merge_source_banks()
    # one representative item per category keeps the test fast while still
    # covering all 31 categories.
    by_cat: dict[str, dict] = {}
    for item in items:
        by_cat.setdefault(item["aamc_category"], item)
    subset = list(by_cat.values())

    stats = bank.build_notes(col, subset)
    assert stats.notes_created == len(subset)
    assert stats.cards_created == len(subset)  # exactly one card per MCQ
    assert sorted(stats.categories) == sorted(by_cat)

    # every note carries the coarse marker tag and exactly its AAMC tag
    note_ids = col.find_notes(f'"note:{bank.MCQ_NOTETYPE_NAME}"')
    assert len(note_ids) == len(subset)
    for nid in note_ids:
        note = col.get_note(nid)
        assert bank.MCQ_TAG in note.tags
        aamc_tags = [t for t in note.tags if t.startswith(bank.AAMC_TAG_PREFIX)]
        assert len(aamc_tags) == 1
    col.close()


def test_provision_collection_is_idempotent():
    col = getEmptyCol()
    items = bank.merge_source_banks()

    first = bank.provision_collection(col, bank_items=items)
    assert first.already_present is False
    assert first.notes_created == 414
    assert col.decks.by_name(bank.MCQ_DECK_NAME) is not None

    # provisioning again is a no-op: the deck exists, nothing is duplicated
    second = bank.provision_collection(col, bank_items=items)
    assert second.already_present is True
    assert len(col.find_notes(f'"note:{bank.MCQ_NOTETYPE_NAME}"')) == 414
    col.close()


# --- reconciliation: tags resolve to AAMC categories end to end -------------


def test_aamc_tags_resolve_through_taxonomy():
    """The whole point of tagging by category: the pre-loaded deck must feed the
    points-at-stake engine. Build the deck, hand the backend a taxonomy with the
    ReadyMCAT MCQ mappings, and confirm every category resolves with the right
    per-category card counts and full coverage."""
    col = getEmptyCol()
    items = bank.merge_source_banks()
    bank.build_notes(col, items)

    categories = sorted({it["aamc_category"] for it in items})
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

    expected = Counter(it["aamc_category"] for it in items)
    resolved = {t.category: t.total_cards for t in resp.topics if t.total_cards > 0}
    assert resolved == dict(expected)
    # coverage sees every category the bank fills
    assert resp.coverage.categories_covered == len(categories)
    assert sum(t.total_cards for t in resp.topics) == 414
    col.close()


# --- MCQ grading + reviewer payload -----------------------------------------


def test_mcq_grading_mapping():
    # correct on the first attempt -> Good; anything that needed the ladder
    # (correct only after, or still wrong) -> Again (relearning / spaced).
    assert bank.ease_for_mcq_outcome(bank.OUTCOME_CORRECT_FIRST) == bank.EASE_GOOD
    assert bank.ease_for_mcq_outcome(bank.OUTCOME_CORRECT_AFTER) == bank.EASE_AGAIN
    assert bank.ease_for_mcq_outcome(bank.OUTCOME_WRONG) == bank.EASE_AGAIN
    # only "missed again after the ladder" flags the concept as struggling
    assert bank.outcome_is_struggling(bank.OUTCOME_WRONG) is True
    assert bank.outcome_is_struggling(bank.OUTCOME_CORRECT_AFTER) is False
    assert bank.outcome_is_struggling(bank.OUTCOME_CORRECT_FIRST) is False


def test_mcq_payload_round_trips_from_a_built_note():
    col = getEmptyCol()
    items = bank.merge_source_banks()
    item = items[0]
    bank.build_notes(col, [item])
    note = col.get_note(col.find_notes(f'"note:{bank.MCQ_NOTETYPE_NAME}"')[0])

    payload = bank.mcq_payload_from_fields(dict(note.items()))
    assert payload["question"] == item["stem"]
    assert payload["options"] == item["options"]
    assert payload["correctIndex"] == item["correct_index"]
    assert len(payload["subquestions"]) == len(item["subquestions"])
    col.close()


# --- per-question teach-on-miss (ladder parsing) ----------------------------


def test_parse_subquestions_builds_a_clean_ladder():
    raw = json.dumps(
        [
            {
                "stem": "Guiding one?",
                "options": ["a", "b", "c", "d"],
                "correct_index": 2,
                "explanation": "because c",
            },
            # malformed rungs are dropped, never crash the reviewer
            {"stem": "no options"},
            {"stem": "bad index", "options": ["a", "b", "c", "d"], "correct_index": 9},
            {"options": ["a", "b", "c", "d"], "correct_index": 0},  # no stem
        ]
    )
    ladder = bank.parse_subquestions(raw)
    assert len(ladder) == 1
    assert ladder[0]["stem"] == "Guiding one?"
    assert ladder[0]["correct_index"] == 2
    assert ladder[0]["options"] == ["a", "b", "c", "d"]
    # empty / invalid input yields an empty ladder (flow just skips to re-show)
    assert bank.parse_subquestions("") == []
    assert bank.parse_subquestions("not json") == []
    assert bank.parse_subquestions(None) == []


def test_every_bank_item_yields_a_usable_ladder():
    """Per-question teach-on-miss uses each card's own sub-questions, so every
    bank item must parse into at least one guiding rung."""
    items = bank.merge_source_banks()
    for item in items:
        raw = json.dumps(item.get("subquestions") or [])
        ladder = bank.parse_subquestions(raw)
        assert len(ladder) >= 1, f"{item['id']} has no usable sub-questions"
        for rung in ladder:
            assert len(rung["options"]) == 4
            assert 0 <= rung["correct_index"] <= 3
