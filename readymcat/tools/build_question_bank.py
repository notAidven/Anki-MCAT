#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Merge the three ReadyMCAT content banks into one canonical
``question_bank.json`` and build it into an Anki collection as a pre-loaded
multiple-choice deck.

This module is the single source of truth for the ReadyMCAT MCQ deck. It has two
jobs, and no dependency on Qt so it can be unit-tested in the lightweight
``pylib`` test environment (``anki`` is imported lazily, inside the functions
that need a live collection):

1. **Merge + validate** the section banks
   (``readymcat/content/{bio_biochem,chem_phys,psych_soc}.json``) into
   ``readymcat/content/question_bank.json`` — one canonical bank of MCAT MCQs.
   Each item has the schema::

       {id, section, aamc_category, subtopic, stem, options[4], correct_index,
        explanation, difficulty, cognitive_level, source, subquestions[]}

2. **Build** that bank into a collection: it creates a dedicated MCQ note type
   (:data:`MCQ_NOTETYPE_NAME`) with one card per note, adds one note per MCQ into
   the :data:`MCQ_DECK_NAME` deck, and tags every note by its AAMC content
   category as ``#ReadyMCAT::AAMC::<cat>``. That ``#``-prefixed tag is what
   ``taxonomy.json`` resolves to a category, so the pre-loaded deck feeds the
   points-at-stake queue, the coverage map and the honest-memory dashboard with
   zero further configuration (see :func:`taxonomy_mappings_for_categories`).

The desktop app calls :func:`provision_collection` on first launch (see
``qt/aqt/readymcat_provision.py``) so a brand-new user gets the full deck with no
import step. The pure helpers near the bottom (payload/ladder/grading) are shared
with the MCQ reviewer via ``qt/aqt/readymcat.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from anki.collection import Collection
    from anki.models import NotetypeDict

# --- canonical names / tags -------------------------------------------------

#: Note type created for pre-loaded MCQs (one card per note).
MCQ_NOTETYPE_NAME = "ReadyMCAT MCQ"
#: Single deck the pre-loaded MCQ bank is imported into.
MCQ_DECK_NAME = "ReadyMCAT"
#: A ``#``-prefixed tag namespace mapped to AAMC categories by ``taxonomy.json``.
#: Each MCQ note carries exactly one ``#ReadyMCAT::AAMC::<cat>`` tag so the
#: points-at-stake engine resolves it to its content category.
AAMC_TAG_PREFIX = "#ReadyMCAT::AAMC"
#: Coarse marker tag on every MCQ note (easy to find / manage in the Browser).
MCQ_TAG = "ReadyMCAT::MCQ"
#: Collection-config marker recording when the MCQ deck was provisioned.
PROVISION_CONFIG_KEY = "readymcat_mcq_provisioned_at"

#: The section banks merged into the canonical bank, in a stable order.
SOURCE_BANKS = ("bio_biochem.json", "chem_phys.json", "psych_soc.json")

#: Ordered fields of the MCQ note type. Index 0 (Question) is the sort field.
MCQ_FIELDS = (
    "Question",
    "OptionA",
    "OptionB",
    "OptionC",
    "OptionD",
    "CorrectIndex",
    "Explanation",
    "Subtopic",
    "Source",
    "Subquestions",
)

#: Required keys on every bank item (schema guard).
_REQUIRED_ITEM_KEYS = frozenset(
    {
        "id",
        "section",
        "aamc_category",
        "subtopic",
        "stem",
        "options",
        "correct_index",
        "explanation",
    }
)


def aamc_tag_for(category: str) -> str:
    """The ``#``-prefixed taxonomy tag for an AAMC content category."""
    return f"{AAMC_TAG_PREFIX}::{category}"


# --- merge + validate -------------------------------------------------------


def _default_content_dir() -> Path:
    # build_question_bank.py -> readymcat/tools -> readymcat -> content
    return Path(__file__).resolve().parent.parent / "content"


