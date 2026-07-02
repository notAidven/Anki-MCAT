#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Seed SYNTHETIC demo data so the ReadyMCAT honest-scores dashboard renders
all THREE scores (Memory, Performance, Readiness) fully populated.

============================  H O N E S T Y   R U L E  ========================
Everything this script creates is FAKE. It exists only to preview how the
dashboard *looks* once a real student has studied for a while. It is NOT a real
student's readiness, and the numbers are invented. Every seeded note is tagged
``ReadyMCAT_SYNTHETIC_DEMO`` and every seeded card's text says so, so the demo
data is easy to spot and to delete (see ``remove_demo_data``).
===============================================================================

What it does
------------
The dashboard (``rslib/src/points_at_stake``) computes three honest scores, each
with its own give-up rule:

* **Memory** — the FSRS recall probability of the cards mapped to each AAMC
  category (via ``taxonomy.json``), shown as a range once there are >= 200
  graded reviews AND >= 50% category coverage.
* **Performance** — first-attempt accuracy on the ReadyMCAT question notetypes
  (MCQ / FreeResponse / Passage) read from the review log, shown once there are
  >= 30 first attempts.
* **Readiness** — a heuristic (uncalibrated) 472–528 projection blended from
  performance + memory, shown only once BOTH of the above qualify.

To make all three render, this seeder:

* creates dummy Basic cards in the decks / with the tags that ``taxonomy.json``
  maps onto ~70% of the 31 AAMC categories (so coverage clears 50%),
* gives each card an FSRS memory state (stability + difficulty) chosen so its
  recall lands in a designed per-category band — some topics strong, some weak,
  so "what to study next" is meaningful,
* writes a realistic synthetic review history to ``revlog`` (well over the 200
  graded-reviews threshold), and
* creates synthetic practice-question cards on the three ReadyMCAT question
  notetypes, each with one first-attempt review whose grade (Good=hit /
  Again=miss) is drawn from a designed per-category accuracy — so performance
  (and hence readiness) computes real numbers.

Both aggregations are computed purely from the collection (FSRS state + the
review log), so these synthetic states are exactly what the dashboard reads
back.

Usage (dev)
-----------
Run inside the built dev environment (after ``ninja pylib`` / ``just build``)::

    out/pyenv/bin/python readymcat/tools/seed_demo_dashboard.py \
        --collection /path/to/collection.anki2

Or seed the collection of a named profile base::

    out/pyenv/bin/python readymcat/tools/seed_demo_dashboard.py \
        --anki-base "$HOME/.local/share/Anki2" --profile "User 1"

The desktop app exposes the same routine through
*Tools → Load ReadyMCAT demo data (SYNTHETIC)* (see ``qt/aqt/readymcat_demo.py``).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from anki.collection import Collection

# --- honesty markers --------------------------------------------------------

#: Tag applied to every synthetic note. Search ``tag:ReadyMCAT_SYNTHETIC_DEMO``
#: to find (or delete) the demo data.
DEMO_TAG = "ReadyMCAT_SYNTHETIC_DEMO"
#: Per-card human-readable category tag, e.g. ``ReadyMCAT_demo::cat::1A``. These
#: do NOT start with ``#`` so they never interfere with taxonomy tag mappings.
DEMO_CAT_TAG_PREFIX = "ReadyMCAT_demo::cat"
#: Holding deck for categories that resolve via a ``#`` tag (no subdeck mapping).
DEMO_HOLDING_DECK = "ReadyMCAT Demo (SYNTHETIC)"
#: Collection-config marker recording when the demo was last seeded.
DEMO_CONFIG_KEY = "readymcat_demo_seeded_at"

# FSRS forgetting-curve factor for the default decay (0.5): 0.9**-2 - 1.
# Retrievability R(t) = (1 + FSRS_FACTOR * t / S) ** -0.5, so R == 0.9 when the
# elapsed time t equals the stability S. Inverting gives the stability needed to
# land a card at a target recall (see ``_stability_for``).
FSRS_FACTOR = 0.2345

