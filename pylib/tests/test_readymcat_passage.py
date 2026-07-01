# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the pre-loaded ReadyMCAT passage deck.

Covers the builder (the three passage section banks merge into one validated
bank and build into a tagged note type / sub-deck with one MCQ card per
question, grouped by passage), the idempotent provisioning, and the passage
reviewer payload (passage + question + options + grouping id + guiding ladder).
"""

from __future__ import annotations

import importlib.util
import json
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


def test_merge_passage_source_banks_is_valid_and_complete():
    passages = bank.merge_passage_source_banks()
    assert len(passages) == 36
    assert bank.passage_question_count(passages) == 174
    # passage ids and question ids are globally unique
    pids = [p["id"] for p in passages]
    assert len(set(pids)) == len(pids)
    qids = [q["id"] for p in passages for q in p["questions"]]
    assert len(set(qids)) == len(qids)
    for passage in passages:
        assert bank.validate_passage(passage) == []


def test_ensure_passage_notetype_shape():
    col = getEmptyCol()
    notetype = bank.ensure_passage_notetype(col)
    assert notetype["name"] == bank.PASSAGE_NOTETYPE_NAME
    field_names = [f["name"] for f in notetype["flds"]]
    assert field_names == list(bank.PASSAGE_FIELDS)
    assert len(notetype["tmpls"]) == 1  # one card per question
    again = bank.ensure_passage_notetype(col)
    assert again["id"] == notetype["id"]  # idempotent
    col.close()


def test_build_passage_notes_tags_by_category_and_groups_by_passage():
    col = getEmptyCol()
    passages = bank.merge_passage_source_banks()
    # a representative slice: a few whole passages keeps the test fast while
    # still exercising grouping + tagging.
    subset = passages[:4]
    expected_cards = bank.passage_question_count(subset)

    stats = bank.build_passage_notes(col, subset)
    assert stats.notes_created == expected_cards
    assert stats.cards_created == expected_cards  # one card per question
    assert stats.deck_name == bank.PASSAGE_DECK_NAME

    note_ids = col.find_notes(f'"note:{bank.PASSAGE_NOTETYPE_NAME}"')
    assert len(note_ids) == expected_cards
    passage_ids_seen: set[str] = set()
    for nid in note_ids:
        note = col.get_note(nid)
        fields = dict(note.items())
        assert bank.PASSAGE_TAG in note.tags
        aamc_tags = [t for t in note.tags if t.startswith(bank.AAMC_TAG_PREFIX)]
        assert len(aamc_tags) == 1  # tagged by the QUESTION's category
        assert fields["Passage"]  # the shared passage travels with each card
        passage_ids_seen.add(fields["PassageId"])
    # every card carries a grouping id, one per source passage
    assert passage_ids_seen == {p["id"] for p in subset}
    col.close()


def test_provision_passages_is_idempotent():
    col = getEmptyCol()
    passages = bank.merge_passage_source_banks()

    first = bank.provision_passages(col, passages=passages)
    assert first.already_present is False
    assert first.notes_created == 174
    assert col.decks.by_name(bank.PASSAGE_DECK_NAME) is not None

    second = bank.provision_passages(col, passages=passages)
    assert second.already_present is True
    assert len(col.find_notes(f'"note:{bank.PASSAGE_NOTETYPE_NAME}"')) == 174
    col.close()


# --- reviewer payload -------------------------------------------------------


def test_passage_payload_round_trips_from_a_built_note():
    col = getEmptyCol()
    passages = bank.merge_passage_source_banks()
    passage = passages[0]
    question = passage["questions"][0]
    bank.build_passage_notes(col, [passage])
    note = col.get_note(col.find_notes(f'"note:{bank.PASSAGE_NOTETYPE_NAME}"')[0])

    payload = bank.passage_payload_from_fields(dict(note.items()))
    assert payload["passage"] == passage["passage"]
    assert payload["passageId"] == passage["id"]
    assert payload["question"] == question["stem"]
    assert payload["options"] == question["options"]
    assert payload["correctIndex"] == question["correct_index"]
    # the guiding ladder reuses the MCQ sub-question shape (options + index)
    assert len(payload["subquestions"]) == len(question.get("subquestions") or [])
    for rung in payload["subquestions"]:
        assert len(rung["options"]) == 4
        assert 0 <= rung["correct_index"] <= 3
    col.close()


def test_passage_questions_without_a_ladder_are_still_wellformed():
    """Not every passage question ships guiding sub-questions; those must still
    build a valid card (the reviewer simply skips straight to the re-ask)."""
    passages = bank.merge_passage_source_banks()
    for passage in passages:
        for question in passage["questions"]:
            raw = json.dumps(question.get("subquestions") or [])
            ladder = bank.parse_subquestions(raw)
            # a ladder is optional, but any rung present must be well-formed
            for rung in ladder:
                assert len(rung["options"]) == 4
                assert 0 <= rung["correct_index"] <= 3
