# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Desktop host for ReadyMCAT runtime teach-on-miss ladder generation.

The pure generation logic (prompt, parser, guardrails, OpenAI call) lives in
``readymcat/tools/ladder_gen.py`` so it is shared, unchanged, with the eval
harness. This aqt-layer module is the thin *host* around it:

* it decides whether generation is enabled (an ``OPENAI_API_KEY`` is present
  and the user hasn't opted out);
* it turns a card's fields into the grounding :class:`CardContext`;
* it caches a validated ladder per note in a sidecar next to the collection
  (``readymcat_generated_ladders.json``) so a card is only ever generated once
  and every later miss is instant; and
* :func:`generate_and_cache` is written to be safe to run off the main thread
  (it touches only the network, the pure core and the sidecar file — never the
  collection), so the reviewer can generate in the background without freezing
  the UI.

The generated ladder uses the same ``{"q", "a"}`` shape as the authored
``subquestions.json`` concepts, so the reviewer renders it with the existing
teach-on-miss flow.
"""

from __future__ import annotations

import json
import os
import re
from html import unescape
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

from aqt.readymcat_tools import load_tool_module

#: Sidecar cache, next to the collection (mirrors where the other ReadyMCAT
#: sidecars live). Keyed by note id so a generated ladder survives restarts and
#: is reused on every later miss of that card.
CACHE_FILENAME = "readymcat_generated_ladders.json"

#: Opt-out escape hatch (e.g. for e2e runs that must stay offline/deterministic).
_DISABLE_ENV = "READYMCAT_DISABLE_LADDER_GEN"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_core_module: Optional[ModuleType] = None
_core_loaded = False


def _core() -> Optional[ModuleType]:
    """Load (and cache) the pure ``ladder_gen`` core module by path.

    The path lookup lives in ``aqt.readymcat_tools`` (shared by every ReadyMCAT
    aqt host); this only adds the load-once cache. Defensive: returns ``None``
    if it cannot be located/imported, in which case generation is treated as
    unavailable and the reviewer falls back.
    """
    global _core_module, _core_loaded
    if not _core_loaded:
        _core_loaded = True
        _core_module = load_tool_module("ladder_gen.py", "readymcat_ladder_gen_core")
    return _core_module


def is_enabled() -> bool:
    """True when runtime generation should be attempted.

    Requires an ``OPENAI_API_KEY`` (this is the one feature that makes a
    network call), no explicit opt-out, and the core module present. When
    False the reviewer behaves exactly as before generation existed.
    """
    if os.environ.get(_DISABLE_ENV):
        return False
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    return _core() is not None


def _plain_text(html: str) -> str:
    """Strip tags/entities from card HTML to plain grounding text."""
    text = _TAG_RE.sub(" ", html or "")
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _note_field(note: Any, name: str) -> str:
    """Best-effort read of a named field; '' if the notetype lacks it."""
    try:
        return str(note[name])
    except Exception:
        return ""


def build_context(note: Any, question_html: str, answer_html: str) -> Any:
    """Build the core ``CardContext`` for a note from its rendered Q/A.

    Works for any notetype: a ReadyMCAT card contributes its ``Source`` field
    as extra grounding; a plain imported card grounds on its answer text only
    (the core flags that as 'card-only'). Called on the main thread before the
    background task starts, so touching the note here is safe.
    """
    core = _core()
    assert core is not None, "build_context called while generation unavailable"
    source = _note_field(note, "Source")
    return core.CardContext(
        _plain_text(question_html),
        _plain_text(answer_html),
        source=_plain_text(source),
        tags=list(note.tags),
    )


def _cache_path(col_path: Optional[str]) -> Optional[Path]:
    if not col_path:
        return None
    return Path(col_path).resolve().parent / CACHE_FILENAME


def _read_cache(col_path: Optional[str]) -> dict[str, Any]:
    path = _cache_path(col_path)
    if not path or not path.is_file():
        return {"version": 1, "ladders": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("ladders"), dict):
            return data
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not read generated-ladder cache", exc)
    return {"version": 1, "ladders": {}}


def cached_ladder(
    col_path: Optional[str], note_id: int
) -> Optional[list[dict[str, str]]]:
    """Return the previously-generated ladder for ``note_id``, or ``None``."""
    ladders = _read_cache(col_path).get("ladders", {})
    rungs = ladders.get(str(note_id))
    if not isinstance(rungs, list) or not rungs:
        return None
    clean: list[dict[str, str]] = []
    for rung in rungs:
        if isinstance(rung, dict) and rung.get("q") and rung.get("a"):
            clean.append({"q": str(rung["q"]), "a": str(rung["a"])})
    return clean or None


def _write_cache(
    col_path: Optional[str], note_id: int, ladder: list[dict[str, str]]
) -> None:
    path = _cache_path(col_path)
    if not path:
        return
    try:
        data = _read_cache(col_path)
        data.setdefault("ladders", {})[str(note_id)] = ladder
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not write generated-ladder cache", exc)


def generate_and_cache(
    col_path: Optional[str], note_id: int, context: Any
) -> dict[str, Any]:
    """Generate a ladder for one card, cache it on success, and return a
    plain-dict outcome (safe to hand back to the main thread).

    Runs entirely off the collection — only the pure core (which makes the
    OpenAI call) and the sidecar file — so it is safe to call from a
    background worker.
    """
    core = _core()
    if core is None:  # pragma: no cover - defensive
        return {
            "ok": False,
            "ladder": None,
            "validation": None,
            "error": "core unavailable",
        }
    outcome = core.generate_ladder(context)
    result = outcome.as_dict()
    if outcome.ok and outcome.ladder:
        _write_cache(col_path, note_id, outcome.ladder)
    return result


def derive_title_category(note: Any) -> tuple[str, str]:
    """A human title + AAMC category for the synthesized generated concept.

    Title prefers the card's ``Subtopic`` field, else the leaf of its first
    tag, else a generic label. Category is pulled from a ``#ReadyMCAT::AAMC::``
    tag when present so the generated concept slots into the same reporting as
    authored ones; otherwise it is left blank.
    """
    subtopic = _note_field(note, "Subtopic").strip()
    category = ""
    leaf = ""
    for tag in note.tags:
        if "AAMC::" in tag:
            category = tag.rsplit("::", 1)[-1]
        if not leaf and "::" in tag:
            leaf = tag.rsplit("::", 1)[-1]
    title = subtopic or leaf or "Guided review"
    return title, category
