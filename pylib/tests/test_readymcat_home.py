# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the ReadyMCAT home/study-launcher hub's backend helpers.

Covers the two things the hub's honesty depends on:

* per-format due/total counts never leak a nested subdeck's cards into a
  sibling format's tile (``ReadyMCAT`` parents ``Free Response``,
  ``Passages`` parents ``CARS``); and
* the streak / accuracy / diagnostic-status numbers are read straight off
  the collection, with no fabricated evidence when there is none.

Also covers the launch-routing decision (diagnostic-first on a genuinely new
profile, home hub on every other launch, and never both at once — the
regression this hub introduces if it double-opens with the diagnostic).
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

from anki import diagnostic_pb2 as diag_pb
from tests.shared import getEmptyCol

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relpath: str):
    path = _REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


home = _load("readymcat_home_launcher_test", "readymcat/tools/home_launcher.py")
bank = _load(
    "readymcat_build_question_bank_test_for_home",
    "readymcat/tools/build_question_bank.py",
)


# --- fake deck tree for the pure find/stat helpers --------------------------


@dataclass
class FakeNode:
    deck_id: int
    total_in_deck: int = 0
    new_uncapped: int = 0
    review_uncapped: int = 0
    intraday_learning: int = 0
    interday_learning_uncapped: int = 0
    children: list["FakeNode"] = field(default_factory=list)


def test_find_deck_node_depth_first():
    tree = FakeNode(
        deck_id=1, children=[FakeNode(deck_id=2, children=[FakeNode(deck_id=3)])]
    )
    found = home.find_deck_node(tree, 3)
    assert found is not None
    assert found.deck_id == 3
    assert home.find_deck_node(tree, 999) is None


def test_deck_launch_stats_uses_uncapped_child_excluding_counters():
    node = FakeNode(
        deck_id=5,
        total_in_deck=40,
        new_uncapped=10,
        review_uncapped=3,
        intraday_learning=1,
        interday_learning_uncapped=2,
    )
    stats = home.deck_launch_stats(node, 5)
    assert stats.present is True
    assert stats.total == 40
    assert stats.due == 16
    assert stats.as_dict() == {"present": True, "deckId": 5, "due": 16, "total": 40}


def test_deck_launch_stats_absent_deck_is_honest_not_fabricated():
    stats = home.deck_launch_stats(None, None)
    assert stats.present is False
    assert stats.due == 0
    assert stats.total == 0


# --- streak / accuracy pure math --------------------------------------------


def test_streak_counts_consecutive_days_ending_today():
    assert home.compute_streak_days({100, 99, 98, 95}, today=100) == 3


def test_streak_survives_through_yesterday_if_today_not_reviewed_yet():
    assert home.compute_streak_days({99, 98, 97}, today=100) == 3


def test_streak_is_honestly_zero_after_a_gap():
    assert home.compute_streak_days({97, 96}, today=100) == 0


def test_streak_is_zero_with_no_evidence():
    assert home.compute_streak_days(set(), today=100) == 0


def test_accuracy_is_none_without_evidence_not_fabricated():
    assert home.compute_accuracy(0, 0) is None


def test_accuracy_is_fraction_of_non_again_reviews():
    assert home.compute_accuracy(3, 4) == 0.75


def test_summarize_progress_from_synthetic_revlog_rows():
    day_cutoff = 1_000_000  # arbitrary "end of today" unix seconds
    today = 50
    ms = home.MS_PER_DAY
    rows = [
        (day_cutoff * 1000 - 1, 3),  # today, pass
        (day_cutoff * 1000 - ms - 1, 1),  # yesterday, fail (Again)
        (day_cutoff * 1000 - 2 * ms - 1, 3),  # 2 days ago, pass
    ]
    progress = home.summarize_progress(rows, today=today, day_cutoff_secs=day_cutoff)
    assert progress["streakDays"] == 3
    assert progress["activeDaysThisWeek"] == 3
    assert progress["reviewsLast7d"] == 3
    assert progress["accuracy7d"] == 2 / 3


def test_summarize_progress_is_honest_with_no_reviews():
    progress = home.summarize_progress([], today=50, day_cutoff_secs=1_000_000)
    assert progress["streakDays"] == 0
    assert progress["activeDaysThisWeek"] == 0
    assert progress["reviewsLast7d"] == 0
    assert progress["accuracy7d"] is None


# --- summarize_home_status against a real collection ------------------------


def _add_card(col, deck_name: str) -> int:
    deck_id = col.decks.id(deck_name)
    note = col.new_note(col.models.by_name("Basic"))
    note.fields[0] = deck_name
    note.fields[1] = "x"
    col.add_note(note, deck_id)
    return note.cards()[0].id


def test_summarize_home_status_excludes_nested_subdecks_per_tile():
    col = getEmptyCol()
    deck_names = home.default_deck_names(bank)

    # two MCQ cards directly in the parent deck...
    _add_card(col, bank.MCQ_DECK_NAME)
    _add_card(col, bank.MCQ_DECK_NAME)
    # ...and one card in each nested child, which must NOT leak into "mcq".
    _add_card(col, bank.FR_DECK_NAME)
    _add_card(col, bank.PASSAGE_DECK_NAME)
    _add_card(col, bank.CARS_PASSAGE_DECK_NAME)

    status = home.summarize_home_status(col, deck_names)

    assert status["decks"]["mcq"]["total"] == 2
    assert status["decks"]["mcq"]["present"] is True
    assert status["decks"]["fr"]["total"] == 1
    # "Passages" must not count its CARS child.
    assert status["decks"]["passage"]["total"] == 1
    assert status["decks"]["cars"]["total"] == 1

    col.close()


