# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Desktop entry point for the ReadyMCAT home / study-launcher hub.

The hub (Svelte ``ts/routes/readymcat-home``) is a single-screen dashboard
whose hero is four one-tap launch tiles — Multiple Choice, Free Response,
Passage Sets, CARS — each showing an honest due/available count and starting
that format's review in one click. A secondary row surfaces "what to study
next" (reusing the points-at-stake queue), the diagnostic entry, and
lightweight overall progress.

This module is a thin GUI wrapper, mirroring ``aqt.readymcat``'s dashboard /
diagnostic windows: the honest number-crunching lives in the pure
``readymcat/tools/home_launcher.py`` (loaded by path, no ``aqt`` dependency,
directly unit tested), and this module only wires it to Qt — the window, the
mediasrv JSON endpoint, one-tap review launch, and first-launch routing
between the diagnostic and the hub.
"""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from types import ModuleType
from typing import Any

import aqt.main
from anki.decks import DeckId
from aqt.qt import QDialog, Qt, QVBoxLayout
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind

# A single, reused filtered deck used to isolate a one-tap review session for
# formats that have nested child decks (see ``start_deck_review``). Reusing
# one deck (rather than minting a new one per click) avoids littering the
# deck list.
LAUNCHER_FILTERED_DECK_NAME = "ReadyMCAT Launcher"

# Order enum value for Deck.Filtered.SearchTerm.Order.DUE (proto/anki/decks.proto).
_ORDER_DUE = 6

_home_launcher: ModuleType | None = None
_home_launcher_loaded = False
_bank_module: ModuleType | None = None
_bank_loaded = False


def _load_home_launcher() -> ModuleType | None:
    """Load (and cache) the pure home-hub helper module by path.

    Mirrors ``aqt.readymcat._bank`` / ``aqt.readymcat_provision._load_core``."""
    global _home_launcher, _home_launcher_loaded
    if _home_launcher_loaded:
        return _home_launcher
    _home_launcher_loaded = True
    candidates = [
        Path(__file__).resolve().parents[2]
        / "readymcat"
        / "tools"
        / "home_launcher.py",
        Path.cwd() / "readymcat" / "tools" / "home_launcher.py",
    ]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location(
                "readymcat_home_launcher", path
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _home_launcher = module
            return module
        except Exception as exc:  # pragma: no cover - defensive
            print("ReadyMCAT: could not load home-hub helpers", exc)
            continue
    return None


def _load_bank() -> ModuleType | None:
    """Load (and cache) the pure question-bank module (deck name constants)."""
    global _bank_module, _bank_loaded
    if _bank_loaded:
        return _bank_module
    _bank_loaded = True
    candidates = [
        Path(__file__).resolve().parents[2]
        / "readymcat"
        / "tools"
        / "build_question_bank.py",
        Path.cwd() / "readymcat" / "tools" / "build_question_bank.py",
    ]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location(
                "readymcat_build_question_bank_for_home", path
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _bank_module = module
            return module
        except Exception as exc:  # pragma: no cover - defensive
            print("ReadyMCAT: could not load question-bank helpers", exc)
            continue
    return None


def _deck_names() -> dict[str, str] | None:
    launcher = _load_home_launcher()
    bank = _load_bank()
    if launcher is None or bank is None:
        return None
    return launcher.default_deck_names(bank)


# --- honest home-hub status (mediasrv JSON endpoint) ------------------------


def build_home_status(mw: aqt.main.AnkiQt) -> dict[str, Any]:
    """Build the JSON payload served as ``readymcatHomeStatus``.

    Returns an honest "unavailable" shape (rather than raising, which would
    404 the whole hub) when the collection or the pure helpers aren't ready."""
    if mw.col is None:
        return {"available": False, "reason": "no collection open"}
    launcher = _load_home_launcher()
    names = _deck_names()
    if launcher is None or names is None:
        return {"available": False, "reason": "home-hub helpers unavailable"}
    try:
        status = launcher.summarize_home_status(mw.col, names)
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not summarize home status", exc)
        return {"available": False, "reason": str(exc)}
    status["available"] = True
    return status


# --- one-tap review launch ---------------------------------------------------


