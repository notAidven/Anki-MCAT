# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""ReadyMCAT desktop integration helpers.

This module hosts the two ReadyMCAT desktop features that live in the ``aqt``
layer:

* The honest-memory **dashboard** window (:class:`ReadyMCATDashboard`), which
  hosts the Svelte ``readymcat-dashboard`` page. That page consumes the
  points-at-stake backend message (per-topic mastery/weakness, the ranged memory
  score and the coverage map, obeying the give-up rule).
* The **teach-on-miss** support used by the desktop reviewer
  (``aqt/reviewer.py``): it loads the pre-authored guiding sub-question ladders
  from ``subquestions.json`` and resolves whether a given card belongs to one of
  the curated high-value concepts.

The ladders are content (not engine logic); see ``subquestions.json`` at the
repo root for the schema and ``readymcat/README.md`` for the design.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aqt.main
from aqt.qt import QDialog, Qt, QVBoxLayout
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind

# --- Honest-memory dashboard window -----------------------------------------


class ReadyMCATDashboard(QDialog):
    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        super().__init__(mw, Qt.WindowType.Window)
        self.mw = mw
        self.name = "readyMCATDashboard"
        mw.garbage_collect_on_dialog_finish(self)
        self.setWindowTitle("ReadyMCAT — Honest Memory")
        self.setMinimumSize(720, 720)
        disable_help_button(self)
        restoreGeom(self, self.name, default_size=(820, 820))

        self.web = AnkiWebView(self, kind=AnkiWebViewKind.READYMCAT_DASHBOARD)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)

        self.web.load_sveltekit_page(self._page_path())
        self.show()

    def _page_path(self) -> str:
        page = "readymcat-dashboard"
        taxonomy = _bundled_taxonomy_path(self.mw)
        if taxonomy:
            return f"{page}?taxonomy={quote(taxonomy)}"
        return page

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd == "close":
            self.close()
        return False

    def reject(self) -> None:
        if self.web:
            self.web.cleanup()
            self.web = None  # type: ignore[assignment]
        saveGeom(self, self.name)
        QDialog.reject(self)


def _bundled_taxonomy_path(mw: aqt.main.AnkiQt) -> str:
    """Locate a taxonomy.json.

    Prefer one next to the collection (the backend finds that itself, so we
    return ""); otherwise fall back to a stub in the working directory, which is
    handy for `just run` development builds."""
    if mw.col is not None:
        col_dir = os.path.dirname(mw.col.path)
        if os.path.exists(os.path.join(col_dir, "taxonomy.json")):
            return ""
    candidate = os.path.join(os.getcwd(), "taxonomy.json")
    if os.path.exists(candidate):
        return candidate
    return ""


def show_readymcat_dashboard(mw: aqt.main.AnkiQt) -> None:
    ReadyMCATDashboard(mw)


# --- Teach-on-miss support --------------------------------------------------


@dataclass
class Concept:
    """One curated concept and its pre-authored ladder."""

    id: str
    title: str
    category: str
    match_tags: list[str]
    ladder: list[dict[str, str]]
    resource: dict[str, str] = field(default_factory=dict)


@dataclass
class Subquestions:
    concepts: list[Concept]


_cache: Subquestions | None = None
_loaded = False


def _candidate_paths(col_path: str | None) -> list[Path]:
    """Where to look for subquestions.json, most specific first."""
    paths: list[Path] = []
    env = os.environ.get("READYMCAT_SUBQUESTIONS")
    if env:
        paths.append(Path(env))
    if col_path:
        col_dir = Path(col_path).resolve().parent
        paths.append(col_dir / "subquestions.json")
        paths.append(col_dir.parent / "subquestions.json")
    # repo root, relative to this file (qt/aqt/readymcat.py -> repo root)
    paths.append(Path(__file__).resolve().parents[2] / "subquestions.json")
    paths.append(Path.cwd() / "subquestions.json")
    return paths


def load_subquestions(
    col_path: str | None = None, force: bool = False
) -> Subquestions | None:
    """Load (and cache) the ladders. Returns None if no file is found."""
    global _cache, _loaded
    if _loaded and not force:
        return _cache
    _loaded = True
    _cache = None
    for path in _candidate_paths(col_path):
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            print("ReadyMCAT: could not read", path, exc)
            continue
        concepts: list[Concept] = []
        for raw in data.get("concepts", []):
            ladder = [
                {"q": str(rung.get("q", "")), "a": str(rung.get("a", ""))}
                for rung in raw.get("ladder", [])
                if rung.get("q") and rung.get("a")
            ]
            if not ladder or not raw.get("match_tags"):
                continue
            concepts.append(
                Concept(
                    id=str(raw["id"]),
                    title=str(raw.get("title", raw["id"])),
                    category=str(raw.get("category", "")),
                    match_tags=[str(t) for t in raw.get("match_tags", [])],
                    ladder=ladder,
                    resource={k: str(v) for k, v in raw.get("resource", {}).items()},
                )
            )
        _cache = Subquestions(concepts=concepts)
        print(f"ReadyMCAT: loaded {len(concepts)} teach-on-miss concepts from {path}")
        return _cache
    return None


def _is_path_prefix(prefix: str, value: str) -> bool:
    """True if ``prefix`` matches ``value`` on '::' path boundaries."""
    return value == prefix or value.startswith(prefix + "::")


def match_concept(tags: list[str], data: Subquestions | None) -> Concept | None:
    """Resolve a card (by its tags) to a concept; longest prefix wins."""
    if not data:
        return None
    best_len = -1
    best: Concept | None = None
    for concept in data.concepts:
        for prefix in concept.match_tags:
            if any(_is_path_prefix(prefix, tag) for tag in tags) and (
                len(prefix) > best_len
            ):
                best_len = len(prefix)
                best = concept
    return best


_URL_RE = re.compile(r"""https?://[^\s"'<>)]+""")


def extract_resource_link(html: str) -> str | None:
    """Pull the first external http(s) link out of card HTML, if any.

    Media files are stored as local filenames, so an http(s) URL in a card is
    typically a real resource (e.g. a Khan Academy link)."""
    match = _URL_RE.search(html or "")
    return match.group(0) if match else None


def log_event(col_path: str | None, event: dict[str, Any]) -> None:
    """Append a teach-on-miss event to a JSONL log next to the collection.

    Instruments the PRD's headline metric (corrected-concept re-retrieval): each
    miss, ladder result, and self-mark is recorded so a later analysis can ask
    whether teach-on-miss concepts are recalled better when they return."""
    if not col_path:
        return
    try:
        log_path = Path(col_path).resolve().parent / "readymcat_teach_on_miss_log.jsonl"
        record = {"ts": round(time.time(), 3), **event}
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not write teach-on-miss log", exc)