def test_summarize_home_status_reports_absent_deck_honestly():
    col = getEmptyCol()
    deck_names = home.default_deck_names(bank)
    # nothing provisioned at all yet
    status = home.summarize_home_status(col, deck_names)
    for key in ("mcq", "fr", "passage", "cars"):
        assert status["decks"][key] == {
            "present": False,
            "deckId": None,
            "due": 0,
            "total": 0,
        }
    col.close()


def test_summarize_home_status_reflects_diagnostic_and_reviews():
    col = getEmptyCol()
    deck_names = home.default_deck_names(bank)
    cid = _add_card(col, bank.MCQ_DECK_NAME)

    before = home.summarize_home_status(col, deck_names)
    assert before["diagnostic"]["taken"] is False
    assert before["diagnostic"]["takenAt"] is None
    assert before["progress"]["cardsStudied"] == 0

    # log one real review for that card, timestamped "today"
    col.db.execute(
        "insert into revlog values (?,?,?,?,?,?,?,?,?)",
        col.sched.day_cutoff * 1000 - 1,
        cid,
        -1,
        3,
        1,
        1,
        2500,
        4000,
        0,
    )

    # take the diagnostic
    col._backend.score_and_seed_diagnostic(
        diag_pb.DiagnosticResponses(
            responses=[
                diag_pb.DiagnosticResponse(
                    item_id="DQ-1A-01",
                    category="1A",
                    chosen="A",
                    answered=True,
                    correct=True,
                    difficulty="easy",
                )
            ],
            mode="short",
        )
    )

    after = home.summarize_home_status(col, deck_names)
    assert after["diagnostic"]["taken"] is True
    assert after["diagnostic"]["takenAt"] is not None
    assert after["progress"]["cardsStudied"] == 1
    assert after["progress"]["streakDays"] == 1
    assert after["progress"]["accuracy7d"] == 1.0

    col.close()


# --- one-tap review launch search isolation ---------------------------------


def test_isolating_search_excludes_nested_children_for_mcq_and_passage():
    col = getEmptyCol()
    deck_names = home.default_deck_names(bank)

    mcq_1 = _add_card(col, bank.MCQ_DECK_NAME)
    mcq_2 = _add_card(col, bank.MCQ_DECK_NAME)
    _add_card(col, bank.FR_DECK_NAME)
    passage_1 = _add_card(col, bank.PASSAGE_DECK_NAME)
    _add_card(col, bank.CARS_PASSAGE_DECK_NAME)

    mcq_search = home.isolating_search_for(deck_names, "mcq")
    assert set(col.find_cards(mcq_search)) == {mcq_1, mcq_2}

    passage_search = home.isolating_search_for(deck_names, "passage")
    assert set(col.find_cards(passage_search)) == {passage_1}

    # leaf decks need no isolating query — a plain deck selection is enough.
    assert home.isolating_search_for(deck_names, "fr") is None
    assert home.isolating_search_for(deck_names, "cars") is None

    col.close()


def test_isolating_search_actually_builds_a_working_filtered_deck():
    """End-to-end proof that the search string isolates the right cards when
    fed through the real filtered-deck machinery ``start_deck_review`` uses,
    not just a plain ``find_cards`` count."""
    col = getEmptyCol()
    deck_names = home.default_deck_names(bank)

    mcq_1 = _add_card(col, bank.MCQ_DECK_NAME)
    mcq_2 = _add_card(col, bank.MCQ_DECK_NAME)
    _add_card(col, bank.FR_DECK_NAME)
    _add_card(col, bank.PASSAGE_DECK_NAME)
    _add_card(col, bank.CARS_PASSAGE_DECK_NAME)

    search = home.isolating_search_for(deck_names, "mcq")
    deck = col.sched.get_or_create_filtered_deck(deck_id=0)
    deck.name = "ReadyMCAT Launcher"
    del deck.config.search_terms[:]
    term = deck.config.search_terms.add()
    term.search = search
    term.limit = 9999
    term.order = 6  # DUE
    deck.config.reschedule = True
    result = col.sched.add_or_update_filtered_deck(deck)
    col.sched.rebuild_filtered_deck(result.id)

    cards_in_launcher = col.decks.cids(result.id)
    assert set(cards_in_launcher) == {mcq_1, mcq_2}

    col.close()


# --- launch routing ----------------------------------------------------------


def test_diagnostic_opens_only_for_a_genuinely_new_profile():
    assert home.should_open_diagnostic_on_launch(
        diagnostic_already_taken=False, quiz_available=True, skip_diagnostic=False
    )
    assert not home.should_open_home_on_launch(
        diagnostic_already_taken=False, quiz_available=True, skip_diagnostic=False
    )


def test_home_opens_once_diagnostic_already_taken():
    assert home.should_open_home_on_launch(
        diagnostic_already_taken=True, quiz_available=True, skip_diagnostic=False
    )
    assert not home.should_open_diagnostic_on_launch(
        diagnostic_already_taken=True, quiz_available=True, skip_diagnostic=False
    )


def test_home_opens_when_no_quiz_bank_is_available():
    assert home.should_open_home_on_launch(
        diagnostic_already_taken=False, quiz_available=False, skip_diagnostic=False
    )


def test_env_escape_hatch_skips_diagnostic_and_opens_home():
    assert home.should_open_home_on_launch(
        diagnostic_already_taken=False, quiz_available=True, skip_diagnostic=True
    )
    assert not home.should_open_diagnostic_on_launch(
        diagnostic_already_taken=False, quiz_available=True, skip_diagnostic=True
    )


def test_diagnostic_and_home_never_both_open():
    for taken in (True, False):
        for quiz in (True, False):
            for skip in (True, False):
                opens_diag = home.should_open_diagnostic_on_launch(taken, quiz, skip)
                opens_home = home.should_open_home_on_launch(taken, quiz, skip)
                assert opens_diag != opens_home
