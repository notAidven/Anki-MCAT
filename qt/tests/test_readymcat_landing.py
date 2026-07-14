# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the ReadyMCAT startup landing routing (``aqt.main``).

ReadyMCAT opens straight to its own experience rather than the bare Anki deck
browser. This module guards that contract:

* a genuinely new profile (no diagnostic prior) still sees the introductory
  diagnostic first, and the landing surface is *not* also auto-opened
  (exactly one entry surface opens per launch);
* every returning/provisioned profile lands directly on
  ``READYMCAT_LANDING_ROUTE`` — the study/launcher home hub; and
* that route is a single, servable flip-point constant, so switching the
  landing surface to the honest-memory dashboard is a one-line change.

The routing is pure Qt plumbing around the already-tested, Qt-free decision in
``aqt.readymcat.maybe_show_diagnostic_on_launch`` (see
``pylib/tests/test_readymcat_home.py`` for the decision itself), so these tests
drive the two ``AnkiQt`` helpers directly with a fake ``mw`` and never need a
live Qt event loop or collection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import aqt.main
import aqt.readymcat
import aqt.readymcat_home
from aqt.main import READYMCAT_LANDING_ROUTE
from aqt.mediasrv import is_sveltekit_page


def _fake_mw() -> MagicMock:
    """A stand-in for ``AnkiQt`` with a loaded collection."""
    mw = MagicMock()
    mw.col = object()
    return mw


# --- the flip-point constant -------------------------------------------------


def test_landing_route_defaults_to_the_home_hub() -> None:
    # Requirement: a returning/provisioned profile opens directly to the
    # study/launcher home hub, not the deck browser.
    assert READYMCAT_LANDING_ROUTE == "readymcat-home"


def test_landing_route_is_a_servable_sveltekit_page() -> None:
    # A typo'd/unregistered landing route would 404 on launch instead of
    # opening a page, so the flip-point constant must always resolve to a
    # registered SvelteKit page. Both supported surfaces must stay servable so
    # flipping the constant is always safe.
    assert is_sveltekit_page(READYMCAT_LANDING_ROUTE)
    assert is_sveltekit_page("readymcat-dashboard")
    assert is_sveltekit_page("readymcat-home")


# --- _open_readymcat_landing: the constant -> window mapping -----------------


def test_open_landing_opens_the_home_hub_by_default(monkeypatch) -> None:
    opened: list[tuple[str, object]] = []
    monkeypatch.setattr(
        aqt.readymcat,
        "show_readymcat_dashboard",
        lambda mw: opened.append(("dashboard", mw)),
    )
    monkeypatch.setattr(
        aqt.readymcat_home,
        "show_readymcat_home",
        lambda mw: opened.append(("home", mw)),
    )
    mw = _fake_mw()
    aqt.main.AnkiQt._open_readymcat_landing(mw)
    assert [kind for kind, _ in opened] == ["home"]
    assert opened[0][1] is mw


def test_open_landing_flips_to_the_dashboard_with_one_constant(monkeypatch) -> None:
    # Flipping the single constant is enough to land on the dashboard instead.
    monkeypatch.setattr(aqt.main, "READYMCAT_LANDING_ROUTE", "readymcat-dashboard")
    opened: list[str] = []
    monkeypatch.setattr(
        aqt.readymcat,
        "show_readymcat_dashboard",
        lambda mw: opened.append("dashboard"),
    )
    monkeypatch.setattr(
        aqt.readymcat_home,
        "show_readymcat_home",
        lambda mw: opened.append("home"),
    )
    aqt.main.AnkiQt._open_readymcat_landing(_fake_mw())
    assert opened == ["dashboard"]


def test_open_landing_is_a_noop_without_a_collection(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        aqt.readymcat,
        "show_readymcat_dashboard",
        lambda mw: opened.append("dashboard"),
    )
    mw = MagicMock()
    mw.col = None
    aqt.main.AnkiQt._open_readymcat_landing(mw)
    assert opened == []


# --- _route_readymcat_launch: diagnostic-first vs. landing -------------------


def test_returning_profile_routes_to_the_landing_surface(monkeypatch) -> None:
    # The diagnostic declines (already taken / no bank / skipped), so a
    # returning profile lands on the configured landing surface.
    monkeypatch.setattr(
        aqt.readymcat, "maybe_show_diagnostic_on_launch", lambda mw: False
    )
    mw = _fake_mw()
    aqt.main.AnkiQt._route_readymcat_launch(mw)
    mw._open_readymcat_landing.assert_called_once_with()


def test_new_profile_sees_diagnostic_first_and_not_the_landing(monkeypatch) -> None:
    # The diagnostic claims the launch (genuinely new profile), so the landing
    # surface must NOT also open — exactly one entry surface auto-opens.
    monkeypatch.setattr(
        aqt.readymcat, "maybe_show_diagnostic_on_launch", lambda mw: True
    )
    mw = _fake_mw()
    aqt.main.AnkiQt._route_readymcat_launch(mw)
    mw._open_readymcat_landing.assert_not_called()


def test_launch_routing_is_a_noop_without_a_collection(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        aqt.readymcat,
        "maybe_show_diagnostic_on_launch",
        lambda mw: called.append("diag") or False,
    )
    mw = MagicMock()
    mw.col = None
    aqt.main.AnkiQt._route_readymcat_launch(mw)
    assert called == []
    mw._open_readymcat_landing.assert_not_called()