def _isolating_search(key: str) -> str | None:
    launcher = _load_home_launcher()
    names = _deck_names()
    if launcher is None or names is None:
        return None
    return launcher.isolating_search_for(names, key)


def _start_review_now(mw: aqt.main.AnkiQt) -> None:
    """Jump straight into reviewing the currently-selected deck, matching the
    one-tap promise of the hub's tiles.

    Goes directly to the ``review`` state rather than stepping through
    ``overview`` first. The previous ``overview`` -> ``review`` hop issued two
    back-to-back async page loads into the *same* ``mw.web`` in one event-loop
    turn: the reviewer's queued ``_showQuestion`` / ``_mcqStart`` evals ran
    after the first load's ``domDone`` (painting the card), then the second
    (reviewer ``_initWeb``) load reloaded the page and wiped ``#qa`` with no
    pending evals left to repaint it — so tiles landed on a blank reviewer even
    though a card was loaded (rev.state was correct, ``#qa`` was empty). A
    single load has no such race. ``onStudyKey`` never hits this because its
    ``overview`` -> ``review`` steps are two separate user actions with the
    overview already settled in between.

    If nothing is due, ``Reviewer.nextCard()`` falls back to ``overview`` on
    its own, so the honest "no cards due" screen is still reached."""
    mw.col.startTimebox()
    mw.moveToState("review")


def _rebuild_launcher_deck(mw: aqt.main.AnkiQt, search: str) -> DeckId | None:
    """(Re)build the single, reused ReadyMCAT launcher filtered deck so it
    contains exactly the cards matching ``search``, and select it."""
    existing_id = mw.col.decks.id_for_name(LAUNCHER_FILTERED_DECK_NAME)
    seed_id = (
        existing_id
        if existing_id and mw.col.decks.is_filtered(existing_id)
        else DeckId(0)
    )
    deck = mw.col.sched.get_or_create_filtered_deck(deck_id=seed_id)
    deck.name = LAUNCHER_FILTERED_DECK_NAME
    deck.config.reschedule = True
    del deck.config.search_terms[:]
    term = deck.config.search_terms.add()
    term.search = search
    term.limit = 9999
    term.order = _ORDER_DUE  # type: ignore[assignment]
    result = mw.col.sched.add_or_update_filtered_deck(deck)
    did = DeckId(result.id)
    mw.col.sched.rebuild_filtered_deck(did)
    return did


def start_deck_review(mw: aqt.main.AnkiQt, key: str) -> None:
    """Start reviewing exactly one format's cards in one click.

    ``fr`` and ``cars`` are leaf decks, so a plain deck selection already
    reviews exactly that format. ``mcq`` (parents Free Response / Passages /
    Passages::CARS) and ``passage`` (parents Passages::CARS) are routed
    through a small, reused filtered deck scoped by search query instead —
    Anki's per-deck review always includes a deck's children, and without
    this the "Multiple Choice" tile would silently pull in every other
    format too, contradicting its own due count.
    """
    if mw.col is None:
        return
    names = _deck_names()
    if names is None or key not in names:
        return
    try:
        search = _isolating_search(key)
        if search is None:
            did = mw.col.decks.id_for_name(names[key])
            if did is None:
                return
            mw.col.decks.select(did)
        else:
            did = _rebuild_launcher_deck(mw, search)
            if did is None:
                return
            mw.col.decks.select(did)
        _start_review_now(mw)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"ReadyMCAT: could not start '{key}' review", exc)


# --- dev/e2e study probe -----------------------------------------------------
#
# The interactive ReadyMCAT reviewer renders its card into the desktop Qt
# webview (``mw.web``), NOT into a mediasrv-served page — so the Playwright e2e
# harness (whose own Chromium can only load mediasrv HTTP pages) cannot observe
# it directly. This dev-only probe bridges that gap: it drives a real study
# launch on the main thread and reads back the reviewer's live ``#qa`` HTML, so
# the e2e suite can assert a question actually paints (the regression this
# module fixes was a *blank* reviewer despite a loaded card) and is answerable,
# and that a wrong answer triggers the teach-on-miss ladder + struggling flag.
# It is gated behind ``dev_mode`` (ANKIDEV) by the mediasrv handler and is never
# reachable in a packaged build.

_PROBE_READ_QA_JS = "(document.getElementById('qa')||{}).innerHTML || ''"

