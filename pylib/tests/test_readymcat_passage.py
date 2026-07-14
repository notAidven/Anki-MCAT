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


# --- CARS: the skills-section passage bank ----------------------------------
#
# CARS is folded in as a fourth pre-loaded content type. It reuses the passage
# note type but (1) lives in its own ReadyMCAT::Passages::CARS sub-deck, (2) is
# tagged #ReadyMCAT::CARS with NO AAMC content-category tag, and (3) is
# provisioned by stable per-note guid so it can be topped up onto a profile that
# already has the AAMC passages, without duplicating cards.

CARS_PASSAGE_COUNT = 15
CARS_QUESTION_COUNT = 77


def test_merge_cars_passage_banks_is_valid_and_complete():
    cars = bank.merge_cars_passage_banks()
    assert len(cars) == CARS_PASSAGE_COUNT
    assert bank.passage_question_count(cars) == CARS_QUESTION_COUNT
    # passage ids and question ids are globally unique within CARS
    pids = [p["id"] for p in cars]
    assert len(set(pids)) == len(pids)
    qids = [q["id"] for p in cars for q in p["questions"]]
    assert len(set(qids)) == len(qids)
    for passage in cars:
        assert passage.get("section") == "CARS"
        assert bank.validate_passage(passage) == []
        for question in passage["questions"]:
            # CARS is a *skills* section: each question carries a skill and has
            # no numbered AAMC content category (the "no aamc_category" contract)
            assert str(question.get("skill", "")).strip()
            assert bank._passage_question_category(passage, question) == "CARS"


def test_parse_passage_subquestions_accepts_variable_option_counts():
    """AAMC passage ladders use four options; CARS ladders use two or three. The
    passage ladder parser must keep all of them, while the strict MCQ parser
    (four options only) still rejects the short CARS rungs."""
    cars_ladder = json.dumps(
        [
            {
                "stem": "Two-option rung?",
                "options": ["yes", "no"],
                "correct_index": 0,
                "explanation": "e",
            },
            {
                "stem": "Three-option rung?",
                "options": ["a", "b", "c"],
                "correct_index": 2,
                "explanation": "e",
            },
        ]
    )
    lenient = bank.parse_passage_subquestions(cars_ladder)
    assert len(lenient) == 2
    assert [len(r["options"]) for r in lenient] == [2, 3]
    assert [r["correct_index"] for r in lenient] == [0, 2]
    # the strict MCQ parser drops these (it requires exactly four options)
    assert bank.parse_subquestions(cars_ladder) == []
    # a rung whose answer index is out of range for its options is dropped
    bad = json.dumps(
        [{"stem": "x", "options": ["a", "b"], "correct_index": 3, "explanation": ""}]
    )
    assert bank.parse_passage_subquestions(bad) == []


def test_cars_note_guid_is_stable_and_unique():
    cars = bank.merge_cars_passage_banks()
    qids = [q["id"] for p in cars for q in p["questions"]]
    guids = [bank.cars_note_guid(qid) for qid in qids]
    # deterministic (same id -> same guid) and collision-free across the bank
    assert guids == [bank.cars_note_guid(qid) for qid in qids]
    assert len(set(guids)) == len(guids)


def test_build_cars_passage_notes_deck_and_tags():
    col = getEmptyCol()
    cars = bank.merge_cars_passage_banks()

    stats = bank.build_cars_passage_notes(col, cars)
    assert stats.notes_created == CARS_QUESTION_COUNT
    assert stats.cards_created == CARS_QUESTION_COUNT  # one card per question
    assert stats.deck_name == bank.CARS_PASSAGE_DECK_NAME
    # CARS has no AAMC category, so none are recorded
    assert stats.categories == []

    # the CARS sub-deck is a child of the shared Passages deck
    assert col.decks.by_name(bank.CARS_PASSAGE_DECK_NAME) is not None
    assert bank.CARS_PASSAGE_DECK_NAME == f"{bank.PASSAGE_DECK_NAME}::CARS"

    note_ids = col.find_notes(f'deck:"{bank.CARS_PASSAGE_DECK_NAME}"')
    assert len(note_ids) == CARS_QUESTION_COUNT
    for nid in note_ids:
        note = col.get_note(nid)
        fields = dict(note.items())
        # tagged as a CARS passage, but NEVER given an AAMC content-category tag
        assert bank.CARS_TAG in note.tags
        assert bank.PASSAGE_TAG in note.tags
        assert not any(t.startswith(bank.AAMC_TAG_PREFIX) for t in note.tags)
        # same passage note type + fields as the AAMC passages
        assert note.note_type()["name"] == bank.PASSAGE_NOTETYPE_NAME
        assert fields["Passage"]
        assert fields["Question"]
        # the CARS skill is surfaced in the Subtopic slot the reviewer renders
        assert fields["Subtopic"] in {
            "comprehension",
            "reasoning-within",
            "reasoning-beyond",
        }
    col.close()


