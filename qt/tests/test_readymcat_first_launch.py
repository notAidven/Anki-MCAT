# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""First-launch clone-and-run contract for the pre-loaded ReadyMCAT content.

A fresh clone + a brand-new (empty) profile must load the introductory
diagnostic, the pre-loaded decks, ``taxonomy.json`` and ``subquestions.json``
from files that SHIP in the repository — with ZERO manual file-copying into the
profile dir. This used to be worked around by hand-copying ``diagnostic_quiz``
/ ``taxonomy`` / ``subquestions`` next to the collection; these tests lock in
that first-launch provisioning + the desktop path-resolution helpers now do it
automatically.

They drive the real aqt helpers (``aqt.readymcat`` + ``aqt.readymcat_provision``)
with a fake ``mw`` whose ``col`` is a real, empty collection in a throwaway temp
dir, so no live Qt event loop is needed (mirroring test_readymcat_landing.py).
The path resolution is ``__file__``-relative to the repo root, so it is
independent of the working directory the tests happen to run in.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import aqt.readymcat as readymcat
import aqt.readymcat_provision as provision
from anki.collection import Collection

SIDECARS = ("taxonomy.json", "subquestions.json", "diagnostic_quiz.json")


def _fresh_mw(tmp_path: Path) -> tuple[MagicMock, Collection]:
    """A fake AnkiQt with a real, empty collection in a fresh (empty) profile."""
    col = Collection(str(tmp_path / "collection.anki2"))
    mw = MagicMock()
    mw.col = col
    return mw, col


def test_diagnostic_quiz_resolves_from_shipped_file_before_provisioning(tmp_path):
    """The diagnostic bank loads from the bundled repo file even with a brand-new
    empty profile and nothing copied next to the collection — the exact case that
    used to surface "the diagnostic needs its question bank (diagnostic_quiz.json)".
    """
    mw, col = _fresh_mw(tmp_path)
    try:
        # A genuinely fresh profile dir: nothing placed next to the collection.
        assert not list(tmp_path.glob("*.json"))

        quiz_path = readymcat._bundled_quiz_path(mw)
        assert quiz_path and Path(quiz_path).is_file(), (
            "diagnostic_quiz.json should resolve from the shipped repo files"
        )

        quiz = col._backend.get_diagnostic_quiz(quiz_path=quiz_path, mode="short")
        assert quiz.present and quiz.items
    finally:
        col.close()


def test_taxonomy_path_falls_back_to_the_shipped_file(tmp_path):
    """``_bundled_taxonomy_path`` hands back the bundled taxonomy.json when none
    is next to the collection (parity with ``_bundled_quiz_path``), and returns
    "" once one is present next to the collection (so the backend resolves it)."""
    mw, col = _fresh_mw(tmp_path)
    try:
        shipped = readymcat._bundled_taxonomy_path(mw)
        assert shipped and Path(shipped).is_file()

        # Simulate provisioning having placed it next to the collection.
        (tmp_path / "taxonomy.json").write_text(
            Path(shipped).read_text(encoding="utf-8"), encoding="utf-8"
        )
        assert readymcat._bundled_taxonomy_path(mw) == ""
    finally:
        col.close()


def test_first_launch_provisions_decks_and_places_all_sidecars(tmp_path):
    """The full first-launch flow: provision the decks, place every sidecar next
    to a fresh collection, then confirm the backend resolves the diagnostic and
    taxonomy WITHOUT any explicit path (i.e. next to the collection) and the
    teach-on-miss ladders load — all from shipped files, no manual copying."""
    mw, col = _fresh_mw(tmp_path)
    try:
        core = provision._load_core()
        stats = core.provision_all(col, log=lambda *_a, **_k: None)

        # All four content types built into the fresh, previously-empty profile.
        assert set(stats) == {"mcq", "free_response", "passage", "cars"}
        assert all(stat.notes_created > 0 for stat in stats.values())
        # One card per note for every ReadyMCAT notetype, so the collection holds
        # exactly what provisioning reports it created.
        assert col.card_count() == sum(stat.notes_created for stat in stats.values())

        provision.place_sidecars(mw)
        for name in SIDECARS:
            assert (tmp_path / name).is_file(), f"{name} not placed next to collection"

        # Backend now finds the diagnostic next to the collection (empty path) —
        # the resolution that previously required a hand-copied file.
        quiz = col._backend.get_diagnostic_quiz(quiz_path="", mode="short")
        assert quiz.present and quiz.items

        # Taxonomy resolves through the desktop helper + backend queue.
        resp = col._backend.points_at_stake_queue(
            taxonomy_path=readymcat._bundled_taxonomy_path(mw), deck_id=0, limit=0
        )
        assert resp.coverage.categories_covered > 0

        # Teach-on-miss ladders load from the placed sidecar.
        subs = readymcat.load_subquestions(col.path, force=True)
        assert subs and subs.concepts
    finally:
        col.close()
