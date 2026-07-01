# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the pre-loaded ReadyMCAT free-response deck.

Covers the builder (the three free-response section banks merge into one
validated bank and build into a tagged type-in note type / sub-deck), the
idempotent provisioning, and — most importantly — the auto-grader that the
reviewer uses to mark a typed answer (normalized string / squashed-equation /
key-term matching, plus ±absolute and ±% numeric tolerance parsed from
``key_terms``).
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


def test_merge_fr_source_banks_is_valid_and_complete():
    items = bank.merge_fr_source_banks()
    assert len(items) == 410
    ids = [it["id"] for it in items]
    assert len(set(ids)) == len(ids)
    for item in items:
        assert bank.validate_fr_item(item) == []


def test_ensure_fr_notetype_shape():
    col = getEmptyCol()
    notetype = bank.ensure_fr_notetype(col)
    assert notetype["name"] == bank.FR_NOTETYPE_NAME
    field_names = [f["name"] for f in notetype["flds"]]
    assert field_names == list(bank.FR_FIELDS)
    assert len(notetype["tmpls"]) == 1  # one type-in card per note
    again = bank.ensure_fr_notetype(col)
    assert again["id"] == notetype["id"]  # idempotent
    col.close()


def test_build_fr_notes_tags_by_aamc_category():
    col = getEmptyCol()
    items = bank.merge_fr_source_banks()
    by_cat: dict[str, dict] = {}
    for item in items:
        by_cat.setdefault(item["aamc_category"], item)
    subset = list(by_cat.values())

    stats = bank.build_fr_notes(col, subset)
    assert stats.notes_created == len(subset)
    assert stats.cards_created == len(subset)  # exactly one card per item
    assert sorted(stats.categories) == sorted(by_cat)
    assert stats.deck_name == bank.FR_DECK_NAME

    note_ids = col.find_notes(f'"note:{bank.FR_NOTETYPE_NAME}"')
    assert len(note_ids) == len(subset)
    for nid in note_ids:
        note = col.get_note(nid)
        assert bank.FR_TAG in note.tags
        aamc_tags = [t for t in note.tags if t.startswith(bank.AAMC_TAG_PREFIX)]
        assert len(aamc_tags) == 1
    col.close()


def test_provision_free_response_is_idempotent():
    col = getEmptyCol()
    items = bank.merge_fr_source_banks()

    first = bank.provision_free_response(col, items=items)
    assert first.already_present is False
    assert first.notes_created == 410
    assert col.decks.by_name(bank.FR_DECK_NAME) is not None

    second = bank.provision_free_response(col, items=items)
    assert second.already_present is True
    assert len(col.find_notes(f'"note:{bank.FR_NOTETYPE_NAME}"')) == 410
    col.close()


# --- auto-grader ------------------------------------------------------------


def test_grader_accepts_exact_and_normalized_variants():
    accepted = ["Peptide bond", "amide bond", "peptide (amide) bond"]
    key_terms = ["peptide"]
    # exact, case/punctuation-insensitive, and squashed variants
    assert bank.grade_free_response("peptide bond", accepted, key_terms) is True
    assert bank.grade_free_response("  PEPTIDE  BOND ", accepted, key_terms) is True
    assert bank.grade_free_response("amide-bond", accepted, key_terms) is True
    # prose containing the key term still counts
    assert (
        bank.grade_free_response("it is a peptide linkage", accepted, key_terms)
        is True
    )
    # an unrelated answer does not
    assert bank.grade_free_response("glycosidic bond", accepted, key_terms) is False


def test_grader_numeric_tolerance_absolute():
    accepted = ["30 m/s", "30 m s^-1", "v = 30 m/s", "30"]
    key_terms = ["unit: m/s", "tolerance: ±0.5 m/s", "v = g t"]
    # accepted variant (units differ, numeric match saves it)
    assert bank.grade_free_response("30 m s^-1", accepted, key_terms) is True
    # within the ±0.5 tolerance
    assert bank.grade_free_response("30.4", accepted, key_terms) is True
    assert bank.grade_free_response("29.6 m/s", accepted, key_terms) is True
    # outside the tolerance (and the classic distance trap) is wrong
    assert bank.grade_free_response("30.9", accepted, key_terms) is False
    assert bank.grade_free_response("45 m/s", accepted, key_terms) is False