# Designed target *mean* recall per AAMC category. Covering these 22 of the 31
# categories clears the 50% coverage gate (~71%) while leaving visible gaps.
# A few high-exam-weight topics (1A proteins, 3A nervous/endocrine, 5D organic,
# 5E thermo/kinetics) are deliberately weak so they surface in "what to study
# next" (points = topic_weight * weakness); others look strong.
TARGET_RECALL: dict[str, float] = {
    "1A": 0.52,  # Proteins & amino acids (weight 3.53) -> weak, high yield
    "1B": 0.82,  # Gene -> protein
    "1C": 0.68,  # Heredity & genetic diversity
    "1D": 0.90,  # Bioenergetics & metabolism -> strong
    "2A": 0.80,  # Cells / assemblies of molecules
    "2B": 0.62,  # Prokaryotes & viruses (resolved via a # tag)
    "2C": 0.70,  # Cell division & differentiation
    "3A": 0.58,  # Nervous & endocrine (weight 3.21) -> weak, high yield
    "3B": 0.72,  # Organ systems
    "4A": 0.88,  # Mechanics / translational motion -> strong
    "4C": 0.60,  # Circuits & electrochemistry -> weak
    "4D": 0.74,  # Light & sound
    "5A": 0.84,  # Water & solutions
    "5B": 0.70,  # Molecules & intermolecular forces
    "5D": 0.55,  # Organic reactivity (weight 3.08) -> weak, high yield
    "5E": 0.66,  # Thermodynamics & kinetics -> weak-ish, high yield
    "6A": 0.90,  # Sensing the environment -> strong
    "6B": 0.86,  # Cognition & memory -> strong
    "7A": 0.83,  # Individual influences on behavior
    "7B": 0.71,  # Social processes
    "8A": 0.82,  # Self-identity
    "9A": 0.72,  # Understanding social structure
}

# Designed first-attempt ACCURACY per AAMC category for the seeded practice
# questions (drives the PERFORMANCE score, which is separate from memory). A few
# high-yield topics are deliberately weak (1A proteins, 3A nervous/endocrine, 5D
# organic) so the per-topic accuracy breakdown is meaningful. 16 categories x 3
# question notetypes x cards each clears the 30-attempt performance give-up rule
# comfortably.
TARGET_ACCURACY: dict[str, float] = {
    "1A": 0.48,  # Proteins & amino acids -> weak, high yield
    "1B": 0.78,  # Gene -> protein
    "1D": 0.85,  # Bioenergetics & metabolism -> strong
    "2A": 0.72,  # Cells / assemblies of molecules
    "3A": 0.55,  # Nervous & endocrine -> weak, high yield
    "3B": 0.70,  # Organ systems
    "4A": 0.82,  # Mechanics -> strong
    "4C": 0.58,  # Circuits & electrochemistry -> weak
    "5A": 0.80,  # Water & solutions
    "5B": 0.68,  # Molecules & intermolecular forces
    "5D": 0.52,  # Organic reactivity -> weak, high yield
    "5E": 0.63,  # Thermodynamics & kinetics
    "6A": 0.86,  # Sensing the environment -> strong
    "6B": 0.83,  # Cognition & memory -> strong
    "7A": 0.75,  # Individual influences on behavior
    "7B": 0.71,  # Social processes
}

#: Sub-deck of the holding deck the synthetic practice-question cards live in, so
#: they never pollute the counts of the real pre-loaded ReadyMCAT decks.
DEMO_QUESTION_DECK = f"{DEMO_HOLDING_DECK}::Practice Questions"


