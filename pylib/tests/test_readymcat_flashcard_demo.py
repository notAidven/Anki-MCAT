# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the authorless demo flashcards that drive the retrieve-before-reveal
teach-on-miss flow.

The demo seeder (``readymcat/tools/seed_demo_dashboard.py``) creates a handful of
plain ``Basic`` front/back cards with NO authored ladder, so the desktop
reviewer's "Stuck? work it out" path AI-generates a guiding ladder from the card
itself. These offline tests (no Qt, no network) assert the two invariants that
make that work:

* the demo flashcards are real, reviewable Basic cards, correctly tagged so the
  demo remains clearly SYNTHETIC and fully removable; and
* they are genuinely *authorless* — none carries a ``#...`` tag, and every
  authored concept in ``subquestions.json`` matches only ``#...`` tags, so no
  demo flashcard can ever match an authored ladder (the AI path is what fires).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from anki.consts import QUEUE_TYPE_NEW
from tests.shared import getEmptyCol

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEED_PATH = _REPO_ROOT / "readymcat" / "tools" / "seed_demo_dashboard.py"
_SUBQUESTIONS_PATH = _REPO_ROOT / "subquestions.json"


def _load_seeder():
    spec = importlib.util.spec_from_file_location(
        "readymcat_seed_demo_dashboard_flashcard_test", _SEED_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seeder = _load_seeder()


def _seed_flashcards_only(col):
    """Run just the flashcard portion of the seeder (fast, no dashboard data)."""
    stats = seeder.DemoStats()
    seeder._seed_flashcards(col, stats=stats, log=lambda *_a, **_k: None)
    return stats


# --- the flashcards are real, reviewable, correctly-tagged Basic cards -------


def test_seed_flashcards_creates_basic_front_back_cards():
    col = getEmptyCol()
    stats = _seed_flashcards_only(col)

    assert stats.flashcards_created == len(seeder.DEMO_FLASHCARDS)
    note_ids = col.find_notes(f"tag:{seeder.DEMO_FLASHCARD_TAG}")
    assert len(note_ids) == len(seeder.DEMO_FLASHCARDS)

    for nid in note_ids:
        note = col.get_note(nid)
        # Plain Basic front/back note type.
        assert note.note_type()["name"] == "Basic"
        assert len(note.fields) == 2
        front, back = note.fields[0], note.fields[1]
        assert front.startswith("[SYNTHETIC DEMO]")
        assert back.strip()
        # Tagged so the demo stays clearly synthetic and removable.
        assert note.has_tag(seeder.DEMO_TAG)
        assert note.has_tag(seeder.DEMO_FLASHCARD_TAG)
        # New cards (queue NEW) -> immediately reviewable in the demo.
        for cid in col.card_ids_of_note(nid):
            assert col.get_card(cid).queue == QUEUE_TYPE_NEW
    col.close()


def test_flashcards_live_in_their_own_demo_deck():
    col = getEmptyCol()
    _seed_flashcards_only(col)

    deck = col.decks.by_name(seeder.DEMO_FLASHCARD_DECK)
    assert deck is not None
    in_deck = col.find_notes(f'deck:"{seeder.DEMO_FLASHCARD_DECK}"')
    assert len(in_deck) == len(seeder.DEMO_FLASHCARDS)
    col.close()


def test_demo_flashcards_are_removable_with_the_rest_of_the_demo():
    col = getEmptyCol()
    _seed_flashcards_only(col)

    assert seeder.has_demo_data(col) is True
    removed = seeder.remove_demo_data(col)
    assert removed == len(seeder.DEMO_FLASHCARDS)
    assert col.find_notes(f"tag:{seeder.DEMO_TAG}") == []
    col.close()


# --- the flashcards are genuinely authorless ---------------------------------


def test_demo_flashcards_carry_no_authored_ladder_tag():
    """No demo flashcard tag starts with '#', so it cannot match an authored
    concept (whose match_tags are all '#...'). This is what forces the reviewer
    down the AI-generated retrieve-before-reveal path for these cards."""
    col = getEmptyCol()
    _seed_flashcards_only(col)
    for nid in col.find_notes(f"tag:{seeder.DEMO_FLASHCARD_TAG}"):
        for tag in col.get_note(nid).tags:
            assert not tag.startswith("#"), f"unexpected authored-style tag: {tag}"
    col.close()


def test_authored_concepts_only_match_hash_tags():
    """The authorless invariant above only holds if every authored ladder
    matches solely ``#...`` tags. Assert that here so a future authored concept
    that used a plain tag would fail loudly rather than silently capturing the
    demo flashcards."""
    data = json.loads(_SUBQUESTIONS_PATH.read_text(encoding="utf-8"))
    concepts = data.get("concepts", [])
    assert concepts, "expected authored concepts in subquestions.json"
    for concept in concepts:
        for prefix in concept.get("match_tags", []):
            assert prefix.startswith("#"), (
                f"concept {concept.get('id')} matches a non-# tag {prefix!r}; "
                "authorless demo flashcards could collide with it"
            )
