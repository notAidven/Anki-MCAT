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
import hashlib
import json
import os
import re
import sys
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

# --- free-response + passage content types ---------------------------------
#
# Alongside the MCQ deck, a brand-new user is pre-loaded with two more content
# types so *every* AAMC-tagged item feeds the same points-at-stake queue,
# coverage map and honest dashboard with zero import:
#
# * **Free response** — a type-in prompt auto-graded by the reviewer against
#   ``accepted_answers`` / ``key_terms`` (normalised string + numeric tolerance).
# * **Passage** — a shared passage with one card per question (MCQ interaction),
#   the passage's questions grouped together in the deck.
#
# The AAMC content types live in sub-decks of the pre-loaded ``ReadyMCAT`` deck
# and are tagged the same ``#ReadyMCAT::AAMC::<cat>`` way as the MCQs. CARS is a
# fourth, special content type: it is the MCAT's *skills* section, has no AAMC
# content category, and so is built into its own ``ReadyMCAT::Passages::CARS``
# sub-deck and tagged :data:`CARS_TAG` (no AAMC tag) so it is cleanly ignored by
# the points-at-stake queue / coverage map / dashboard — see the CARS section.

#: Note type for pre-loaded free-response items (one type-in card per note).
FR_NOTETYPE_NAME = "ReadyMCAT FreeResponse"
#: Sub-deck the free-response bank is imported into.
FR_DECK_NAME = f"{MCQ_DECK_NAME}::Free Response"
#: Coarse marker tag on every free-response note.
FR_TAG = "ReadyMCAT::FreeResponse"
#: Collection-config marker recording when the FR deck was provisioned.
FR_PROVISION_CONFIG_KEY = "readymcat_fr_provisioned_at"
#: Ordered fields of the FR note type. Index 0 (Prompt) is the sort field.
FR_FIELDS = (
    "Prompt",
    "AcceptedAnswers",
    "KeyTerms",
    "ModelAnswer",
    "Explanation",
    "Subtopic",
    "Source",
    "Subquestions",
)
#: The free-response section banks, in a stable order.
FR_SOURCE_BANKS = (
    "free_response_bio_biochem.json",
    "free_response_chem_phys.json",
    "free_response_psych_soc.json",
)
#: Required keys on every free-response item (schema guard).
_FR_REQUIRED_ITEM_KEYS = frozenset(
    {"id", "section", "aamc_category", "prompt", "accepted_answers", "explanation"}
)

