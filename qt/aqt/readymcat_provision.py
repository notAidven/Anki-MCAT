# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""First-launch provisioning for the pre-loaded ReadyMCAT decks.

A brand-new ReadyMCAT user should get the full MCAT deck — multiple-choice,
free-response *and* passage cards — with **zero import**. This module is the
desktop hook that makes that happen: on collection load it checks whether each
content type is already present and, if not, builds it directly from the bundled
banks (see ``readymcat/tools/build_question_bank.py``) and drops the sidecar
files the topic-aware features expect (``taxonomy.json``, ``subquestions.json``,
``diagnostic_quiz.json``) next to the collection.

It is a thin GUI wrapper around the pure ``anki`` builder, mirroring how
``qt/aqt/readymcat_demo.py`` wraps the demo seeder. Everything here is silent and
defensive so it can never block start-up; set ``READYMCAT_NO_PROVISION`` to skip
it (used by e2e/headless runs that manage their own fixtures).
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aqt.main

_core: ModuleType | None = None


def _load_core() -> ModuleType:
    """Load the shared pure-``anki`` builder module by path (cached).

    Located relative to this file (``qt/aqt/readymcat_provision.py`` -> repo root
    -> ``readymcat/tools/build_question_bank.py``), mirroring how
    ``aqt.readymcat_demo`` locates the seeder."""
    global _core
    if _core is not None:
        return _core
    candidates = [
        Path(__file__).resolve().parents[2]
        / "readymcat"
        / "tools"
        / "build_question_bank.py",
        Path.cwd() / "readymcat" / "tools" / "build_question_bank.py",
    ]
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location(
                "readymcat_build_question_bank", path
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _core = module
            return module
    raise FileNotFoundError(
        "build_question_bank.py not found; expected under readymcat/tools/."
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _first_existing(*candidates: Path) -> Path | None:
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _source_sidecars() -> dict[str, Path | None]:
    """Locate the bundled sidecar files to copy next to the collection."""
    root = _repo_root()
    cwd = Path.cwd()
    return {
        "taxonomy.json": _first_existing(root / "taxonomy.json", cwd / "taxonomy.json"),
        "subquestions.json": _first_existing(
            root / "subquestions.json", cwd / "subquestions.json"
        ),
        "diagnostic_quiz.json": _first_existing(
            root / "readymcat" / "diagnostic" / "diagnostic_quiz.json",
            cwd / "readymcat" / "diagnostic" / "diagnostic_quiz.json",
        ),
    }


def place_sidecars(mw: "aqt.main.AnkiQt") -> None:
    """Copy the topic-aware sidecar files next to the collection (if missing).

    Never overwrites a user's file. For an existing ``taxonomy.json`` it only
    tops up the ReadyMCAT MCQ tag-mappings so category resolution keeps working;
    it leaves the rest of the file untouched."""
    if mw.col is None:
        return
    try:
        col_dir = Path(mw.col.path).resolve().parent
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not resolve collection dir", exc)
        return

    sources = _source_sidecars()
    for name, src in sources.items():
        if src is None:
            continue
        dest = col_dir / name
        try:
            if not dest.exists():
                shutil.copyfile(src, dest)
                print(f"ReadyMCAT: placed {name} next to the collection.")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"ReadyMCAT: could not place {name}", exc)

    _ensure_taxonomy_mappings_present(mw, col_dir)


def _ensure_taxonomy_mappings_present(mw: "aqt.main.AnkiQt", col_dir: Path) -> None:
    """Make sure the collection-local taxonomy.json can resolve the MCQ tags."""
    taxonomy = col_dir / "taxonomy.json"
    if not taxonomy.exists():
        return
    try:
        core = _load_core()
        categories = core.all_content_categories()
        added = core.ensure_taxonomy_mappings(str(taxonomy), categories)
        if added:
            print(f"ReadyMCAT: added {added} mapping(s) to {taxonomy}.")
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not top up taxonomy mappings", exc)


def _all_content_present(core: ModuleType, col: "object") -> bool:
    """True once every pre-loaded content type (MCQ + FR + passage) exists."""
    try:
        return (
            core.has_mcq_deck(col)
            and core.has_fr_notes(col)
            and core.has_passage_notes(col)
        )
    except Exception:  # pragma: no cover - defensive
        return False


def maybe_provision_readymcat(mw: "aqt.main.AnkiQt") -> None:
    """Build the pre-loaded decks (MCQ + free-response + passage) on first
    launch, then place sidecars.

    Idempotent + silent: each content type is guarded independently, so if
    everything already exists this only ensures the sidecar files are present,
    and an existing collection missing a newer content type is topped up without
    duplicating anything. Skipped entirely when ``READYMCAT_NO_PROVISION`` is
    set."""
    if os.environ.get("READYMCAT_NO_PROVISION"):
        return
    if mw.col is None:
        return
    try:
        core = _load_core()
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: provisioning unavailable", exc)
        return

    try:
        if _all_content_present(core, mw.col):
            place_sidecars(mw)
            return
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: provisioning check failed", exc)
        return

    mw.progress.start(label="Preparing the ReadyMCAT question bank…", immediate=True)
    try:
        stats = core.provision_all(mw.col, log=print)
        place_sidecars(mw)
    except Exception as exc:
        mw.progress.finish()
        print("ReadyMCAT: could not provision the decks", exc)
        return
    mw.progress.finish()

    created = sum(s.notes_created for s in stats.values() if not s.already_present)
    if created:
        # Refresh so the freshly-built decks appear without a manual reload.
        mw.reset()
        from aqt.utils import tooltip

        categories: set[str] = set()
        for stat in stats.values():
            categories.update(getattr(stat, "categories", []) or [])
        tooltip(
            f"ReadyMCAT: loaded {created} items (MCQ + free-response + passage) "
            f"across {len(categories)} AAMC categories — no import needed.",
            period=5000,
        )