# Click option ``__IDX__`` of the rendered MCQ, submit it, and hand back the
# resulting ``#qa`` — exactly the DOM path a user takes, so the returned HTML
# shows the real post-answer UI (explanation + Continue for a hit; the guiding
# ladder for a miss).
_PROBE_CLICK_JS = """
(function(){
  var idx = __IDX__;
  var opts = Array.prototype.slice.call(document.querySelectorAll('.rmcq-option'));
  if (opts.length > idx) { opts[idx].click(); }
  var btns = Array.prototype.slice.call(document.querySelectorAll('.rmcq-btn.primary'));
  var submit = btns.filter(function(b){ return !b.disabled; })[0];
  if (submit) { submit.click(); }
  return (document.getElementById('qa')||{}).innerHTML || '';
})()
"""


def _probe_correct_index(mw: aqt.main.AnkiQt) -> int:
    from aqt import readymcat

    try:
        card = mw.reviewer.card
        payload = readymcat.build_mcq_payload(card.note()) if card else None
        if payload:
            return max(0, min(3, int(payload.get("correctIndex", 0))))
    except Exception:  # pragma: no cover - defensive
        pass
    return 0


def _launch_for_probe(mw: aqt.main.AnkiQt, key: str, native: bool) -> None:
    """Mirror one of the two real launch flows the e2e must cover: the deck
    browser's native Study Now (select the deck, then review) or the home-hub
    tile (``start_deck_review``)."""
    # Return any cards the reused launcher filtered deck is still holding, so a
    # probe of one format isn't skewed by a previous probe's tile launch (the
    # filtered deck pulls a deck's cards out while active).
    launcher_id = mw.col.decks.id_for_name(LAUNCHER_FILTERED_DECK_NAME)
    if launcher_id and mw.col.decks.is_filtered(launcher_id):
        try:
            mw.col.sched.empty_filtered_deck(launcher_id)
        except Exception:  # pragma: no cover - defensive
            pass
    names = _deck_names()
    if native and names and key in names:
        did = mw.col.decks.id_for_name(names[key])
        if did is not None:
            mw.col.decks.select(did)
        mw.col.startTimebox()
        mw.moveToState("review")
    else:
        start_deck_review(mw, key)


def study_probe(mw: aqt.main.AnkiQt, options: dict[str, Any]) -> dict[str, Any]:
    """Start (and optionally answer) one review, returning what the reviewer
    webview actually rendered.

    ``options`` keys: ``key`` (mcq|fr|passage|cars), ``native`` (bool, native
    Study Now vs. hub tile) and ``answer`` (None | "correct" | "wrong" |
    "wrongFull"). Every GUI step runs on the main thread; the calling mediasrv
    worker thread blocks until the webview has painted so the HTTP response
    reflects the real on-screen state.
    """
    key = str(options.get("key", "mcq"))
    native = bool(options.get("native", False))
    answer = options.get("answer")

    result: dict[str, Any] = {"ok": False}
    done = threading.Event()

    def finish_with_qa(html: str | None) -> None:
        html = html or ""
        result.update(
            ok=True,
            state=mw.reviewer.state,
            card=mw.reviewer.card is not None,
            qa=html,
            qaLen=len(html),
            interactive=any(
                marker in html for marker in ("rmcq-wrap", "rmfr-wrap", "rmpsg-wrap")
            ),
        )
        done.set()

    def do_full_miss() -> None:
        """Exercise the Python teach-on-miss grading path (first miss ->
        guiding ladder -> still wrong) and report the struggling flag."""
        reviewer = mw.reviewer
        card = reviewer.card
        wrong = 1 if _probe_correct_index(mw) == 0 else 0
        try:
            reviewer._handle_mcq(f"first:wrong:{wrong}")
            reviewer._handle_mcq("reattempt:wrong")
            tags = list(card.note().tags) if card else []
        except Exception as exc:  # pragma: no cover - defensive
            result.update(ok=False, error=repr(exc))
            done.set()
            return
        result.update(
            ok=True,
            state=reviewer.state,
            struggling="ReadyMCAT::struggling" in tags,
            tags=tags,
        )
        done.set()

    def after_render() -> None:
        if answer == "wrongFull":
            do_full_miss()
        elif answer in ("correct", "wrong"):
            idx = _probe_correct_index(mw)
            click_idx = idx if answer == "correct" else (1 if idx == 0 else 0)
            mw.web.evalWithCallback(
                _PROBE_CLICK_JS.replace("__IDX__", str(click_idx)), finish_with_qa
            )
        else:
            mw.web.evalWithCallback(_PROBE_READ_QA_JS, finish_with_qa)

    def on_main() -> None:
        try:
            _launch_for_probe(mw, key, native)
        except Exception as exc:  # pragma: no cover - defensive
            result.update(ok=False, error=repr(exc))
            done.set()
            return
        # Give the reviewer webview time to load + paint before reading it.
        mw.progress.single_shot(1200, after_render, False)

    mw.taskman.run_on_main(on_main)
    if not done.wait(timeout=25):
        return {"ok": False, "error": "timeout"}
    return result