#: Note type for pre-loaded passage items (one card per passage question).
PASSAGE_NOTETYPE_NAME = "ReadyMCAT Passage"
#: Sub-deck the passage bank is imported into.
PASSAGE_DECK_NAME = f"{MCQ_DECK_NAME}::Passages"
#: Coarse marker tag on every passage note.
PASSAGE_TAG = "ReadyMCAT::Passage"
#: Collection-config marker recording when the passage deck was provisioned.
PASSAGE_PROVISION_CONFIG_KEY = "readymcat_passage_provisioned_at"
#: Ordered fields of the passage note type. Index 0 (Passage) is the sort field
#: so a passage's questions group together in the Browser.
PASSAGE_FIELDS = (
    "Passage",
    "PassageId",
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
#: The passage section banks, in a stable order.
PASSAGE_SOURCE_BANKS = (
    "passage_bio_biochem.json",
    "passage_chem_phys.json",
    "passage_psych_soc.json",
)
#: AAMC category used for CARS passage items (which have no numbered category).
CARS_CATEGORY = "CARS"

# --- CARS: the skills-section passage bank ----------------------------------
#
# CARS (Critical Analysis and Reasoning Skills) is folded in as a fourth
# pre-loaded content type. Its questions carry a ``skill`` (comprehension /
# reasoning-within / reasoning-beyond) instead of a numbered AAMC content
# category, so it is deliberately kept OUT of :func:`merge_passage_source_banks`
# and :func:`all_content_categories`. It reuses the ``ReadyMCAT Passage`` note
# type but lands in its own sub-deck with its own marker tag.

#: The CARS passage bank(s), in a stable order.
CARS_PASSAGE_SOURCE_BANKS = ("passage_cars.json",)
#: Sub-deck the CARS passages are imported into (a child of the Passages deck).
CARS_PASSAGE_DECK_NAME = f"{PASSAGE_DECK_NAME}::CARS"
#: Marker tag on every CARS passage note. Deliberately NOT a
#: ``#ReadyMCAT::AAMC::<cat>`` tag: CARS has no content category, and because no
#: ``taxonomy.json`` mapping resolves ``#ReadyMCAT::CARS``, the points-at-stake
#: queue, coverage map and honest dashboard cleanly IGNORE CARS cards.
CARS_TAG = "#ReadyMCAT::CARS"
#: Collection-config marker recording when the CARS deck was last provisioned.
CARS_PROVISION_CONFIG_KEY = "readymcat_cars_provisioned_at"


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


class BuildStats:
    """Summary of a build/provision run.

    A plain class (not a ``@dataclass``) so it loads cleanly when this module is
    imported by path — mirroring ``seed_demo_dashboard.DemoStats``."""

    def __init__(
        self,
        deck_name: str = MCQ_DECK_NAME,
        notetype_name: str = MCQ_NOTETYPE_NAME,
    ) -> None:
        self.already_present = False
        self.notes_created = 0
        self.cards_created = 0
        self.categories: list[str] = []
        self.subquestions = 0
        self.deck_name = deck_name
        self.notetype_name = notetype_name

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
        stats = BuildStats()
        stats.already_present = True
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


def _parse_choice_ladder(
    raw: str | None, *, min_options: int, exact: bool
) -> list[dict[str, Any]]:
    """Shared parser behind :func:`parse_subquestions` and
    :func:`parse_passage_subquestions`.

    Each rung is normalised to ``{stem, options, correct_index, explanation}``.
    A rung needs at least ``min_options`` options — and *exactly* that many when
    ``exact`` (the discrete-MCQ case of four); otherwise more are allowed (AAMC
    passage ladders use four, CARS guiding ladders two or three). Malformed rungs
    (no stem, too few options, or an out-of-range answer) are dropped so the
    reviewer runs a shorter — or empty — ladder rather than crashing on bad data.
    """
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
        if not isinstance(options, list) or len(options) < min_options:
            continue
        if exact and len(options) != min_options:
            continue
        idx = entry.get("correct_index")
        if not isinstance(idx, int) or not 0 <= idx < len(options):
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


def parse_subquestions(raw: str | None) -> list[dict[str, Any]]:
    """Parse the note's ``Subquestions`` JSON field into a clean ladder.

    Each rung is normalised to ``{stem, options[4], correct_index, explanation}``
    and malformed rungs are dropped, so the reviewer never crashes on bad data
    (it simply runs a shorter — or empty — ladder)."""
    return _parse_choice_ladder(raw, min_options=4, exact=True)


def parse_passage_subquestions(raw: str | None) -> list[dict[str, Any]]:
    """Parse a passage note's ``Subquestions`` JSON into a guiding ladder.

    Like :func:`parse_subquestions`, but accepts a *variable* number of options
    per rung (>= 2 rather than exactly 4): AAMC passage ladders use four options,
    while CARS guiding ladders use two or three."""
    return _parse_choice_ladder(raw, min_options=2, exact=False)


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


# --- free-response: merge + validate ---------------------------------------


def validate_fr_item(item: dict[str, Any]) -> list[str]:
    """Return human-readable problems with a single free-response item."""
    problems: list[str] = []
    missing = _FR_REQUIRED_ITEM_KEYS - set(item.keys())
    if missing:
        problems.append(f"missing keys {sorted(missing)}")
    accepted = item.get("accepted_answers")
    if not isinstance(accepted, list) or not accepted:
        problems.append("accepted_answers must be a non-empty list")
    key_terms = item.get("key_terms", [])
    if key_terms is not None and not isinstance(key_terms, list):
        problems.append("key_terms must be a list when present")
    subs = item.get("subquestions", [])
    if subs is not None and not isinstance(subs, list):
        problems.append("subquestions must be a list when present")
    return problems


def merge_fr_source_banks(content_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read + concatenate the three free-response section banks, validating each
    item and checking that ids are globally unique. Raises ``ValueError`` on any
    problem so a broken bank can never be silently shipped."""
    content_dir = content_dir or _default_content_dir()
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    problems: list[str] = []
    for name in FR_SOURCE_BANKS:
        path = content_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing free-response bank: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{name}: expected a JSON array of items")
        for item in data:
            item_id = item.get("id", "<no id>")
            for problem in validate_fr_item(item):
                problems.append(f"{name}:{item_id}: {problem}")
            if item_id in seen_ids:
                problems.append(f"{name}:{item_id}: duplicate id")
            seen_ids.add(item_id)
            items.append(item)
    if problems:
        raise ValueError(
            "free-response bank validation failed:\n  " + "\n  ".join(problems[:50])
        )
    return items


# --- passage: merge + validate ---------------------------------------------


def validate_passage(passage: dict[str, Any]) -> list[str]:
    """Return human-readable problems with a single passage set (empty when the
    passage and all of its questions are well-formed)."""
    problems: list[str] = []
    if not str(passage.get("passage", "")).strip():
        problems.append("missing passage text")
    questions = passage.get("questions")
    if not isinstance(questions, list) or not questions:
        problems.append("questions must be a non-empty list")
        return problems
    for question in questions:
        qid = question.get("id", "<no qid>")
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            problems.append(f"{qid}: options must be a list of exactly 4 choices")
        idx = question.get("correct_index")
        if not isinstance(idx, int) or not 0 <= idx <= 3:
            problems.append(f"{qid}: correct_index must be an int in 0..3")
        if not str(question.get("stem", "")).strip():
            problems.append(f"{qid}: missing stem")
        subs = question.get("subquestions", [])
        if subs is not None and not isinstance(subs, list):
            problems.append(f"{qid}: subquestions must be a list when present")
    return problems


def _merge_passage_banks(
    banks: tuple[str, ...],
    content_dir: Path | None = None,
    *,
    kind: str = "passage",
) -> list[dict[str, Any]]:
    """Read + concatenate a set of passage banks, validating each passage (and
    its questions) and checking that both passage ids and question ids are
    globally unique. Shared by the AAMC passage banks and the CARS bank."""
    content_dir = content_dir or _default_content_dir()
    passages: list[dict[str, Any]] = []
    seen_pids: set[str] = set()
    seen_qids: set[str] = set()
    problems: list[str] = []
    for name in banks:
        path = content_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing {kind} bank: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{name}: expected a JSON array of passages")
        for passage in data:
            pid = passage.get("id", "<no id>")
            for problem in validate_passage(passage):
                problems.append(f"{name}:{pid}: {problem}")
            if pid in seen_pids:
                problems.append(f"{name}:{pid}: duplicate passage id")
            seen_pids.add(pid)
            for question in passage.get("questions") or []:
                qid = question.get("id", "<no qid>")
                if qid in seen_qids:
                    problems.append(f"{name}:{qid}: duplicate question id")
                seen_qids.add(qid)
            passages.append(passage)
    if problems:
        raise ValueError(
            f"{kind} bank validation failed:\n  " + "\n  ".join(problems[:50])
        )
    return passages


def merge_passage_source_banks(
    content_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Read + concatenate the three AAMC passage section banks (bio/biochem,
    chem/phys, psych/soc), validating each passage and checking that ids are
    globally unique. CARS is a separate bank — see
    :func:`merge_cars_passage_banks`."""
    return _merge_passage_banks(PASSAGE_SOURCE_BANKS, content_dir)


def merge_cars_passage_banks(
    content_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Read + validate the CARS passage bank. CARS questions carry a ``skill``
    and no numbered AAMC category; :func:`validate_passage` does not require a
    category, so it validates CARS unchanged."""
    return _merge_passage_banks(
        CARS_PASSAGE_SOURCE_BANKS, content_dir, kind="CARS passage"
    )


def passage_question_count(passages: list[dict[str, Any]]) -> int:
    """Total number of questions (= cards) across all passages."""
    return sum(len(p.get("questions") or []) for p in passages)


def _passage_question_category(
    passage: dict[str, Any], question: dict[str, Any]
) -> str:
    """The AAMC category for a passage question; CARS passages (which carry no
    numbered category) fall back to :data:`CARS_CATEGORY`."""
    category = str(question.get("aamc_category", "")).strip()
    if category:
        return category
    if str(passage.get("section", "")).strip().upper() == "CARS":
        return CARS_CATEGORY
    return ""


# --- free-response: note type + note building ------------------------------

_FR_CARD_CSS = (
    _CARD_CSS
    + """
.rmcat-prompt { font-size: 1.08em; font-weight: 600; margin-bottom: .6em; }
.rmcat-typein { font-size: .82em; opacity: .6; text-transform: uppercase;
  letter-spacing: .04em; margin-top: .6em; }
.rmcat-model { margin-top: .8em; }
"""
)

_FR_FRONT_TEMPLATE = """\
<div class="rmcat-fr">
  <div class="rmcat-prompt">{{Prompt}}</div>
  {{#Subtopic}}<div class="rmcat-subtopic">{{Subtopic}}</div>{{/Subtopic}}
  <div class="rmcat-typein">Type your answer</div>
</div>
"""

# Static fallback back (the interactive reviewer auto-grades a typed answer).
_FR_BACK_TEMPLATE = """\
{{FrontSide}}
<hr id="answer">
<div class="rmcat-answer">
  {{#ModelAnswer}}<div class="rmcat-model"><b>Model answer.</b> {{ModelAnswer}}</div>{{/ModelAnswer}}
  <div class="rmcat-explanation"><b>Explanation.</b> {{Explanation}}</div>
  {{#Source}}<div class="rmcat-source">Source: {{Source}}</div>{{/Source}}
</div>
"""


def ensure_fr_notetype(col: Collection) -> NotetypeDict:
    """Return the ReadyMCAT free-response note type, creating it if absent."""
    existing = col.models.by_name(FR_NOTETYPE_NAME)
    if existing is not None:
        return existing
    notetype = col.models.new(FR_NOTETYPE_NAME)
    for field_name in FR_FIELDS:
        col.models.add_field(notetype, col.models.new_field(field_name))
    template = col.models.new_template("FreeResponse Card")
    template["qfmt"] = _FR_FRONT_TEMPLATE
    template["afmt"] = _FR_BACK_TEMPLATE
    col.models.add_template(notetype, template)
    notetype["css"] = _FR_CARD_CSS
    col.models.add(notetype)
    return col.models.by_name(FR_NOTETYPE_NAME)


def _fr_fields_for_item(item: dict[str, Any]) -> list[str]:
    """Map a free-response bank item onto the ordered FR note fields."""
    return [
        str(item.get("prompt", "")),
        json.dumps(item.get("accepted_answers") or [], ensure_ascii=False),
        json.dumps(item.get("key_terms") or [], ensure_ascii=False),
        str(item.get("model_answer", "")),
        str(item.get("explanation", "")),
        str(item.get("subtopic", "")),
        _source_text(item.get("source")),
        json.dumps(item.get("subquestions") or [], ensure_ascii=False),
    ]


def build_fr_notes(
    col: Collection,
    items: list[dict[str, Any]],
    *,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Create the free-response note type + sub-deck and add one note per item,
    tagged by its AAMC category. Mirrors :func:`build_notes` for MCQs."""
    stats = BuildStats(deck_name=FR_DECK_NAME, notetype_name=FR_NOTETYPE_NAME)
    notetype = ensure_fr_notetype(col)
    deck_id = col.decks.id(FR_DECK_NAME)
    categories: set[str] = set()

    for item in items:
        category = str(item.get("aamc_category", "")).strip()
        note = col.new_note(notetype)
        note.fields = _fr_fields_for_item(item)
        note.add_tag(FR_TAG)
        if category:
            note.add_tag(aamc_tag_for(category))
            categories.add(category)
        section = str(item.get("section", "")).strip()
        if section:
            note.add_tag(f"{FR_TAG}::{section.replace('/', '-')}")
        col.add_note(note, deck_id)
        stats.notes_created += 1
        stats.cards_created += len(note.cards())
        stats.subquestions += len(item.get("subquestions") or [])

    stats.categories = sorted(categories)
    log(
        f"ReadyMCAT: built {stats.notes_created} free-response notes "
        f"({stats.cards_created} cards) across {len(stats.categories)} AAMC "
        f"categories into deck '{FR_DECK_NAME}'."
    )
    return stats


# --- passage: note type + note building ------------------------------------

_PASSAGE_CARD_CSS = (
    _CARD_CSS
    + """
.rmcat-passage { border-left: 3px solid var(--accent, #2186eb); padding-left: 1em;
  margin-bottom: 1em; white-space: pre-wrap; font-size: .96em; }
.rmcat-question { font-size: 1.06em; font-weight: 600; margin: .8em 0 .4em; }
"""
)

_PASSAGE_FRONT_TEMPLATE = """\
<div class="rmcat-passage-card" data-correct-index="{{CorrectIndex}}"
     data-passage-id="{{PassageId}}">
  <div class="rmcat-passage">{{Passage}}</div>
  <div class="rmcat-question">{{Question}}</div>
  <ol class="rmcat-options" type="A">
    <li>{{OptionA}}</li>
    <li>{{OptionB}}</li>
    <li>{{OptionC}}</li>
    <li>{{OptionD}}</li>
  </ol>
  {{#Subtopic}}<div class="rmcat-subtopic">{{Subtopic}}</div>{{/Subtopic}}
</div>
"""

_PASSAGE_BACK_TEMPLATE = """\
{{FrontSide}}
<hr id="answer">
<div class="rmcat-answer">
  <div class="rmcat-explanation"><b>Explanation.</b> {{Explanation}}</div>
  {{#Source}}<div class="rmcat-source">Source: {{Source}}</div>{{/Source}}
</div>
"""


def ensure_passage_notetype(col: Collection) -> NotetypeDict:
    """Return the ReadyMCAT passage note type, creating it if absent."""
    existing = col.models.by_name(PASSAGE_NOTETYPE_NAME)
    if existing is not None:
        return existing
    notetype = col.models.new(PASSAGE_NOTETYPE_NAME)
    for field_name in PASSAGE_FIELDS:
        col.models.add_field(notetype, col.models.new_field(field_name))
    template = col.models.new_template("Passage Card")
    template["qfmt"] = _PASSAGE_FRONT_TEMPLATE
    template["afmt"] = _PASSAGE_BACK_TEMPLATE
    col.models.add_template(notetype, template)
    notetype["css"] = _PASSAGE_CARD_CSS
    col.models.add(notetype)
    return col.models.by_name(PASSAGE_NOTETYPE_NAME)


def _passage_fields_for_question(
    passage: dict[str, Any], question: dict[str, Any]
) -> list[str]:
    """Map a passage + one of its questions onto the ordered passage fields."""
    options = list(question.get("options", []))
    options += [""] * (4 - len(options))
    source = passage.get("passage_source") or question.get("source")
    return [
        str(passage.get("passage", "")),
        str(passage.get("id", "")),
        str(question.get("stem", "")),
        str(options[0]),
        str(options[1]),
        str(options[2]),
        str(options[3]),
        str(int(question.get("correct_index", 0))),
        str(question.get("explanation", "")),
        str(question.get("subtopic", "")),
        _source_text(source),
        json.dumps(question.get("subquestions") or [], ensure_ascii=False),
    ]


def build_passage_notes(
    col: Collection,
    passages: list[dict[str, Any]],
    *,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Create the passage note type + sub-deck and add one note per question,
    tagged by that question's AAMC category. A passage's questions are added
    consecutively so they stay grouped together in the deck."""
    stats = BuildStats(deck_name=PASSAGE_DECK_NAME, notetype_name=PASSAGE_NOTETYPE_NAME)
    notetype = ensure_passage_notetype(col)
    deck_id = col.decks.id(PASSAGE_DECK_NAME)
    categories: set[str] = set()

    for passage in passages:
        section = str(passage.get("section", "")).strip()
        for question in passage.get("questions") or []:
            category = _passage_question_category(passage, question)
            note = col.new_note(notetype)
            note.fields = _passage_fields_for_question(passage, question)
            note.add_tag(PASSAGE_TAG)
            if category:
                note.add_tag(aamc_tag_for(category))
                categories.add(category)
            if section:
                note.add_tag(f"{PASSAGE_TAG}::{section.replace('/', '-')}")
            col.add_note(note, deck_id)
            stats.notes_created += 1
            stats.cards_created += len(note.cards())
            stats.subquestions += len(question.get("subquestions") or [])

    stats.categories = sorted(categories)
    log(
        f"ReadyMCAT: built {stats.notes_created} passage notes "
        f"({stats.cards_created} cards) across {len(stats.categories)} AAMC "
        f"categories into deck '{PASSAGE_DECK_NAME}'."
    )
    return stats


# --- CARS: note building (stable-guid, add-missing) -------------------------


def _existing_guids(col: Collection) -> set[str]:
    """Every note guid currently in the collection (for stable-key add-missing)."""
    try:
        return set(col.db.list("select guid from notes"))
    except Exception:  # pragma: no cover - defensive
        return set()


def cars_note_guid(question_id: str) -> str:
    """A deterministic, stable Anki note guid for a CARS passage question.

    Deriving the guid from the globally-unique question id lets provisioning add
    only the CARS notes that are missing, so a profile provisioned *before* CARS
    existed gains exactly the new CARS cards on next launch and relaunches never
    duplicate them."""
    digest = hashlib.sha256(f"readymcat-cars:{question_id}".encode("utf-8")).hexdigest()
    return f"rmcat-cars-{digest[:16]}"


def _cars_passage_fields_for_question(
    passage: dict[str, Any], question: dict[str, Any]
) -> list[str]:
    """Fields for a CARS passage question. Identical to the AAMC mapping, except
    the Subtopic slot carries the CARS ``skill`` (comprehension /
    reasoning-within / reasoning-beyond) when there is no subtopic — CARS has no
    AAMC subtopic, and this is what the reviewer surfaces so a CARS card renders
    its skill instead."""
    fields = _passage_fields_for_question(passage, question)
    subtopic_idx = PASSAGE_FIELDS.index("Subtopic")
    skill = str(question.get("skill", "")).strip()
    if skill and not fields[subtopic_idx]:
        fields[subtopic_idx] = skill
    return fields


def build_cars_passage_notes(
    col: Collection,
    passages: list[dict[str, Any]],
    *,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Build the CARS passages into the ``ReadyMCAT::Passages::CARS`` sub-deck.

    Reuses the shared :data:`PASSAGE_NOTETYPE_NAME` note type but tags each note
    with the coarse passage marker + :data:`CARS_TAG` (and NO AAMC category tag),
    and gives each note a deterministic guid (:func:`cars_note_guid`). Only notes
    whose stable guid is not already present are added, so this is safe to call
    on a fresh OR an already-provisioned profile without creating duplicates."""
    stats = BuildStats(
        deck_name=CARS_PASSAGE_DECK_NAME, notetype_name=PASSAGE_NOTETYPE_NAME
    )
    notetype = ensure_passage_notetype(col)
    deck_id = col.decks.id(CARS_PASSAGE_DECK_NAME)
    existing = _existing_guids(col)

    for passage in passages:
        for question in passage.get("questions") or []:
            guid = cars_note_guid(str(question.get("id", "")))
            if guid in existing:
                continue
            note = col.new_note(notetype)
            note.guid = guid
            note.fields = _cars_passage_fields_for_question(passage, question)
            note.add_tag(PASSAGE_TAG)
            note.add_tag(CARS_TAG)
            col.add_note(note, deck_id)
            existing.add(guid)
            stats.notes_created += 1
            stats.cards_created += len(note.cards())
            stats.subquestions += len(question.get("subquestions") or [])

    # CARS has no AAMC category by design, so `categories` stays empty.
    if stats.notes_created:
        log(
            f"ReadyMCAT: built {stats.notes_created} CARS passage notes "
            f"({stats.cards_created} cards) into deck '{CARS_PASSAGE_DECK_NAME}'."
        )
    return stats


# --- provisioning: free-response + passage + everything --------------------


def has_fr_notes(col: Collection) -> bool:
    """True once any free-response note exists (the first-launch guard)."""
    try:
        return len(col.find_notes(f'"note:{FR_NOTETYPE_NAME}"')) > 0
    except Exception:
        return False


def has_passage_notes(col: Collection) -> bool:
    """True once any passage note exists (the first-launch guard)."""
    try:
        return len(col.find_notes(f'"note:{PASSAGE_NOTETYPE_NAME}"')) > 0
    except Exception:
        return False


def provision_free_response(
    col: Collection,
    *,
    items: list[dict[str, Any]] | None = None,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Idempotently ensure the pre-loaded free-response deck exists in ``col``."""
    if has_fr_notes(col):
        stats = BuildStats(deck_name=FR_DECK_NAME, notetype_name=FR_NOTETYPE_NAME)
        stats.already_present = True
        stats.notes_created = len(col.find_notes(f'"note:{FR_NOTETYPE_NAME}"'))
        log(
            f"ReadyMCAT: free-response deck already present "
            f"({stats.notes_created} notes); skipping."
        )
        return stats
    items = items if items is not None else merge_fr_source_banks()
    stats = build_fr_notes(col, items, log=log)
    try:
        import time

        col.set_config(FR_PROVISION_CONFIG_KEY, int(time.time()))
    except Exception:  # pragma: no cover - defensive
        pass
    return stats


def provision_passages(
    col: Collection,
    *,
    passages: list[dict[str, Any]] | None = None,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Idempotently ensure the pre-loaded passage deck exists in ``col``."""
    if has_passage_notes(col):
        stats = BuildStats(
            deck_name=PASSAGE_DECK_NAME, notetype_name=PASSAGE_NOTETYPE_NAME
        )
        stats.already_present = True
        stats.notes_created = len(col.find_notes(f'"note:{PASSAGE_NOTETYPE_NAME}"'))
        log(
            f"ReadyMCAT: passage deck already present "
            f"({stats.notes_created} notes); skipping."
        )
        return stats
    passages = passages if passages is not None else merge_passage_source_banks()
    stats = build_passage_notes(col, passages, log=log)
    try:
        import time

        col.set_config(PASSAGE_PROVISION_CONFIG_KEY, int(time.time()))
    except Exception:  # pragma: no cover - defensive
        pass
    return stats


def cars_notes_missing(
    col: Collection, passages: list[dict[str, Any]] | None = None
) -> int:
    """How many bundled CARS notes are not yet in the collection (0 = complete).

    This is the precise, per-note guard behind CARS top-up: it does not care
    whether the CARS deck exists, only whether every CARS note (by stable guid)
    is present. Defensive — returns 0 on any error so start-up is never blocked."""
    try:
        passages = passages if passages is not None else merge_cars_passage_banks()
        existing = _existing_guids(col)
        missing = 0
        for passage in passages:
            for question in passage.get("questions") or []:
                if cars_note_guid(str(question.get("id", ""))) not in existing:
                    missing += 1
        return missing
    except Exception:  # pragma: no cover - defensive
        return 0


def has_all_cars_notes(col: Collection) -> bool:
    """True once every bundled CARS note is present (the top-up guard)."""
    return cars_notes_missing(col) == 0


def provision_cars_passages(
    col: Collection,
    *,
    passages: list[dict[str, Any]] | None = None,
    log: Callable[[str], None] = print,
) -> BuildStats:
    """Idempotently ensure the pre-loaded CARS passage deck exists in ``col``.

    Unlike the AAMC content decks (guarded by mere deck/notes existence), CARS is
    added by stable per-note guid: only missing CARS notes are created. So a
    profile provisioned *before* CARS existed gains exactly the CARS cards on the
    next launch, and relaunching never duplicates them. ``already_present`` is
    reported when there was nothing to add."""
    passages = passages if passages is not None else merge_cars_passage_banks()
    stats = build_cars_passage_notes(col, passages, log=log)
    if stats.notes_created == 0:
        stats.already_present = True
        try:
            stats.notes_created = len(
                col.find_notes(f'deck:"{CARS_PASSAGE_DECK_NAME}"')
            )
        except Exception:  # pragma: no cover - defensive
            pass
        log(
            f"ReadyMCAT: CARS passage deck already complete "
            f"({stats.notes_created} notes); skipping."
        )
        return stats
    try:
        import time

        col.set_config(CARS_PROVISION_CONFIG_KEY, int(time.time()))
    except Exception:  # pragma: no cover - defensive
        pass
    return stats


def provision_all(
    col: Collection,
    *,
    log: Callable[[str], None] = print,
) -> dict[str, BuildStats]:
    """Idempotently pre-load ALL content types (MCQ + free-response + passage +
    CARS).

    Each content type is independently guarded, so a brand-new user gets the
    full mixed deck with zero import and re-running never duplicates anything.
    MCQ is provisioned first so its deck-existence guard is checked before the
    sub-decks create the shared ``ReadyMCAT`` parent. CARS is provisioned by
    stable per-note guid (add-missing), so it is also topped up on a profile that
    was provisioned before CARS existed — without duplicating existing cards."""
    return {
        "mcq": provision_collection(col, log=log),
        "free_response": provision_free_response(col, log=log),
        "passage": provision_passages(col, log=log),
        "cars": provision_cars_passages(col, log=log),
    }


def all_content_categories(content_dir: Path | None = None) -> list[str]:
    """Sorted union of every AAMC category across MCQ, free-response and passage
    banks. Used to keep ``taxonomy.json`` mappings complete so every pre-loaded
    card (regardless of content type) resolves to its category."""
    content_dir = content_dir or _default_content_dir()
    categories: set[str] = set()
    try:
        for item in load_bank_items_or_merge():
            categories.add(str(item["aamc_category"]))
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        for item in merge_fr_source_banks(content_dir):
            categories.add(str(item["aamc_category"]))
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        for passage in merge_passage_source_banks(content_dir):
            for question in passage.get("questions") or []:
                category = _passage_question_category(passage, question)
                if category:
                    categories.add(category)
    except Exception:  # pragma: no cover - defensive
        pass
    return sorted(categories)


# --- pure free-response auto-grader (shared with the FR reviewer) -----------
#
# Kept free of Anki/Qt so the normalised string / key-term / numeric-tolerance
# grading can be unit-tested directly, and so the TypeScript FR reviewer has a
# single documented specification to mirror.

_FR_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_FR_WS_RE = re.compile(r"\s+")
_FR_SQUASH_RE = re.compile(r"[^a-z0-9]")
_FR_NUMBER_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_FR_TOLERANCE_RE = re.compile(
    r"tolerance\s*[:=]?\s*[±+\-]?\s*"
    r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(%?)",
    re.IGNORECASE,
)


def normalize_answer(text: Any) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for comparison."""
    if text is None:
        return ""
    lowered = str(text).strip().lower()
    depunct = _FR_PUNCT_RE.sub(" ", lowered)
    return _FR_WS_RE.sub(" ", depunct).strip()


def _squash(text: Any) -> str:
    """Normalise then drop all non-alphanumerics (loose match for equations)."""
    return _FR_SQUASH_RE.sub("", normalize_answer(text))


def to_number(text: Any) -> float | None:
    """Best-effort leading numeric value in a string (``"30 m/s" -> 30.0``)."""
    if text is None:
        return None
    match = _FR_NUMBER_RE.search(str(text).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:  # pragma: no cover - regex already constrains this
        return None


def numeric_tolerance_from_key_terms(
    key_terms: list[Any] | None,
) -> tuple[float, bool] | None:
    """Extract a numeric tolerance from a ``"tolerance: ±0.5 m/s"`` key-term.

    Returns ``(magnitude, is_percent)`` or ``None`` when no tolerance is given.
    A trailing ``%`` marks a relative tolerance (fraction of the accepted
    value)."""
    for term in key_terms or []:
        text = str(term)
        if "tolerance" in text.lower():
            match = _FR_TOLERANCE_RE.search(text)
            if match:
                try:
                    return (abs(float(match.group(1))), match.group(2) == "%")
                except ValueError:  # pragma: no cover - defensive
                    continue
    return None


def _non_directive_key_terms(key_terms: list[Any] | None) -> list[str]:
    """Key terms with the ``tolerance:`` / ``unit:`` directives removed."""
    out: list[str] = []
    for term in key_terms or []:
        low = str(term).strip().lower()
        if low.startswith("tolerance") or low.startswith("unit"):
            continue
        out.append(str(term))
    return out


def grade_free_response(
    user_answer: Any,
    accepted_answers: list[Any] | None,
    key_terms: list[Any] | None = None,
) -> bool:
    """Auto-grade a typed answer against ``accepted_answers`` / ``key_terms``.

    An answer is correct when ANY of these hold:

    * it parses to a number matching an accepted numeric answer (within the
      tolerance from ``key_terms`` when provided, else effectively exactly);
    * its normalised (or squashed) form equals an accepted answer;
    * every non-directive key term appears in it (lets prose / derivations that
      contain the essential terms count).
    """
    accepted_answers = accepted_answers or []
    key_terms = key_terms or []
    user_norm = normalize_answer(user_answer)
    if not user_norm:
        return False
    user_squash = _squash(user_answer)
    user_num = to_number(user_answer)
    tolerance = numeric_tolerance_from_key_terms(key_terms)

    # 1. numeric match (respecting a provided tolerance)
    if user_num is not None:
        for accepted in accepted_answers:
            accepted_num = to_number(accepted)
            if accepted_num is None:
                continue
            if tolerance is not None:
                magnitude, is_percent = tolerance
                bound = (
                    magnitude / 100.0 * abs(accepted_num) if is_percent else magnitude
                )
                if abs(user_num - accepted_num) <= bound + 1e-9:
                    return True
            elif abs(user_num - accepted_num) <= 1e-9:
                return True

    # 2. normalised / squashed string match
    for accepted in accepted_answers:
        if not str(accepted).strip():
            continue
        accepted_squash = _squash(accepted)
        if normalize_answer(accepted) == user_norm or (
            accepted_squash and accepted_squash == user_squash
        ):
            return True

    # 3. every non-directive key term present in the answer
    terms = [_squash(t) for t in _non_directive_key_terms(key_terms)]
    terms = [t for t in terms if len(t) >= 3]
    if terms and all(term in user_squash for term in terms):
        return True

    return False


def parse_fr_subquestions(raw: str | None) -> list[dict[str, Any]]:
    """Parse a free-response note's ``Subquestions`` JSON into a type-in ladder.

    Each rung is normalised to ``{stem, accepted_answers[], key_terms[],
    explanation}``; malformed rungs (no stem / no accepted answers) are dropped
    so the reviewer runs a shorter — or empty — ladder rather than crashing."""
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
        stem = str(entry.get("stem", "")).strip()
        accepted = entry.get("accepted_answers")
        if not stem or not isinstance(accepted, list) or not accepted:
            continue
        key_terms = entry.get("key_terms")
        rungs.append(
            {
                "stem": stem,
                "accepted_answers": [str(a) for a in accepted],
                "key_terms": [str(k) for k in key_terms]
                if isinstance(key_terms, list)
                else [],
                "explanation": str(entry.get("explanation", "")),
            }
        )
    return rungs


def _load_json_list(raw: str | None) -> list[Any]:
    """Defensively parse a JSON-array note field into a Python list."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def fr_payload_from_fields(fields: dict[str, str]) -> dict[str, Any]:
    """Build the free-response reviewer payload from a note's fields.

    Kept pure so the reviewer's data contract is testable without a webview."""
    return {
        "prompt": fields.get("Prompt", ""),
        "acceptedAnswers": [
            str(a) for a in _load_json_list(fields.get("AcceptedAnswers"))
        ],
        "keyTerms": [str(k) for k in _load_json_list(fields.get("KeyTerms"))],
        "modelAnswer": fields.get("ModelAnswer", ""),
        "explanation": fields.get("Explanation", ""),
        "subtopic": fields.get("Subtopic", ""),
        "source": fields.get("Source", ""),
        "subquestions": parse_fr_subquestions(fields.get("Subquestions", "")),
    }


def passage_payload_from_fields(fields: dict[str, str]) -> dict[str, Any]:
    """Build the passage reviewer payload from a note's fields.

    The passage is carried alongside an MCQ-style question so the reviewer can
    show the two together; the guiding ladder reuses the MCQ sub-question shape.
    """
    try:
        correct_index = int(str(fields.get("CorrectIndex", "0")).strip() or "0")
    except ValueError:
        correct_index = 0
    correct_index = max(0, min(3, correct_index))
    return {
        "passage": fields.get("Passage", ""),
        "passageId": fields.get("PassageId", ""),
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
        # Passage ladders may have a variable number of options (AAMC use four,
        # CARS use two or three), so use the lenient passage parser.
        "subquestions": parse_passage_subquestions(fields.get("Subquestions", "")),
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
        fr_items = merge_fr_source_banks()
        passages = merge_passage_source_banks()
        cars = merge_cars_passage_banks()
        print(
            f"Free-response bank: {len(fr_items)} items. "
            f"Passage bank: {len(passages)} passages / "
            f"{passage_question_count(passages)} questions."
        )
        print(
            f"CARS passage bank: {len(cars)} passages / "
            f"{passage_question_count(cars)} questions "
            f"(skills section; no AAMC category, ignored by points-at-stake)."
        )

    if args.sync_taxonomy:
        categories = all_content_categories()
        added = ensure_taxonomy_mappings(args.sync_taxonomy, categories)
        print(
            f"Added {added} ReadyMCAT mapping(s) to {args.sync_taxonomy} "
            f"({len(categories)} categories across MCQ + FR + passage)."
        )

    if args.collection:
        _ensure_anki_importable()
        from anki.collection import Collection

        col = Collection(str(Path(args.collection).expanduser()))
        try:
            stats = provision_all(col)
        finally:
            col.close()
        print(json.dumps({k: v.as_dict() for k, v in stats.items()}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