def validate_item(item: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems with a single bank item (empty
    when the item is well-formed)."""
    problems: list[str] = []
    missing = _REQUIRED_ITEM_KEYS - set(item.keys())
    if missing:
        problems.append(f"missing keys {sorted(missing)}")
    options = item.get("options")
    if not isinstance(options, list) or len(options) != 4:
        problems.append("options must be a list of exactly 4 choices")
    idx = item.get("correct_index")
    if not isinstance(idx, int) or not 0 <= idx <= 3:
        problems.append("correct_index must be an int in 0..3")
    subs = item.get("subquestions", [])
    if subs is not None and not isinstance(subs, list):
        problems.append("subquestions must be a list when present")
    return problems


def merge_source_banks(content_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read + concatenate the three section banks, validating each item and
    checking that ids are globally unique. Raises ``ValueError`` on any problem
    so a broken bank can never be silently shipped."""
    content_dir = content_dir or _default_content_dir()
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    problems: list[str] = []
    for name in SOURCE_BANKS:
        path = content_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing source bank: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{name}: expected a JSON array of items")
        for item in data:
            item_id = item.get("id", "<no id>")
            for problem in validate_item(item):
                problems.append(f"{name}:{item_id}: {problem}")
            if item_id in seen_ids:
                problems.append(f"{name}:{item_id}: duplicate id")
            seen_ids.add(item_id)
            items.append(item)
    if problems:
        raise ValueError(
            "question bank validation failed:\n  " + "\n  ".join(problems[:50])
        )
    return items


def build_bank_document(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap merged items in the canonical bank document (with metadata)."""
    categories = sorted({str(it["aamc_category"]) for it in items})
    sections = sorted({str(it["section"]) for it in items})
    subquestions = sum(len(it.get("subquestions") or []) for it in items)
    return {
        "version": 1,
        "description": (
            "Canonical ReadyMCAT MCQ bank: merged bio/biochem, chem/phys and "
            "psych/soc section banks. Built into the pre-loaded '"
            + MCQ_DECK_NAME
            + "' deck by readymcat/tools/build_question_bank.py; each note is "
            "tagged '#ReadyMCAT::AAMC::<category>' for the points-at-stake queue."
        ),
        "note_type": MCQ_NOTETYPE_NAME,
        "deck": MCQ_DECK_NAME,
        "count": len(items),
        "subquestion_count": subquestions,
        "sections": sections,
        "aamc_categories": categories,
        "items": items,
    }


def write_question_bank(
    content_dir: Path | None = None, out_path: Path | None = None
) -> tuple[Path, dict[str, Any]]:
    """Merge the section banks and write ``question_bank.json``. Returns the
    output path and the bank document."""
    content_dir = content_dir or _default_content_dir()
    out_path = out_path or (content_dir / "question_bank.json")
    items = merge_source_banks(content_dir)
    document = build_bank_document(items)
    out_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out_path, document


def load_bank_items(path: str | Path) -> list[dict[str, Any]]:
    """Load MCQ items from a canonical bank document *or* a bare items array."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("items", []))
    if isinstance(data, list):
        return data
    raise ValueError(f"unrecognised question bank format at {path}")


def find_question_bank() -> Path | None:
    """Locate a canonical ``question_bank.json`` (env override, repo layout,
    cwd). Returns ``None`` when none exists — callers may fall back to merging
    the section banks in memory via :func:`merge_source_banks`."""
    candidates: list[Path] = []
    env = os.environ.get("READYMCAT_QUESTION_BANK")
    if env:
        candidates.append(Path(env))
    repo_content = _default_content_dir()
    candidates.append(repo_content / "question_bank.json")
    candidates.append(Path.cwd() / "readymcat" / "content" / "question_bank.json")
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def load_bank_items_or_merge() -> list[dict[str, Any]]:
    """Best available bank: a written ``question_bank.json`` if present, else the
    three section banks merged in memory."""
    path = find_question_bank()
    if path is not None:
        return load_bank_items(path)
    return merge_source_banks()


# --- taxonomy wiring --------------------------------------------------------


def taxonomy_mappings_for_categories(categories: list[str]) -> list[dict[str, str]]:
    """The taxonomy tag-mappings that resolve each MCQ note to its AAMC category.

    A ``#ReadyMCAT::AAMC::<cat>`` tag maps to ``<cat>``; because every MCQ note
    carries exactly one such tag, resolution is unambiguous regardless of any
    other (Aidan-deck) mappings in the file."""
    return [
        {"deck_tag_or_subdeck": aamc_tag_for(cat), "category": cat}
        for cat in sorted(set(categories))
    ]


def ensure_taxonomy_mappings(taxonomy_path: str | Path, categories: list[str]) -> int:
    """Add any missing ReadyMCAT MCQ tag-mappings to ``taxonomy.json`` in place.

    Returns the number of mappings added. Idempotent: existing mappings (matched
    by ``deck_tag_or_subdeck``) are left untouched, so re-running is safe."""
    path = Path(taxonomy_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    mappings: list[dict[str, str]] = data.setdefault("mappings", [])
    present = {m.get("deck_tag_or_subdeck") for m in mappings}
    added = 0
    for mapping in taxonomy_mappings_for_categories(categories):
        if mapping["deck_tag_or_subdeck"] not in present:
            mappings.append(mapping)
            added += 1
    if added:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )
    return added


# --- note type + note building ---------------------------------------------

_CARD_CSS = """\
.card {
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 18px;
  color: var(--fg, #202020);
  background: var(--canvas, #fff);
  max-width: 760px;
  margin: 1.2em auto;
  text-align: left;
  line-height: 1.5;
}
.rmcat-stem { font-size: 1.08em; font-weight: 600; margin-bottom: .8em; }
.rmcat-options { margin: 0; padding-left: 1.4em; }
.rmcat-options li { margin: .35em 0; }
.rmcat-subtopic { margin-top: 1em; font-size: .8em; opacity: .6;
  text-transform: uppercase; letter-spacing: .04em; }
.rmcat-answer { margin-top: 1em; }
.rmcat-explanation { margin-top: .8em; }
.rmcat-source { margin-top: 1em; font-size: .82em; opacity: .7; }
"""

_FRONT_TEMPLATE = """\
<div class="rmcat-mcq" data-correct-index="{{CorrectIndex}}">
  <div class="rmcat-stem">{{Question}}</div>
  <ol class="rmcat-options" type="A">
    <li>{{OptionA}}</li>
    <li>{{OptionB}}</li>
    <li>{{OptionC}}</li>
    <li>{{OptionD}}</li>
  </ol>
  {{#Subtopic}}<div class="rmcat-subtopic">{{Subtopic}}</div>{{/Subtopic}}
</div>
"""

# The interactive reviewer highlights the chosen/correct options; this static
# back is the graceful fallback (Browser preview, exports, other clients). The
# bank's explanations describe the correct choice in prose.
_BACK_TEMPLATE = """\
{{FrontSide}}
<hr id="answer">
<div class="rmcat-answer">
  <div class="rmcat-explanation"><b>Explanation.</b> {{Explanation}}</div>
  {{#Source}}<div class="rmcat-source">Source: {{Source}}</div>{{/Source}}
</div>
"""


def ensure_notetype(col: Collection) -> NotetypeDict:
    """Return the ReadyMCAT MCQ note type, creating it if it does not exist."""
    existing = col.models.by_name(MCQ_NOTETYPE_NAME)
    if existing is not None:
        return existing
    notetype = col.models.new(MCQ_NOTETYPE_NAME)
    for field_name in MCQ_FIELDS:
        col.models.add_field(notetype, col.models.new_field(field_name))
    template = col.models.new_template("MCQ Card")
    template["qfmt"] = _FRONT_TEMPLATE
    template["afmt"] = _BACK_TEMPLATE
    col.models.add_template(notetype, template)
    notetype["css"] = _CARD_CSS
    col.models.add(notetype)
    # re-fetch so the caller gets the stored dict (with ids assigned)
    return col.models.by_name(MCQ_NOTETYPE_NAME)


def _source_text(source: Any) -> str:
    """Render a bank item's ``source`` object as a compact readable string."""
    if isinstance(source, dict):
        name = str(source.get("name", "")).strip()
        url = str(source.get("url", "")).strip()
        if name and url:
            return f"{name} ({url})"
        return name or url
    return str(source or "")


def _fields_for_item(item: dict[str, Any]) -> list[str]:
    """Map a bank item onto the ordered MCQ note fields."""
    options = list(item.get("options", []))
    options += [""] * (4 - len(options))
    return [
        str(item.get("stem", "")),
        str(options[0]),
        str(options[1]),
        str(options[2]),
        str(options[3]),
        str(int(item.get("correct_index", 0))),
        str(item.get("explanation", "")),
        str(item.get("subtopic", "")),
        _source_text(item.get("source")),
        json.dumps(item.get("subquestions") or [], ensure_ascii=False),
    ]


@dataclass
class BuildStats:
    """Summary of a build/provision run."""

    already_present: bool = False
    notes_created: int = 0
    cards_created: int = 0
    categories: list[str] = field(default_factory=list)
    subquestions: int = 0
    deck_name: str = MCQ_DECK_NAME
    notetype_name: str = MCQ_NOTETYPE_NAME

    def as_dict(self) -> dict[str, Any]:
        return {
            "already_present": self.already_present,
            "notes_created": self.notes_created,
            "cards_created": self.cards_created,
            "categories": self.categories,
            "subquestions": self.subquestions,
            "deck_name": self.deck_name,
            "notetype_name": self.notetype_name,
        }


def has_mcq_deck(col: Collection) -> bool:
    """True once the pre-loaded MCQ deck exists (the first-launch guard)."""
    try:
        return col.decks.by_name(MCQ_DECK_NAME) is not None
    except Exception:
        return False


def build_notes(
    col: Collection,
    items: list[dict[str, Any]],
    *,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Create the MCQ note type + deck and add one note per item, tagged by its
    AAMC category. Returns what was created. Not idempotent on its own — callers
    use :func:`provision_collection` for the first-launch guard."""
    stats = BuildStats()
    notetype = ensure_notetype(col)
    deck_id = col.decks.id(MCQ_DECK_NAME)
    categories: set[str] = set()

    for item in items:
        category = str(item.get("aamc_category", "")).strip()
        note = col.new_note(notetype)
        note.fields = _fields_for_item(item)
        note.add_tag(MCQ_TAG)
        if category:
            note.add_tag(aamc_tag_for(category))
            categories.add(category)
        section = str(item.get("section", "")).strip()
        if section:
            note.add_tag(f"{MCQ_TAG}::{section.replace('/', '-')}")
        col.add_note(note, deck_id)
        stats.notes_created += 1
        stats.cards_created += len(note.cards())
        stats.subquestions += len(item.get("subquestions") or [])

    stats.categories = sorted(categories)
    log(
        f"ReadyMCAT: built {stats.notes_created} MCQ notes "
        f"({stats.cards_created} cards) across {len(stats.categories)} AAMC "
        f"categories into deck '{MCQ_DECK_NAME}'."
    )
    return stats


def provision_collection(
    col: Collection,
    *,
    bank_items: list[dict[str, Any]] | None = None,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Idempotently ensure the pre-loaded MCQ deck exists in ``col``.

    If the deck is already present, this is a no-op. Otherwise it builds every
    MCQ from the bank (``bank_items`` or the best bank found on disk) and records
    a config marker. This is what the desktop app runs on first launch so a new
    user gets the full deck with zero import."""
    if has_mcq_deck(col):
        stats = BuildStats(already_present=True)
        stats.notes_created = len(col.find_notes(f'"note:{MCQ_NOTETYPE_NAME}"'))
        log(
            f"ReadyMCAT: MCQ deck '{MCQ_DECK_NAME}' already present "
            f"({stats.notes_created} notes); skipping provisioning."
        )
        return stats

    items = bank_items if bank_items is not None else load_bank_items_or_merge()
    stats = build_notes(col, items, log=log)
    try:
        import time

        col.set_config(PROVISION_CONFIG_KEY, int(time.time()))
    except Exception:  # pragma: no cover - defensive
        pass
    return stats


# --- pure MCQ reviewer helpers (shared with qt/aqt/readymcat.py) ------------
#
# These are intentionally free of Anki/Qt so the MCQ grading + per-question
# teach-on-miss logic can be unit-tested directly.

#: FSRS grade mapping (documented in readymcat/README.md): a first-attempt hit
#: is Good; anything that required the teach-on-miss ladder grades Again so the
#: corrected concept re-enters relearning (spaced re-retrieval).
EASE_AGAIN = 1
EASE_GOOD = 3

#: Outcomes reported by the MCQ reviewer flow.
OUTCOME_CORRECT_FIRST = "correct_first"
OUTCOME_CORRECT_AFTER = "correct_after"
OUTCOME_WRONG = "wrong"


def ease_for_mcq_outcome(outcome: str) -> int:
    """Map an MCQ outcome to an FSRS ease. Correct on the first try -> Good;
    correct only after the ladder, or still wrong -> Again (not mastered)."""
    return EASE_GOOD if outcome == OUTCOME_CORRECT_FIRST else EASE_AGAIN


def outcome_is_struggling(outcome: str) -> bool:
    """Whether an outcome flags the concept as struggling (missed again after
    the full teach-on-miss ladder)."""
    return outcome == OUTCOME_WRONG


def parse_subquestions(raw: str | None) -> list[dict[str, Any]]:
    """Parse the note's ``Subquestions`` JSON field into a clean ladder.

    Each rung is normalised to ``{stem, options[4], correct_index, explanation}``
    and malformed rungs are dropped, so the reviewer never crashes on bad data
    (it simply runs a shorter — or empty — ladder)."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    rungs: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        options = entry.get("options")
        if not isinstance(options, list) or len(options) != 4:
            continue
        idx = entry.get("correct_index")
        if not isinstance(idx, int) or not 0 <= idx <= 3:
            continue
        stem = str(entry.get("stem", "")).strip()
        if not stem:
            continue
        rungs.append(
            {
                "stem": stem,
                "options": [str(o) for o in options],
                "correct_index": idx,
                "explanation": str(entry.get("explanation", "")),
            }
        )
    return rungs


def mcq_payload_from_fields(fields: dict[str, str]) -> dict[str, Any]:
    """Build the reviewer payload (sent to ``_mcqStart``) from a note's fields.

    Kept pure so the reviewer's data contract is testable without a webview."""
    try:
        correct_index = int(str(fields.get("CorrectIndex", "0")).strip() or "0")
    except ValueError:
        correct_index = 0
    correct_index = max(0, min(3, correct_index))
    return {
        "question": fields.get("Question", ""),
        "options": [
            fields.get("OptionA", ""),
            fields.get("OptionB", ""),
            fields.get("OptionC", ""),
            fields.get("OptionD", ""),
        ],
        "correctIndex": correct_index,
        "explanation": fields.get("Explanation", ""),
        "subtopic": fields.get("Subtopic", ""),
        "source": fields.get("Source", ""),
        "subquestions": parse_subquestions(fields.get("Subquestions", "")),
    }


# --- standalone CLI ---------------------------------------------------------


def _ensure_anki_importable() -> None:
    try:
        import anki  # noqa: F401

        return
    except Exception:
        pass
    repo_root = Path(__file__).resolve().parents[2]
    for rel in ("pylib", "out/pylib"):
        candidate = repo_root / rel
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge the ReadyMCAT section banks into question_bank.json and "
            "optionally build the pre-loaded MCQ deck into a collection."
        )
    )
    parser.add_argument(
        "--write-bank",
        action="store_true",
        help="(re)generate readymcat/content/question_bank.json from the banks",
    )
    parser.add_argument(
        "--sync-taxonomy",
        metavar="TAXONOMY_JSON",
        help="add the #ReadyMCAT::AAMC::<cat> mappings to this taxonomy.json",
    )
    parser.add_argument(
        "--collection", help="build the deck into this collection.anki2 path"
    )
    args = parser.parse_args(argv)

    if args.write_bank or not (args.collection or args.sync_taxonomy):
        out_path, document = write_question_bank()
        print(
            f"Wrote {out_path} — {document['count']} MCQs, "
            f"{document['subquestion_count']} sub-questions, "
            f"{len(document['aamc_categories'])} AAMC categories."
        )

    if args.sync_taxonomy:
        items = load_bank_items_or_merge()
        categories = sorted({str(it["aamc_category"]) for it in items})
        added = ensure_taxonomy_mappings(args.sync_taxonomy, categories)
        print(f"Added {added} ReadyMCAT MCQ mapping(s) to {args.sync_taxonomy}.")

    if args.collection:
        _ensure_anki_importable()
        from anki.collection import Collection

        col = Collection(str(Path(args.collection).expanduser()))
        try:
            stats = provision_collection(col)
        finally:
            col.close()
        print(json.dumps(stats.as_dict(), indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