class DemoStats:
    """Summary of what a seeding run created (or found already present)."""

    def __init__(self) -> None:
        self.already_seeded = False
        self.categories_covered = 0
        self.cards_created = 0
        self.reviews_created = 0
        #: Synthetic practice-question cards created (drive the performance score).
        self.questions_created = 0
        #: First-attempt hits designed into those question cards.
        self.question_hits = 0
        self.taxonomy_path = ""
        self.category_recall: dict[str, float] = {}
        self.skipped_categories: list[str] = []
        # Filled in by the backend self-verify (None if it could not run).
        self.meets_threshold: bool | None = None
        self.memory_low: float | None = None
        self.memory_high: float | None = None
        self.reported_graded_reviews: int | None = None
        self.reported_graded_cards: int | None = None
        self.coverage_covered: int | None = None
        self.coverage_total: int | None = None
        self.coverage_fraction: float | None = None
        self.coverage_weighted: float | None = None
        #: [(category, name, points)] highest first — the "what to study next" list.
        self.study_next: list[tuple[str, str, float]] = []
        # Performance (accuracy on practice questions) self-check.
        self.performance_meets: bool | None = None
        self.performance_low: float | None = None
        self.performance_high: float | None = None
        self.performance_mean: float | None = None
        self.performance_attempts: int | None = None
        # Readiness (heuristic 472–528 projection) self-check.
        self.readiness_meets: bool | None = None
        self.readiness_point: float | None = None
        self.readiness_low: float | None = None
        self.readiness_high: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "already_seeded": self.already_seeded,
            "categories_covered": self.categories_covered,
            "cards_created": self.cards_created,
            "reviews_created": self.reviews_created,
            "questions_created": self.questions_created,
            "question_hits": self.question_hits,
            "taxonomy_path": self.taxonomy_path,
            "category_recall": self.category_recall,
            "skipped_categories": self.skipped_categories,
            "meets_threshold": self.meets_threshold,
            "memory_low": self.memory_low,
            "memory_high": self.memory_high,
            "reported_graded_reviews": self.reported_graded_reviews,
            "reported_graded_cards": self.reported_graded_cards,
            "coverage_covered": self.coverage_covered,
            "coverage_total": self.coverage_total,
            "coverage_fraction": self.coverage_fraction,
            "coverage_weighted": self.coverage_weighted,
            "study_next": self.study_next,
            "performance_meets": self.performance_meets,
            "performance_low": self.performance_low,
            "performance_high": self.performance_high,
            "performance_mean": self.performance_mean,
            "performance_attempts": self.performance_attempts,
            "readiness_meets": self.readiness_meets,
            "readiness_point": self.readiness_point,
            "readiness_low": self.readiness_low,
            "readiness_high": self.readiness_high,
        }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _stability_for(recall: float, elapsed_days: float) -> float:
    """Stability (days) that puts a card at ~``recall`` after ``elapsed_days``.

    Inverts the FSRS forgetting curve R = (1 + FSRS_FACTOR * t/S) ** -0.5."""
    r = _clamp(recall, 0.05, 0.985)
    denom = r**-2.0 - 1.0
    if denom <= 1e-6:
        return max(elapsed_days * 60.0, 60.0)
    return max(FSRS_FACTOR * elapsed_days / denom, 0.5)


def _ease_pool(recall: float) -> list[int]:
    """A pool of review buttons (1=Again..4=Easy) reflecting a recall band."""
    if recall >= 0.85:
        return [3, 3, 4, 4, 2]
    if recall >= 0.70:
        return [2, 3, 3, 4, 3]
    if recall >= 0.55:
        return [1, 2, 3, 3, 2]
    return [1, 1, 2, 3, 2]


def _load_question_bank() -> Any:
    """Load the pure-``anki`` question-bank builder module (same directory).

    It is the single source of truth for the ReadyMCAT question notetype names
    (``ReadyMCAT MCQ`` / ``ReadyMCAT FreeResponse`` / ``ReadyMCAT Passage``) and
    the ``#ReadyMCAT::AAMC::<cat>`` tag helper — the exact names the Rust
    performance query filters on — so the demo cards are counted."""
    import importlib.util

    path = Path(__file__).resolve().parent / "build_question_bank.py"
    spec = importlib.util.spec_from_file_location(
        "readymcat_build_question_bank_for_seed", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_taxonomy(col: "Collection | None") -> Path | None:
    """Locate taxonomy.json: env override, next to the collection, or repo root."""
    candidates: list[Path] = []
    env = os.environ.get("READYMCAT_TAXONOMY")
    if env:
        candidates.append(Path(env))
    if col is not None:
        try:
            candidates.append(Path(col.path).resolve().parent / "taxonomy.json")
        except Exception:
            pass
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "taxonomy.json")
    candidates.append(Path.cwd() / "taxonomy.json")
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _representative_mapping(
    mappings: list[dict[str, str]], category: str
) -> tuple[str, str] | None:
    """Pick how to place cards into ``category``.

    Returns ``("deck", name)`` for a subdeck mapping (matched by deck name) or
    ``("tag", "#...")`` for a tag mapping. Subdeck mappings win; among them the
    shallowest/shortest path is chosen for a clean deck name. ``None`` if the
    category has no mapping at all."""
    subdecks = [
        m["deck_tag_or_subdeck"]
        for m in mappings
        if m.get("category") == category
        and not str(m.get("deck_tag_or_subdeck", "")).startswith("#")
    ]
    if subdecks:
        best = min(subdecks, key=lambda p: (p.count("::"), len(p)))
        return ("deck", best)
    tags = [
        m["deck_tag_or_subdeck"]
        for m in mappings
        if m.get("category") == category
        and str(m.get("deck_tag_or_subdeck", "")).startswith("#")
    ]
    if tags:
        return ("tag", tags[0])
    return None


