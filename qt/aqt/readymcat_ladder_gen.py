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

Each generated rung is a multiple-choice question
(``{"question", "options", "correctIndex", "explanation"}``): the student
*works it out* by choosing, and the reviewer renders it as an interactive MCQ
scaffold (retrieve-before-reveal) rather than the authored ``{"q", "a"}``
reveal-and-self-mark flow.
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

#: Cache/generation version, stamped into the sidecar. Bump whenever the
#: generation or grounding logic changes in a way that would make previously
#: cached ladders wrong — e.g. the grounding-text cleaning that stops diagram
#: markup (CSS, LaTeX/TikZ, SVG, image-occlusion shape data, ...) leaking into
#: the ladder. :func:`cached_ladder` ignores any cache stamped with a different
#: version, so stale ladders are transparently regenerated with the current
#: grounding instead of being replayed (which reintroduced bug 2).
#: v2: grounding-text cleaning (``clean_grounding_text``) added.
CACHE_VERSION = 2

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
    """Extract plain, human-readable grounding text from card HTML.

    Delegates to the shared core cleaner (``readymcat/tools/ladder_gen.py``) so
    the desktop runtime and the eval harness strip the *same* non-content
    markup — ``<script>``/``<style>`` bodies, image/SVG/diagram source, ``data:``
    URIs, media filenames and image-occlusion shape data — leaving only the text
    the model should ground on. Without this, a diagram/fill-in-the-blank card
    grounds the ladder on its LaTeX/TikZ/SVG source instead of its topic. Falls
    back to a minimal tag strip only if the core cannot be loaded.
    """
    core = _core()
    if core is not None:
        return str(core.clean_grounding_text(html))
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
        return {"version": CACHE_VERSION, "ladders": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("ladders"), dict):
            return data
    except Exception as exc:  # pragma: no cover - defensive
        print("ReadyMCAT: could not read generated-ladder cache", exc)
    return {"version": CACHE_VERSION, "ladders": {}}


def cached_ladder(
    col_path: Optional[str], note_id: int
) -> Optional[list[dict[str, Any]]]:
    """Return the previously-generated MCQ ladder for ``note_id``, or ``None``.

    Ignores caches written by an older :data:`CACHE_VERSION` (the whole file is
    stale after a generation/grounding change), so a ladder generated before the
    current grounding logic is regenerated rather than replayed. Also defensive
    about shape: a rung is kept only when it has a question, a list of options,
    an in-range integer ``correctIndex`` and an explanation, so a stale entry in
    the pre-MCQ ``{"q", "a"}`` format likewise yields ``None``.
    """
    data = _read_cache(col_path)
    if data.get("version") != CACHE_VERSION:
        return None
    ladders = data.get("ladders", {})
    rungs = ladders.get(str(note_id))
    if not isinstance(rungs, list) or not rungs:
        return None
    clean: list[dict[str, Any]] = []
    for rung in rungs:
        normalized = _normalize_cached_rung(rung)
        if normalized is not None:
            clean.append(normalized)
    return clean or None


def _normalize_cached_rung(rung: Any) -> Optional[dict[str, Any]]:
    """Coerce one cached rung to the MCQ shape, or ``None`` if unusable."""
    if not isinstance(rung, dict):
        return None
    question = str(rung.get("question", "")).strip()
    explanation = str(rung.get("explanation", "")).strip()
    options = rung.get("options")
    if not question or not explanation or not isinstance(options, list):
        return None
    clean_options = [str(opt).strip() for opt in options if str(opt).strip()]
    if len(clean_options) < 2:
        return None
    index = rung.get("correctIndex")
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    if not (0 <= index < len(clean_options)):
        return None
    return {
        "question": question,
        "options": clean_options,
        "correctIndex": index,
        "explanation": explanation,
    }


def _write_cache(
    col_path: Optional[str], note_id: int, ladder: list[dict[str, Any]]
) -> None:
    path = _cache_path(col_path)
    if not path:
        return
    try:
        data = _read_cache(col_path)
        # Drop entries written by an older version rather than mixing them with
        # current-grounding ones, and always stamp the current version.
        if data.get("version") != CACHE_VERSION:
            data = {"version": CACHE_VERSION, "ladders": {}}
        data["version"] = CACHE_VERSION
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