# --- the hub window ----------------------------------------------------------


class ReadyMCATHome(QDialog):
    """The home/study-launcher hub — the app's entry screen."""

    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        super().__init__(mw, Qt.WindowType.Window)
        self.mw = mw
        self.name = "readyMCATHome"
        mw.garbage_collect_on_dialog_finish(self)
        self.setWindowTitle("ReadyMCAT — Study Hub")
        self.setMinimumSize(760, 640)
        disable_help_button(self)
        restoreGeom(self, self.name, default_size=(1040, 800))

        self.web = AnkiWebView(self, kind=AnkiWebViewKind.READYMCAT_HOME)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)

        self.web.load_sveltekit_page(self._page_path())
        self.show()

    def _page_path(self) -> str:
        from urllib.parse import quote

        from aqt.readymcat import _bundled_taxonomy_path

        page = "readymcat-home"
        taxonomy = _bundled_taxonomy_path(self.mw)
        if taxonomy:
            return f"{page}?taxonomy={quote(taxonomy)}"
        return page

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd == "close":
            self.close()
        elif cmd.startswith("startDeck:"):
            key = cmd.split(":", 1)[1]
            self.close()
            start_deck_review(self.mw, key)
        elif cmd == "openDiagnostic":
            self.close()
            from aqt.readymcat import show_readymcat_diagnostic

            show_readymcat_diagnostic(self.mw)
        elif cmd == "openDashboard":
            self.close()
            from aqt.readymcat import show_readymcat_dashboard

            show_readymcat_dashboard(self.mw)
        elif cmd == "refresh":
            self.web.load_sveltekit_page(self._page_path())
        return False

    def reject(self) -> None:
        if self.web:
            self.web.cleanup()
            self.web = None  # type: ignore[assignment]
        saveGeom(self, self.name)
        QDialog.reject(self)


def show_readymcat_home(mw: aqt.main.AnkiQt) -> None:
    ReadyMCATHome(mw)


# --- first-launch routing: diagnostic vs. hub, never both -------------------


def maybe_show_home_on_launch(mw: aqt.main.AnkiQt) -> bool:
    """Open the home hub on launch, unless the diagnostic already claimed
    this launch (see ``route_readymcat_launch``). Silent + defensive."""
    if mw.col is None:
        return False
    try:
        show_readymcat_home(mw)
        return True
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not open home hub on launch", exc)
        return False


def route_readymcat_launch(mw: aqt.main.AnkiQt) -> None:
    """Decide once, per launch, between the introductory diagnostic and the
    home hub, and open exactly one of them.

    A genuinely new profile (no diagnostic prior yet, and a question bank is
    actually available) sees the diagnostic first; every other launch opens
    the home hub, which also surfaces "Take/Retake Diagnostic" as its own
    CTA. The decision itself is the pure, unit-tested
    ``home_launcher.should_open_diagnostic_on_launch`` /
    ``should_open_home_on_launch`` pair, so this function is just the Qt
    plumbing around it. Defensive: if the diagnostic can't determine
    availability, it declines and the hub opens instead — the collection
    always ends up somewhere useful.
    """
    if mw.col is None:
        return
    from aqt.readymcat import maybe_show_diagnostic_on_launch

    opened_diagnostic = maybe_show_diagnostic_on_launch(mw)
    if not opened_diagnostic:
        maybe_show_home_on_launch(mw)