def test_grader_numeric_tolerance_percent():
    accepted = ["100 kPa", "100"]
    key_terms = ["tolerance: ±5%"]
    assert bank.grade_free_response("103 kPa", accepted, key_terms) is True
    assert bank.grade_free_response("95", accepted, key_terms) is True
    assert bank.grade_free_response("120", accepted, key_terms) is False


def test_grader_without_tolerance_requires_near_exact_number():
    accepted = ["0", "0 m/s", "zero"]
    # no tolerance directive -> numbers must match (near-)exactly
    assert bank.grade_free_response("0", accepted, []) is True
    assert bank.grade_free_response("zero", accepted, []) is True  # string match
    assert bank.grade_free_response("0.4", accepted, []) is False


def test_grader_rejects_empty_and_blank():
    assert bank.grade_free_response("", ["glycine"], ["glycine"]) is False
    assert bank.grade_free_response("   ", ["glycine"], ["glycine"]) is False
    assert bank.grade_free_response(None, ["glycine"], None) is False


def test_numeric_tolerance_parsing():
    assert bank.numeric_tolerance_from_key_terms(["tolerance: ±0.5 m/s"]) == (0.5, False)
    assert bank.numeric_tolerance_from_key_terms(["tolerance: ±5%"]) == (5.0, True)
    assert bank.numeric_tolerance_from_key_terms(["unit: m/s", "v = g t"]) is None
    assert bank.numeric_tolerance_from_key_terms([]) is None


# --- teach-on-miss ladder + payload -----------------------------------------


def test_parse_fr_subquestions_builds_a_clean_type_in_ladder():
    raw = json.dumps(
        [
            {
                "stem": "What initial speed does an object dropped from rest have?",
                "accepted_answers": ["0", "0 m/s", "zero"],
                "explanation": "Released from rest means v0 = 0.",
            },
            # malformed rungs are dropped, never crash the reviewer
            {"stem": "no accepted answers"},
            {"accepted_answers": ["x"]},  # no stem
            "not a dict",
        ]
    )
    ladder = bank.parse_fr_subquestions(raw)
    assert len(ladder) == 1
    assert ladder[0]["accepted_answers"] == ["0", "0 m/s", "zero"]
    assert bank.parse_fr_subquestions("") == []
    assert bank.parse_fr_subquestions("not json") == []
    assert bank.parse_fr_subquestions(None) == []


def test_every_fr_item_yields_a_usable_ladder():
    """Per-question teach-on-miss uses each item's own sub-questions, so every
    free-response item must parse into at least one guiding rung."""
    items = bank.merge_fr_source_banks()
    for item in items:
        raw = json.dumps(item.get("subquestions") or [])
        ladder = bank.parse_fr_subquestions(raw)
        assert len(ladder) >= 1, f"{item['id']} has no usable sub-questions"
        for rung in ladder:
            assert rung["accepted_answers"], f"{item['id']} rung has no answers"


def test_fr_payload_round_trips_from_a_built_note():
    col = getEmptyCol()
    items = bank.merge_fr_source_banks()
    item = items[0]
    bank.build_fr_notes(col, [item])
    note = col.get_note(col.find_notes(f'"note:{bank.FR_NOTETYPE_NAME}"')[0])

    payload = bank.fr_payload_from_fields(dict(note.items()))
    assert payload["prompt"] == item["prompt"]
    assert payload["acceptedAnswers"] == item["accepted_answers"]
    assert payload["keyTerms"] == item.get("key_terms", [])
    assert len(payload["subquestions"]) == len(item["subquestions"])
    # the payload can be graded end to end against its own accepted answers
    assert (
        bank.grade_free_response(
            item["accepted_answers"][0],
            payload["acceptedAnswers"],
            payload["keyTerms"],
        )
        is True
    )
    col.close()