def test_provision_cars_passages_is_idempotent():
    col = getEmptyCol()

    first = bank.provision_cars_passages(col)
    assert first.already_present is False
    assert first.notes_created == CARS_QUESTION_COUNT
    assert col.decks.by_name(bank.CARS_PASSAGE_DECK_NAME) is not None

    second = bank.provision_cars_passages(col)
    assert second.already_present is True
    assert (
        len(col.find_notes(f'deck:"{bank.CARS_PASSAGE_DECK_NAME}"'))
        == CARS_QUESTION_COUNT
    )
    col.close()


def test_provision_cars_adds_missing_to_already_provisioned_passage_deck():
    """The regression the CARS fold-in must avoid: a profile that already has the
    AAMC ReadyMCAT::Passages deck (provisioned before CARS existed) must still
    gain exactly the CARS cards on next launch — and never duplicate them."""
    col = getEmptyCol()
    # simulate the pre-CARS state: the AAMC Passages deck already exists...
    bank.provision_passages(col)
    assert col.decks.by_name(bank.PASSAGE_DECK_NAME) is not None
    # ...but no CARS is present yet
    assert bank.has_all_cars_notes(col) is False
    assert col.decks.by_name(bank.CARS_PASSAGE_DECK_NAME) is None
    before = col.card_count()

    added = bank.provision_cars_passages(col)
    assert added.already_present is False
    assert added.notes_created == CARS_QUESTION_COUNT  # exactly the CARS cards
    assert col.card_count() == before + CARS_QUESTION_COUNT
    assert bank.has_all_cars_notes(col) is True
    assert col.decks.by_name(bank.CARS_PASSAGE_DECK_NAME) is not None

    # relaunch: nothing added, nothing duplicated
    again = bank.provision_cars_passages(col)
    assert again.already_present is True
    assert col.card_count() == before + CARS_QUESTION_COUNT
    col.close()


def test_cars_payload_round_trips_from_a_built_note():
    """The passage reviewer renders CARS items purely from note fields (it never
    needs an AAMC category), and surfaces the CARS skill as the subtopic."""
    col = getEmptyCol()
    cars = bank.merge_cars_passage_banks()
    passage = cars[0]
    question = passage["questions"][0]
    bank.build_cars_passage_notes(col, [passage])

    notes = [
        col.get_note(nid)
        for nid in col.find_notes(f'deck:"{bank.CARS_PASSAGE_DECK_NAME}"')
    ]
    by_stem = {dict(n.items())["Question"]: n for n in notes}
    note = by_stem[question["stem"]]

    payload = bank.passage_payload_from_fields(dict(note.items()))
    assert payload["passage"] == passage["passage"]
    assert payload["passageId"] == passage["id"]
    assert payload["question"] == question["stem"]
    assert payload["options"] == question["options"]
    assert payload["correctIndex"] == question["correct_index"]
    # the CARS skill renders where an AAMC subtopic normally would
    assert payload["subtopic"] == question["skill"]
    # the guiding ladder round-trips; CARS rungs use 2-3 options (not the MCQ's
    # fixed four), so the passage payload keeps every rung rather than dropping it
    assert len(payload["subquestions"]) == len(question.get("subquestions") or [])
    assert payload["subquestions"]  # this question ships a ladder
    for rung in payload["subquestions"]:
        assert 2 <= len(rung["options"]) <= 4
        assert 0 <= rung["correct_index"] < len(rung["options"])
    col.close()
