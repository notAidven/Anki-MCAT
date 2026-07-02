# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Load the pure ReadyMCAT helper modules that live under ``readymcat/tools/``.

The ReadyMCAT desktop features keep their real logic (bank building, demo
seeding, ladder generation, the home-hub aggregation) in pure, ``anki``/``aqt``-
free modules under ``readymcat/tools/`` so it can be unit-tested without a Qt or
collection dependency. Those modules deliberately sit OUTSIDE the ``aqt`` package
tree, so the aqt-layer hosts cannot ``import`` them normally — they load them by
path instead.

This module is the single home for that path-loading logic, which was previously
copy-pasted into five aqt hosts (``readymcat._bank`` / ``._load_home_launcher``,
``readymcat_provision._load_core``, ``readymcat_demo._load_core`` and
``readymcat_ladder_gen._core``). Callers keep their own module-level caches; this
only owns *finding and importing* a helper module.

Two variants match the two behaviours those hosts need:

* :func:`load_tool_module` — defensive: returns ``None`` (after logging) when the
  helper is missing or fails to import, so the feature degrades gracefully.
* :func:`require_tool_module` — strict: raises ``FileNotFoundError`` when no
  candidate location has the file, for features that cannot sensibly continue
  without it (the caller still handles that exception).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

#: The subdirectory (relative to the repo root and to the cwd) the pure helper
#: modules live in.
_TOOLS_SUBDIR = ("readymcat", "tools")


def _candidate_paths(filename: str) -> list[Path]:
    """Where a ``readymcat/tools`` helper may live, most specific first.

    ``qt/aqt/readymcat_tools.py`` -> repo root -> ``readymcat/tools/<filename>``,
    then the same path relative to the current working directory (which is how
    ``just run`` / packaged builds find it)."""
    repo_root = Path(__file__).resolve().parents[2]
    return [
        repo_root.joinpath(*_TOOLS_SUBDIR, filename),
        Path.cwd().joinpath(*_TOOLS_SUBDIR, filename),
    ]


def _import_from_path(path: Path, module_name: str) -> ModuleType:
    """Import the module at ``path`` under ``module_name`` (no caching)."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tool_module(filename: str, module_name: str) -> ModuleType | None:
    """Load a ``readymcat/tools`` helper by path, or ``None`` if unavailable.

    Any failure — a missing file or an import error — is swallowed and logged,
    matching the aqt hosts that fall back to inline logic when the pure helper
    cannot be loaded (e.g. an unusual packaged layout)."""
    for path in _candidate_paths(filename):
        try:
            if not path.is_file():
                continue
            return _import_from_path(path, module_name)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"ReadyMCAT: could not load {filename}", exc)
            continue
    return None


def require_tool_module(filename: str, module_name: str) -> ModuleType:
    """Load a ``readymcat/tools`` helper by path, raising if none is found.

    Unlike :func:`load_tool_module`, an import error is *not* swallowed (it
    propagates to the caller) and a missing file raises ``FileNotFoundError`` —
    for hosts that cannot degrade gracefully without the helper."""
    for path in _candidate_paths(filename):
        if path.is_file():
            return _import_from_path(path, module_name)
    raise FileNotFoundError(
        f"{filename} not found; expected under readymcat/tools/."
    )
