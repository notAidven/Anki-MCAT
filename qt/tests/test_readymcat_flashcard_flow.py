# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Wiring tests for the retrieve-BEFORE-reveal teach-on-miss flow for basic
front/back flashcards (``aqt.reviewer.Reviewer``).

ReadyMCAT's MCQ/free-response/passage reviewers are already retrieve-first. For
plain Basic cards, teach-on-miss used to fire on the "Again" grade — AFTER
"Show Answer" had already revealed the back, defeating retrieval. The fix moves
the intercept to the QUESTION side: an opt-in "Stuck? work it out" action runs
the guiding ladder while the back is still hidden.

These tests exercise the decision/wiring logic with a faked ``mw`` (no live Qt
event loop or collection needed, mirroring test_readymcat_single_window.py) via
``Reviewer.__new__`` so no widgets are constructed:

* "Again" no longer launches teach-on-miss (the buggy post-reveal path is gone);
* the question-side "Stuck? work it out" action launches the ladder with
  ``trigger="stuck"`` and falls back to a normal reveal when no ladder exists;
* eligibility is limited to non-interactive cards that actually have a ladder
  path (authored concept OR runtime generation enabled); and
* the "Stuck?" button is only rendered for eligible cards and is routed to the
  handler.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import anki.lang
import aqt.readymcat as readymcat
import aqt.readymcat_ladder_gen as ladder_gen
from aqt.reviewer import Reviewer


@pytest.fixture(autouse=True)
def _init_i18n() -> None:
    # _showAnswerButton renders translated labels (Show Answer / shortcut key).
    anki.lang.set_lang("en")


def _reviewer(state: str = "question") -> Reviewer:
    """A Reviewer with just the attributes the methods under test need — no
    __init__ (so no BottomBar / web views / hooks are created)."""
    r = Reviewer.__new__(Reviewer)
    r.mw = MagicMock()
    r.mw.state = "review"
    r.mw.col.path = "/tmp/collection.anki2"
    r.card = MagicMock()
    r.state = state
    r._tom = None
    r.web = MagicMock()
    r.bottom = MagicMock()
    return r


def _note(tags: list[str]) -> MagicMock:
    note = MagicMock()
    note.tags = tags
    return note


# --- "Again" no longer launches teach-on-miss (bug fix) ---------------------


def test_again_does_not_launch_teach_on_miss_after_reveal():
    r = _reviewer(state="answer")
    r._do_answer_card = MagicMock()
    r._maybe_start_teach_on_miss = MagicMock()

    r._answerCard(1)

    # The card is simply rescheduled; the ladder is NOT started here (it is
    # offered before reveal, on the question side, instead).
    r._do_answer_card.assert_called_once_with(1)
    r._maybe_start_teach_on_miss.assert_not_called()


# --- question-side "Stuck? work it out" -------------------------------------


def test_stuck_launches_teach_on_miss_before_reveal():
    r = _reviewer(state="question")
    r._maybe_start_teach_on_miss = MagicMock(return_value=True)
    r._showAnswer = MagicMock()

    r._on_retrieve_first()

    r._maybe_start_teach_on_miss.assert_called_once_with(trigger="stuck")
    # The back must NOT be revealed when a ladder is running.
    r._showAnswer.assert_not_called()


def test_stuck_falls_back_to_reveal_when_no_ladder():
    r = _reviewer(state="question")
    r._maybe_start_teach_on_miss = MagicMock(return_value=False)
    r._showAnswer = MagicMock()

    r._on_retrieve_first()

    # No ladder could be produced: behave like the normal "Show Answer" button.
    r._showAnswer.assert_called_once()


def test_stuck_is_ignored_outside_the_question_state():
    r = _reviewer(state="answer")
    r._maybe_start_teach_on_miss = MagicMock()
    r._showAnswer = MagicMock()

    r._on_retrieve_first()

    r._maybe_start_teach_on_miss.assert_not_called()
    r._showAnswer.assert_not_called()


def test_stuck_is_ignored_while_a_ladder_is_already_running():
    r = _reviewer(state="question")
    r._tom = {"pending": True}
    r._maybe_start_teach_on_miss = MagicMock()

    r._on_retrieve_first()

    r._maybe_start_teach_on_miss.assert_not_called()


# --- eligibility ------------------------------------------------------------


