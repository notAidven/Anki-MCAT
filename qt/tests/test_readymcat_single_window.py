# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the ReadyMCAT single-window tab bar (``aqt.main`` / ``aqt.toolbar``).

ReadyMCAT's four surfaces — Home · Study · Decks · Dashboard — live in ONE
window with a persistent top tab bar, instead of the Home hub / Dashboard
popping up as separate ``QDialog`` windows. This module guards that contract at
the wiring level (no live Qt event loop or collection needed):

* the tab bar exposes all four tabs, each wired to its surface (Home/Dashboard
  navigate to their in-window states, Decks to the deck browser, Study straight
  into the reviewer in a single load);
* the ``show_readymcat_*`` entry points navigate the single window rather than
  opening a dialog;
* the main window swaps the shared ``mw.web`` in/out of its central stack and
  hides the bottom bar for the ReadyMCAT tabs; and
* the active tab always tracks the main-window state.

The actual in-window rendering of each tab (and that Study serves a question) is
covered end-to-end by ``ts/tests/e2e/readymcat_tabs.test.ts`` via the dev-only
``readymcatTabProbe`` mediasrv endpoint.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import anki.lang
import aqt.main
import aqt.readymcat
import aqt.readymcat_home
from aqt.main import READYMCAT_TAB_STATES
from aqt.toolbar import Toolbar


@pytest.fixture(autouse=True)
def _init_i18n() -> None:
    # The tab bar labels one tab via ``tr.actions_decks()``, which needs the
    # translation backend initialised. Do it here so these tests pass in
    # isolation, not just after another test (e.g. test_i18n) happened to run
    # first and set the global backend.
    anki.lang.set_lang("en")


def _toolbar() -> Toolbar:
    """A ``Toolbar`` over fully faked ``mw``/web — no Qt objects created."""
    mw = MagicMock()
    mw.state = "deckBrowser"
    return Toolbar(mw, MagicMock())


# --- show_* now navigate the single window instead of opening popups --------


def test_show_home_navigates_to_home_tab() -> None:
    mw = MagicMock()
    aqt.readymcat_home.show_readymcat_home(mw)
    mw.moveToState.assert_called_once_with("readymcatHome")


def test_show_dashboard_navigates_to_dashboard_tab() -> None:
    mw = MagicMock()
    aqt.readymcat.show_readymcat_dashboard(mw)
    mw.moveToState.assert_called_once_with("readymcatDashboard")


# --- the four tabs exist and are wired to the four surfaces -----------------


def test_tab_bar_lists_the_four_tabs() -> None:
    tb = _toolbar()
    html = tb._readymcat_tabs()
    for tab_id in ("home", "study", "decks", "dashboard"):
        assert f'data-rmcat-tab="{tab_id}"' in html, f"{tab_id} tab missing"
        assert f"rmcatTab:{tab_id}" in tb.link_handlers, f"{tab_id} handler missing"


def test_home_tab_navigates_to_home_state() -> None:
    tb = _toolbar()
    tb._readymcat_tabs()
    tb._linkHandler("rmcatTab:home")
    tb.mw.moveToState.assert_called_once_with("readymcatHome")


def test_dashboard_tab_navigates_to_dashboard_state() -> None:
    tb = _toolbar()
    tb._readymcat_tabs()
    tb._linkHandler("rmcatTab:dashboard")
    tb.mw.moveToState.assert_called_once_with("readymcatDashboard")


def test_decks_tab_navigates_to_deck_browser() -> None:
    tb = _toolbar()
    tb._readymcat_tabs()
    tb._linkHandler("rmcatTab:decks")
    tb.mw.moveToState.assert_called_once_with("deckBrowser")


def test_study_tab_starts_review_in_a_single_load() -> None:
    # Straight to the reviewer (a double moveToState races the reviewer paint).
    tb = _toolbar()
    tb.mw.state = "deckBrowser"
    tb._readymcat_tabs()
    tb._linkHandler("rmcatTab:study")
    tb.mw.col.startTimebox.assert_called_once_with()
    tb.mw.moveToState.assert_called_once_with("review")


def test_study_tab_is_a_noop_when_already_reviewing() -> None:
    tb = _toolbar()
    tb.mw.state = "review"
    tb._readymcat_tabs()
    tb._linkHandler("rmcatTab:study")
    tb.mw.moveToState.assert_not_called()


# --- active-tab highlight tracks the main-window state ----------------------


@pytest.mark.parametrize(
    "state,expected",
    [
        ("deckBrowser", "decks"),
        ("overview", "study"),
        ("review", "study"),
        ("readymcatHome", "home"),
        ("readymcatDashboard", "dashboard"),
        ("profileManager", ""),
        ("startup", ""),
    ],
)
def test_active_tab_tracks_state(state: str, expected: str) -> None:
    import json

    tb = _toolbar()
    tb.set_active_tab(state)
    eval_js = tb.web.eval.call_args[0][0]
    # the active tab id is embedded as a JSON literal in the toggling JS
    assert json.dumps(expected) in eval_js


# --- the single window swaps its central widget / bottom bar per state ------


@pytest.mark.parametrize(
    "state,is_readymcat",
    [
        ("deckBrowser", False),
        ("overview", False),
        ("review", False),
        ("readymcatHome", True),
        ("readymcatDashboard", True),
    ],
)
def test_sync_chrome_points_central_and_bottom_at_state(
    state: str, is_readymcat: bool
) -> None:
    mw = MagicMock()
    aqt.main.AnkiQt._readymcat_sync_chrome(mw, state)

    # bottom bar is hidden on the ReadyMCAT tabs, shown on the standard screens
    mw.bottomWeb.setVisible.assert_called_once_with(not is_readymcat)
    # active tab always kept in sync
    mw.toolbar.set_active_tab.assert_called_once_with(state)
    # standard screens render into the shared mw.web; ReadyMCAT tabs manage
    # their own central widget in their state handler
    if is_readymcat:
        mw.web_stack.setCurrentWidget.assert_not_called()
    else:
        mw.web_stack.setCurrentWidget.assert_called_once_with(mw.web)


def test_readymcat_tab_states_constant() -> None:
    assert READYMCAT_TAB_STATES == ("readymcatHome", "readymcatDashboard")


def test_state_handlers_are_registered() -> None:
    # moveToState dispatches to _{state}State; both ReadyMCAT tab states need one
    assert callable(aqt.main.AnkiQt._readymcatHomeState)
    assert callable(aqt.main.AnkiQt._readymcatDashboardState)


def test_interactive_state_includes_readymcat_tabs() -> None:
    # so a dropped/opened file (onAppMsg) is handled while on a ReadyMCAT tab
    for st in ("readymcatHome", "readymcatDashboard", "deckBrowser", "review"):
        mw = MagicMock()
        mw.state = st
        assert aqt.main.AnkiQt.interactiveState(mw) is True
    for st in ("profileManager", "startup"):
        mw = MagicMock()
        mw.state = st
        assert aqt.main.AnkiQt.interactiveState(mw) is False


def test_tab_probe_markers_cover_all_tabs() -> None:
    from aqt.readymcat_home import _TAB_MARKERS

    assert set(_TAB_MARKERS) == {"home", "study", "decks", "dashboard"}