def has_demo_data(col: "Collection") -> bool:
    """True if synthetic demo notes are already present."""
    try:
        return bool(col.find_notes(f"tag:{DEMO_TAG}"))
    except Exception:
        return False


def remove_demo_data(col: "Collection") -> int:
    """Delete every synthetic demo note (and its cards). Returns notes removed."""
    note_ids = list(col.find_notes(f"tag:{DEMO_TAG}"))
    if note_ids:
        col.remove_notes(note_ids)
    try:
        col.remove_config(DEMO_CONFIG_KEY)
    except Exception:
        pass
    return len(note_ids)


def seed_demo_data(
    col: "Collection",
    *,
    cards_per_category: int = 12,
    question_cards_per_type: int = 3,
    seed: int = 1234,
    reseed: bool = False,
    log: Callable[[str], None] = print,
) -> DemoStats:
    """Populate ``col`` with synthetic, clearly-labelled ReadyMCAT demo data.

    Idempotent: if demo data already exists it is left untouched unless
    ``reseed`` is set (in which case the old demo data is removed first)."""
    from anki.cards import FSRSMemoryState
    from anki.consts import CARD_TYPE_REV, QUEUE_TYPE_REV

    stats = DemoStats()

    if has_demo_data(col):
        if not reseed:
            existing = len(col.find_notes(f"tag:{DEMO_TAG}"))
            stats.already_seeded = True
            stats.cards_created = existing
            log(
                f"ReadyMCAT demo: {existing} synthetic notes already present; "
                "skipping (pass reseed=True to rebuild)."
            )
            return stats
        removed = remove_demo_data(col)
        log(f"ReadyMCAT demo: removed {removed} existing synthetic notes.")

    taxonomy_path = _find_taxonomy(col)
    if taxonomy_path is None:
        raise FileNotFoundError(
            "taxonomy.json not found (looked next to the collection, at the repo "
            "root, and $READYMCAT_TAXONOMY). It is required to map cards to AAMC "
            "categories."
        )
    stats.taxonomy_path = str(taxonomy_path)
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    mappings: list[dict[str, str]] = taxonomy.get("mappings", [])
    categories: dict[str, Any] = taxonomy.get("aamc_categories", {})

    notetype = col.models.by_name("Basic")
    if notetype is None:
        notetype = col.models.all()[0]

    rng = random.Random(seed)
    today = int(col.sched.today)
    now = int(time.time())
    now_ms = now * 1000

    cards_to_update: list[Any] = []
    # revlog tuples without an id yet: (cid, ease, ivl, lastIvl, factor, time, type)
    pending_reviews: list[tuple[int, int, int, int, int, int, int]] = []
    holding_deck_id: int | None = None

    for category, target in TARGET_RECALL.items():
        rep = _representative_mapping(mappings, category)
        if rep is None:
            stats.skipped_categories.append(category)
            log(f"ReadyMCAT demo: no taxonomy mapping for {category}; skipping.")
            continue
        kind, path = rep
        extra_tag: str | None = None
        if kind == "deck":
            deck_id = col.decks.id(path)
        else:
            if holding_deck_id is None:
                holding_deck_id = col.decks.id(DEMO_HOLDING_DECK)
            deck_id = holding_deck_id
            extra_tag = path  # a "#..."-prefixed tag the taxonomy maps to category

        cat_name = str(categories.get(category, {}).get("name", category))[:60]
        recall_samples: list[float] = []

        for i in range(cards_per_category):
            recall = _clamp(rng.gauss(target, 0.06), 0.05, 0.985)
            elapsed_days = rng.randint(6, 40)
            stability = _stability_for(recall, elapsed_days)
            difficulty = _clamp(
                1.0 + 9.0 * (1.0 - recall) + rng.uniform(-0.5, 0.5), 1.0, 10.0
            )

            note = col.new_note(notetype)
            note.fields[0] = (
                f"[SYNTHETIC DEMO] {category} · {cat_name} — sample {i + 1}"
            )
            note.fields[1] = (
                "Synthetic ReadyMCAT demo card (fake data for a dashboard preview, "
                "not real study material)."
            )
            note.add_tag(DEMO_TAG)
            note.add_tag(f"{DEMO_CAT_TAG_PREFIX}::{category}")
            if extra_tag is not None:
                note.add_tag(extra_tag)
            col.add_note(note, deck_id)

            for cid in col.db.list("select id from cards where nid = ?", note.id):
                card = col.get_card(cid)
                card.type = CARD_TYPE_REV
                card.queue = QUEUE_TYPE_REV
                card.ivl = max(1, round(stability))
                card.due = today - rng.randint(0, 15)
                card.memory_state = FSRSMemoryState(
                    stability=float(stability), difficulty=float(difficulty)
                )
                card.last_review_time = now - elapsed_days * 86400
                cards_to_update.append(card)

                n_reviews = int(
                    _clamp(round(2 + stability / 12 + rng.uniform(-1, 1)), 2, 12)
                )
                eases = _ease_pool(recall)
                prev_ivl = 1
                for r in range(n_reviews):
                    ease = rng.choice(eases)
                    ivl = max(1, round(stability * (r + 1) / n_reviews))
                    pending_reviews.append(
                        (
                            int(cid),
                            ease,
                            ivl,
                            prev_ivl,
                            2500,
                            rng.randint(3000, 25000),
                            1,
                        )
                    )
                    prev_ivl = ivl

            recall_samples.append(recall)
            stats.cards_created += 1

        stats.categories_covered += 1
        if recall_samples:
            stats.category_recall[category] = sum(recall_samples) / len(recall_samples)

    # --- performance: synthetic practice-question attempts ------------------
    # The performance score is first-attempt accuracy on the ReadyMCAT question
    # notetypes (MCQ / FreeResponse / Passage), read from the review log. Seed a
    # spread of question cards (tagged so taxonomy resolves them to a category)
    # and give each ONE first-attempt review whose grade (Good=hit / Again=miss)
    # is drawn from the category's designed accuracy. One review per card means
    # its first attempt is unambiguous regardless of how revlog ids are spread.
    _seed_question_attempts(
        col,
        categories=categories,
        cards_to_update=cards_to_update,
        pending_reviews=pending_reviews,
        today=today,
        now=now,
        rng=rng,
        cards_per_type=question_cards_per_type,
        stats=stats,
        log=log,
    )

    # Persist card FSRS state in batches (one backend call per chunk).
    for start in range(0, len(cards_to_update), 200):
        col.update_cards(cards_to_update[start : start + 200], skip_undo_entry=True)

    # Assign strictly-increasing revlog ids spread across the last ~119 days
    # (ids double as review timestamps in ms and must be unique).
    total = len(pending_reviews)
    span_ms = 119 * 86400 * 1000
    base = now_ms - span_ms
    spacing = max(1, span_ms // max(total, 1))
    rng.shuffle(pending_reviews)
    revlog_rows = [
        (base + k * spacing, cid, 0, ease, ivl, last_ivl, factor, dur, rtype)
        for k, (cid, ease, ivl, last_ivl, factor, dur, rtype) in enumerate(
            pending_reviews
        )
    ]
    if revlog_rows:
        col.db.executemany(
            "insert into revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            revlog_rows,
        )
    stats.reviews_created = total

    # Marker (also forces the write transaction to commit through the backend).
    try:
        col.set_config(DEMO_CONFIG_KEY, now)
    except Exception:
        pass

    _verify(col, stats, log)

    log(
        "ReadyMCAT demo: seeded SYNTHETIC data — "
        f"{stats.cards_created} memory cards across {stats.categories_covered} "
        f"AAMC categories plus {stats.questions_created} practice questions, "
        f"{stats.reviews_created} graded reviews. "
        f"Delete anytime with search 'tag:{DEMO_TAG}'."
    )
    return stats


def _seed_question_attempts(
    col: "Collection",
    *,
    categories: dict[str, Any],
    cards_to_update: list[Any],
    pending_reviews: list[tuple[int, int, int, int, int, int, int]],
    today: int,
    now: int,
    rng: random.Random,
    cards_per_type: int,
    stats: DemoStats,
    log: Callable[[str], None],
) -> None:
    """Create synthetic ReadyMCAT question cards (MCQ / FreeResponse / Passage)
    with one first-attempt review each, so the honest PERFORMANCE score computes
    (and, with memory, READINESS too). Mutates ``cards_to_update`` /
    ``pending_reviews`` in place; ids are assigned by the caller."""
    from anki.cards import FSRSMemoryState
    from anki.consts import CARD_TYPE_REV, QUEUE_TYPE_REV

    try:
        bank = _load_question_bank()
    except Exception as exc:  # pragma: no cover - defensive
        log(f"ReadyMCAT demo: could not load question bank builder ({exc}); "
            "skipping performance seeding.")
        return

    # Ensure the three question notetypes exist (their names must match what the
    # Rust performance query filters on).
    question_types = [
        bank.ensure_notetype(col),
        bank.ensure_fr_notetype(col),
        bank.ensure_passage_notetype(col),
    ]
    deck_id = col.decks.id(DEMO_QUESTION_DECK)

    for category, accuracy in TARGET_ACCURACY.items():
        if category not in categories:
            # Not an AAMC category in this taxonomy; skip rather than invent.
            continue
        cat_name = str(categories.get(category, {}).get("name", category))[:60]
        cat_tag = bank.aamc_tag_for(category)  # "#ReadyMCAT::AAMC::<cat>"
        recall_target = TARGET_RECALL.get(category, 0.72)
        for notetype in question_types:
            type_name = str(notetype.get("name", "ReadyMCAT"))
            for i in range(cards_per_type):
                note = col.new_note(notetype)
                # Fill every field so a card is always generated, whatever the
                # notetype's template references.
                label = (
                    f"[SYNTHETIC DEMO] {category} · {cat_name} — "
                    f"{type_name} sample {i + 1}"
                )
                for field_index in range(len(note.fields)):
                    note.fields[field_index] = label
                note.add_tag(DEMO_TAG)
                note.add_tag(cat_tag)
                note.add_tag(f"{DEMO_CAT_TAG_PREFIX}::{category}")
                col.add_note(note, deck_id)

                hit = rng.random() < accuracy
                # Mirror the reviewer's grading: first-try correct -> Good (3);
                # a miss (needed the teach-on-miss ladder) -> Again (1).
                ease = 3 if hit else 1
                recall = _clamp(rng.gauss(recall_target, 0.06), 0.05, 0.985)
                elapsed_days = rng.randint(6, 40)
                stability = _stability_for(recall, elapsed_days)
                difficulty = _clamp(1.0 + 9.0 * (1.0 - recall), 1.0, 10.0)

                for cid in col.db.list("select id from cards where nid = ?", note.id):
                    card = col.get_card(cid)
                    card.type = CARD_TYPE_REV
                    card.queue = QUEUE_TYPE_REV
                    card.ivl = max(1, round(stability))
                    card.due = today - rng.randint(0, 15)
                    card.memory_state = FSRSMemoryState(
                        stability=float(stability), difficulty=float(difficulty)
                    )
                    card.last_review_time = now - elapsed_days * 86400
                    cards_to_update.append(card)
                    # A single first-attempt review (id assigned later).
                    pending_reviews.append(
                        (
                            int(cid),
                            ease,
                            max(1, round(stability)),
                            1,
                            2500,
                            rng.randint(3000, 25000),
                            1,
                        )
                    )
                stats.questions_created += 1
                if hit:
                    stats.question_hits += 1

    log(
        f"ReadyMCAT demo: seeded {stats.questions_created} synthetic practice "
        f"questions ({stats.question_hits} designed first-try hits) for the "
        "performance score."
    )


def _verify(col: "Collection", stats: DemoStats, log: Callable[[str], None]) -> None:
    """Ask the backend to aggregate what we just seeded, so we can report the
    resulting (SYNTHETIC) memory range, coverage and "what to study next", and
    confirm the give-up threshold is cleared. Best-effort; never fatal."""
    try:
        resp = col._backend.points_at_stake_queue(
            taxonomy_path=stats.taxonomy_path, deck_id=0, limit=0
        )
    except Exception as exc:  # pragma: no cover - verification is optional
        log(f"ReadyMCAT demo: dashboard self-check skipped ({exc}).")
        return
    stats.meets_threshold = bool(resp.meets_data_threshold)
    stats.memory_low = float(resp.memory.range_low)
    stats.memory_high = float(resp.memory.range_high)
    stats.reported_graded_reviews = int(resp.memory.graded_reviews)
    stats.reported_graded_cards = int(resp.memory.graded_cards)
    stats.coverage_covered = int(resp.coverage.categories_covered)
    stats.coverage_total = int(resp.coverage.categories_total)
    stats.coverage_fraction = float(resp.coverage.fraction)
    stats.coverage_weighted = float(resp.coverage.weighted_fraction)
    stats.study_next = sorted(
        (
            (t.category, t.name, t.topic_weight * t.student_weakness)
            for t in resp.topics
            if t.total_cards > 0
        ),
        key=lambda item: item[2],
        reverse=True,
    )[:6]
    # Performance + readiness (added alongside memory).
    perf = getattr(resp, "performance", None)
    if perf is not None:
        stats.performance_meets = bool(perf.meets_data_threshold)
        stats.performance_low = float(perf.range_low)
        stats.performance_high = float(perf.range_high)
        stats.performance_mean = float(perf.mean)
        stats.performance_attempts = int(perf.attempts)
    ready = getattr(resp, "readiness", None)
    if ready is not None:
        stats.readiness_meets = bool(ready.meets_data_threshold)
        stats.readiness_point = float(ready.point)
        stats.readiness_low = float(ready.range_low)
        stats.readiness_high = float(ready.range_high)
    log(
        "ReadyMCAT demo: dashboard self-check — "
        f"memory_meets={stats.meets_threshold}, "
        f"memory={round((stats.memory_low or 0) * 100)}%–"
        f"{round((stats.memory_high or 0) * 100)}%, "
        f"coverage={stats.coverage_covered}/{stats.coverage_total} "
        f"({round((stats.coverage_fraction or 0) * 100)}%), "
        f"graded_reviews={stats.reported_graded_reviews}; "
        f"performance_meets={stats.performance_meets}, "
        f"performance={round((stats.performance_low or 0) * 100)}%–"
        f"{round((stats.performance_high or 0) * 100)}% "
        f"over {stats.performance_attempts} attempts; "
        f"readiness_meets={stats.readiness_meets}, "
        f"readiness={round(stats.readiness_point or 0)} "
        f"({round(stats.readiness_low or 0)}–{round(stats.readiness_high or 0)})."
    )


# --- standalone CLI ---------------------------------------------------------


def _ensure_anki_importable() -> None:
    """Make ``anki`` importable when run as a plain script from the repo."""
    try:
        import anki  # noqa: F401

        return
    except Exception:
        pass
    repo_root = Path(__file__).resolve().parents[2]
    for rel in ("pylib", "out/pylib"):
        path = repo_root / rel
        if path.is_dir():
            sys.path.insert(0, str(path))


def _resolve_collection_path(args: argparse.Namespace) -> str:
    if args.collection:
        return str(Path(args.collection).expanduser())
    base = args.anki_base or os.environ.get("ANKI_BASE")
    if base:
        return str(Path(base).expanduser() / args.profile / "collection.anki2")
    raise SystemExit(
        "error: pass --collection PATH, or --anki-base BASE (+ --profile NAME)."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed SYNTHETIC ReadyMCAT demo data for the dashboard preview."
    )
    parser.add_argument("--collection", help="path to a collection.anki2 file")
    parser.add_argument("--anki-base", help="Anki base dir (contains profiles)")
    parser.add_argument(
        "--profile", default="User 1", help="profile name under --anki-base"
    )
    parser.add_argument("--cards-per-category", type=int, default=12)
    parser.add_argument("--question-cards-per-type", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument(
        "--reseed", action="store_true", help="remove existing demo data first"
    )
    args = parser.parse_args(argv)

    _ensure_anki_importable()
    from anki.collection import Collection

    col_path = _resolve_collection_path(args)
    print("=" * 78)
    print("ReadyMCAT SYNTHETIC demo seeder — this writes FAKE data for a UI preview.")
    print(f"Collection: {col_path}")
    print("=" * 78)

    col = Collection(col_path)
    try:
        stats = seed_demo_data(
            col,
            cards_per_category=args.cards_per_category,
            question_cards_per_type=args.question_cards_per_type,
            seed=args.seed,
            reseed=args.reseed,
        )
    finally:
        col.close()

    print(json.dumps(stats.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