def test_not_available_for_interactive_notetypes(monkeypatch):
    r = _reviewer()
    r.card.note.return_value = _note(["#ReadyMCAT::AAMC::1D"])
    monkeypatch.setattr(readymcat, "is_mcq_note", lambda n: True)
    monkeypatch.setattr(readymcat, "is_fr_note", lambda n: False)
    monkeypatch.setattr(readymcat, "is_passage_note", lambda n: False)
    assert r._retrieve_first_available() is False


def test_available_when_an_authored_concept_matches(monkeypatch):
    r = _reviewer()
    r.card.note.return_value = _note(["#Biochemistry::Enzymes::Regulation::Inhibition"])
    monkeypatch.setattr(readymcat, "is_mcq_note", lambda n: False)
    monkeypatch.setattr(readymcat, "is_fr_note", lambda n: False)
    monkeypatch.setattr(readymcat, "is_passage_note", lambda n: False)
    monkeypatch.setattr(readymcat, "load_subquestions", lambda path: object())
    monkeypatch.setattr(readymcat, "match_concept", lambda tags, data: object())
    # Generation disabled: availability must come purely from the authored match.
    monkeypatch.setattr(ladder_gen, "is_enabled", lambda: False)
    assert r._retrieve_first_available() is True


def test_available_when_generation_enabled_for_authorless_card(monkeypatch):
    r = _reviewer()
    r.card.note.return_value = _note(
        ["ReadyMCAT_SYNTHETIC_DEMO", "ReadyMCAT_SYNTHETIC_DEMO::flashcards"]
    )
    monkeypatch.setattr(readymcat, "is_mcq_note", lambda n: False)
    monkeypatch.setattr(readymcat, "is_fr_note", lambda n: False)
    monkeypatch.setattr(readymcat, "is_passage_note", lambda n: False)
    monkeypatch.setattr(readymcat, "load_subquestions", lambda path: None)
    monkeypatch.setattr(readymcat, "match_concept", lambda tags, data: None)
    monkeypatch.setattr(ladder_gen, "is_enabled", lambda: True)
    assert r._retrieve_first_available() is True


def test_not_available_without_authored_ladder_or_generation(monkeypatch):
    r = _reviewer()
    r.card.note.return_value = _note(["some::imported::tag"])
    monkeypatch.setattr(readymcat, "is_mcq_note", lambda n: False)
    monkeypatch.setattr(readymcat, "is_fr_note", lambda n: False)
    monkeypatch.setattr(readymcat, "is_passage_note", lambda n: False)
    monkeypatch.setattr(readymcat, "load_subquestions", lambda path: None)
    monkeypatch.setattr(readymcat, "match_concept", lambda tags, data: None)
    monkeypatch.setattr(ladder_gen, "is_enabled", lambda: False)
    assert r._retrieve_first_available() is False


# --- the button + its routing -----------------------------------------------


def test_show_answer_button_offers_stuck_when_eligible():
    r = _reviewer(state="question")
    r._remaining = lambda: ""
    r._retrieve_first_available = lambda: True
    r.card.should_show_timer.return_value = False

    r._showAnswerButton()

    (html, _max), _ = _bottom_eval_args(r)
    assert "rmcatStuck" in html
    assert "Stuck? work it out" in html


def test_show_answer_button_omits_stuck_when_not_eligible():
    r = _reviewer(state="question")
    r._remaining = lambda: ""
    r._retrieve_first_available = lambda: False
    r.card.should_show_timer.return_value = False

    r._showAnswerButton()

    (html, _max), _ = _bottom_eval_args(r)
    assert "rmcatStuck" not in html


def test_link_handler_routes_stuck_to_handler():
    r = _reviewer(state="question")
    r._on_retrieve_first = MagicMock()
    r._linkHandler("rmcatStuck")
    r._on_retrieve_first.assert_called_once()


def _bottom_eval_args(r: Reviewer):
    """Parse the ``showQuestion(<json middle>, <maxTime>)`` JS the reviewer sent
    to the bottom bar into ((middle_html, max_time), {})."""
    import json
    import re

    call = r.bottom.web.eval.call_args
    js = call.args[0]
    match = re.match(r"showQuestion\((.*),(\d+)\);", js, re.DOTALL)
    assert match, f"unexpected bottom-bar JS: {js!r}"
    return (json.loads(match.group(1)), int(match.group(2))), {}
