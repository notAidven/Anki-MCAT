# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Desktop entry point for loading SYNTHETIC ReadyMCAT demo data.

This is a thin GUI wrapper around the pure-``anki`` seeder in
``readymcat/tools/seed_demo_dashboard.py``. It powers the
*Tools → Load ReadyMCAT demo data (SYNTHETIC)* action and an env-gated
auto-seed used by the headless e2e/screenshot harness.

Honesty rule: the data this creates is FAKE — a preview of how the honest-memory
dashboard looks once populated, not a real student's readiness. The action label,
the confirmation dialog, every seeded card's text, and a ``ReadyMCAT_SYNTHETIC_DEMO``
tag all say so.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aqt.main

_core: ModuleType | None = None


def _load_core() -> ModuleType:
    """Load the shared pure-``anki`` seeder module by path (cached).

    Located relative to this file (``qt/aqt/readymcat_demo.py`` -> repo root ->
    ``readymcat/tools/seed_demo_dashboard.py``), mirroring how ``aqt.readymcat``
    locates its bundled content files."""
    global _core
    if _core is not None:
        return _core
    candidates = [
        Path(__file__).resolve().parents[2]
        / "readymcat"
        / "tools"
        / "seed_demo_dashboard.py",
        Path.cwd() / "readymcat" / "tools" / "seed_demo_dashboard.py",
    ]
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location(
                "readymcat_seed_demo_dashboard", path
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _core = module
            return module
    raise FileNotFoundError(
        "seed_demo_dashboard.py not found; expected under readymcat/tools/."
    )


_CONFIRM_LOAD = (
    "Load SYNTHETIC ReadyMCAT demo data?\n\n"
    "This creates fake, clearly-labelled cards and an invented review history so "
    "the honest-memory dashboard renders fully populated. It is a UI preview only "
    "— NOT a real measure of readiness.\n\n"
    "Every card is tagged 'ReadyMCAT_SYNTHETIC_DEMO' and can be removed later by "
    "searching that tag in the Browser."
)

_CONFIRM_RESEED = (
    "Synthetic ReadyMCAT demo data is already loaded.\n\n"
    "Rebuild it from scratch? (The existing 'ReadyMCAT_SYNTHETIC_DEMO' cards will "
    "be removed and freshly regenerated.)"
)


def _open_dashboard(mw: "aqt.main.AnkiQt") -> None:
    try:
        from aqt.readymcat import show_readymcat_dashboard

        show_readymcat_dashboard(mw)
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT demo: could not open dashboard", exc)


def _summary(stats) -> str:
    if getattr(stats, "already_seeded", False):
        return (
            "Synthetic demo data is already present "
            f"({stats.cards_created} cards). Opening the dashboard."
        )
    lines = [
        "Loaded SYNTHETIC ReadyMCAT demo data (a UI preview, not real readiness).",
        "",
        f"• {stats.cards_created} demo cards across {stats.categories_covered} "
        "AAMC categories",
        f"• {getattr(stats, 'questions_created', 0)} synthetic practice questions",
        f"• {getattr(stats, 'flashcards_created', 0)} authorless flashcards "
        "(retrieve-before-reveal teach-on-miss demo)",
        f"• {stats.reviews_created} synthetic graded reviews",
    ]
    if stats.memory_low is not None and stats.memory_high is not None:
        lines.append(
            f"• Memory range: {round(stats.memory_low * 100)}%–"
            f"{round(stats.memory_high * 100)}% (SYNTHETIC)"
        )
    if getattr(stats, "performance_low", None) is not None:
        lines.append(
            f"• Performance range: {round(stats.performance_low * 100)}%–"
            f"{round(stats.performance_high * 100)}% over "
            f"{stats.performance_attempts} attempts (SYNTHETIC)"
        )
    if getattr(stats, "readiness_point", None) is not None and stats.readiness_meets:
        lines.append(
            f"• Readiness (HEURISTIC, uncalibrated): ~{round(stats.readiness_point)} "
            f"({round(stats.readiness_low)}–{round(stats.readiness_high)}) on 472–528"
        )
    if stats.coverage_covered is not None:
        lines.append(
            f"• Coverage: {stats.coverage_covered}/{stats.coverage_total} categories"
            f" ({round((stats.coverage_fraction or 0) * 100)}% of outline)"
        )
    if stats.study_next:
        preview = ", ".join(
            f"{cat} ({points:.1f} pts)" for cat, _name, points in stats.study_next[:3]
        )
        lines.append(f"• Study next: {preview}")
    lines += ["", "Remove anytime via Browser search 'tag:ReadyMCAT_SYNTHETIC_DEMO'."]
    return "\n".join(lines)


def load_readymcat_demo_data(mw: "aqt.main.AnkiQt") -> None:
    """Tools-menu action: confirm, seed synthetic data, open the dashboard."""
    if mw.col is None:
        return
    from aqt.utils import askUser, showInfo

    try:
        core = _load_core()
    except Exception as exc:
        showInfo(f"Could not load the ReadyMCAT demo seeder:\n{exc}")
        return

    reseed = False
    if core.has_demo_data(mw.col):
        if not askUser(_CONFIRM_RESEED, title="ReadyMCAT demo data"):
            _open_dashboard(mw)
            return
        reseed = True
    elif not askUser(_CONFIRM_LOAD, title="ReadyMCAT demo data"):
        return

    mw.progress.start(label="Seeding SYNTHETIC ReadyMCAT demo data…", immediate=True)
    try:
        stats = core.seed_demo_data(mw.col, reseed=reseed, log=print)
    except Exception as exc:
        mw.progress.finish()
        showInfo(f"Failed to seed ReadyMCAT demo data:\n{exc}")
        return
    else:
        mw.progress.finish()

    mw.reset()
    showInfo(_summary(stats), title="ReadyMCAT demo data")
    _open_dashboard(mw)


def maybe_seed_demo_on_launch(mw: "aqt.main.AnkiQt") -> None:
    """Auto-seed synthetic demo data when ``READYMCAT_SEED_DEMO`` is set.

    Dev/e2e only: the headless screenshot harness sets this so the throwaway
    profile's dashboard is populated without any UI interaction. Silent and
    defensive so it can never block start-up."""
    if not os.environ.get("READYMCAT_SEED_DEMO"):
        return
    if mw.col is None:
        return
    try:
        core = _load_core()
        if core.has_demo_data(mw.col):
            return
        core.seed_demo_data(mw.col, log=print)
        mw.reset()
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT demo: auto-seed on launch failed", exc)
