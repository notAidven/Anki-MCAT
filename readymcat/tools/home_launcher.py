# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Pure helpers behind the ReadyMCAT home/study-launcher hub.

The hub (``ts/routes/readymcat-home``) is a single-screen dashboard whose
hero is four one-tap launch tiles (Multiple Choice, Free Response, Passage
Sets, CARS). This module computes the honest numbers those tiles — and the
secondary "overall progress" panel — need:

* per-format due/total card counts, read straight off ``DeckTreeNode``'s
  *own* (child-excluding) counters so a parent deck's tile never silently
  includes a nested sibling format's cards (``ReadyMCAT`` has ``Free
  Response``, ``Passages`` and ``Passages::CARS`` as subdecks);
* a streak, "active days this week" and a 7-day accuracy figure, read
  straight from the review log; and
* whether the introductory diagnostic has been taken.

Nothing here is invented: counts with no evidence report ``None``/``0``
honestly rather than a fabricated placeholder, mirroring the give-up rule the
honest-memory dashboard already follows (see ``rslib/src/points_at_stake/``).

Loaded by path (mirrors ``build_question_bank.py`` / ``seed_demo_dashboard.py``)
from ``qt/aqt/readymcat_home.py`` and from the pylib test suite, so it has no
import-time dependency on ``aqt`` or a packaged ``anki`` install.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# Rolling window used for "active days this week" and the 7-day accuracy
# figure. Not a calendar week — a trailing 7-day window is simpler to reason
# about and just as honest.
ACCURACY_WINDOW_DAYS = 7

MS_PER_DAY = 24 * 60 * 60 * 1000


class _DeckTreeNodeLike(Protocol):
    deck_id: int
    total_in_deck: int
    new_uncapped: int
    review_uncapped: int
    intraday_learning: int
    interday_learning_uncapped: int
    children: list[Any]


@dataclass
class DeckLaunchStats:
    """Honest, child-excluding due/total counts for one launch tile."""

    deck_id: int | None
    present: bool
    due: int
    total: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "deckId": int(self.deck_id) if self.deck_id else None,
            "due": self.due,
            "total": self.total,
        }


def find_deck_node(
    root: _DeckTreeNodeLike, deck_id: int
) -> _DeckTreeNodeLike | None:
    """Depth-first search for ``deck_id`` in a ``col.decks.deck_tree()`` result."""
    if root.deck_id == deck_id:
        return root
    for child in root.children:
        found = find_deck_node(child, deck_id)
        if found is not None:
            return found
    return None


def deck_launch_stats(
    node: _DeckTreeNodeLike | None, deck_id: int | None
) -> DeckLaunchStats:
    """Honest due/total counts for one format tile.

    Deliberately uses ``DeckTreeNode``'s *uncapped, without-children*
    counters (``total_in_deck``, ``*_uncapped``, ``intraday_learning``) —
    never the aggregated parent counters — so e.g. the "Multiple Choice"
    tile (deck ``ReadyMCAT``) never silently counts its ``Free Response`` /
    ``Passages`` / ``Passages::CARS`` children, and "Passage Sets"
    (``ReadyMCAT::Passages``) never counts its ``CARS`` child. Also
    deliberately ignores each deck's daily new/review limits: a launcher
    tile should say what's genuinely available to study, not what today's
    cap happens to allow.
    """
    if deck_id is None or node is None:
        return DeckLaunchStats(deck_id=deck_id, present=False, due=0, total=0)
    due = (
        node.new_uncapped
        + node.review_uncapped
        + node.intraday_learning
        + node.interday_learning_uncapped
    )
    return DeckLaunchStats(
        deck_id=deck_id, present=True, due=due, total=node.total_in_deck
    )


def compute_streak_days(review_day_numbers: set[int] | list[int], today: int) -> int:
    """Consecutive-day study streak ending at ``today``.

    ``review_day_numbers`` is the set of "days elapsed since collection
    creation" (``col.sched.today`` epoch) on which at least one review was
    logged. A day with zero reviews breaks the streak immediately — no
    grace days. If today has no reviews *yet*, the streak is measured
    through yesterday (a live streak survives until today's rollover
    passes without a review); if yesterday is also empty, the streak is
    honestly zero.
    """
    days = set(review_day_numbers)
    if not days:
        return 0
    cursor = today if today in days else today - 1
    if cursor not in days:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= 1
    return streak


def compute_accuracy(pass_count: int, total_count: int) -> float | None:
    """Fraction of graded reviews that were not "Again", or ``None`` when
    there is no evidence in the window (never a fabricated 0% or 100%)."""
    if total_count <= 0:
        return None
    return pass_count / total_count


def day_number_for_revlog_id(revlog_id: int, day_cutoff_secs: int, today: int) -> int:
    """Map a revlog row's ``id`` (epoch ms) to a "days elapsed" bucket
    comparable with ``col.sched.today``, using the same day-cutoff boundary
    the scheduler itself uses for "today"."""
    cutoff_ms = day_cutoff_secs * 1000
    days_ago = (cutoff_ms - revlog_id) // MS_PER_DAY
    return today - int(days_ago)


def summarize_progress(
    revlog_rows: list[tuple[int, int]],
    today: int,
    day_cutoff_secs: int,
) -> dict[str, Any]:
    """Build the "overall progress" figures from raw ``(id, ease)`` revlog rows.

    Kept separate from any DB/collection access so it is trivially unit
    testable with synthetic rows.
    """
    review_day_numbers: set[int] = set()
    last_window_pass = 0
    last_window_total = 0
    window_start_ms = (day_cutoff_secs - ACCURACY_WINDOW_DAYS * 86400) * 1000

    for revlog_id, ease in revlog_rows:
        review_day_numbers.add(day_number_for_revlog_id(revlog_id, day_cutoff_secs, today))
        if revlog_id >= window_start_ms:
            last_window_total += 1
            if ease and ease > 1:
                last_window_pass += 1

    active_days_this_week = sum(
        1 for d in review_day_numbers if 0 <= today - d < ACCURACY_WINDOW_DAYS
    )

    return {
        "streakDays": compute_streak_days(review_day_numbers, today),
        "activeDaysThisWeek": active_days_this_week,
        "reviewsLast7d": last_window_total,
        "accuracy7d": compute_accuracy(last_window_pass, last_window_total),
    }


# Default tile -> deck name mapping. Kept in sync with build_question_bank.py's
# MCQ_DECK_NAME / FR_DECK_NAME / PASSAGE_DECK_NAME / CARS_PASSAGE_DECK_NAME by
# the caller (``qt/aqt/readymcat_home.py``), which loads that module and
# passes the real constants in — this module stays dependency-free.
def default_deck_names(bank_module: Any) -> dict[str, str]:
    return {
        "mcq": bank_module.MCQ_DECK_NAME,
        "fr": bank_module.FR_DECK_NAME,
        "passage": bank_module.PASSAGE_DECK_NAME,
        "cars": bank_module.CARS_PASSAGE_DECK_NAME,
    }


def summarize_home_status(col: Any, deck_names: dict[str, str]) -> dict[str, Any]:
    """Build the JSON payload served as ``readymcatHomeStatus``.

    ``col`` is a real (or test) ``anki.collection.Collection``. ``deck_names``
    maps tile key ("mcq" | "fr" | "passage" | "cars") to the deck name to
    look up. Every number is a live read off the collection — nothing here
    is invented, and a format with no deck yet honestly reports
    ``present: False`` rather than a fabricated zero.
    """
    tree = col.decks.deck_tree()
    decks: dict[str, Any] = {}
    for key, name in deck_names.items():
        did = col.decks.id_for_name(name)
        node = find_deck_node(tree, did) if did else None
        decks[key] = deck_launch_stats(node, did).as_dict()

    today = col.sched.today
    day_cutoff = col.sched.day_cutoff
    revlog_rows = col.db.all("select id, ease from revlog")
    progress = summarize_progress(revlog_rows, today, day_cutoff)
    progress["cardsStudied"] = int(
        col.db.scalar("select count(distinct cid) from revlog") or 0
    )

    diagnostic = col._backend.get_diagnostic_prior()

    return {
        "decks": decks,
        "progress": progress,
        "diagnostic": {
            "taken": bool(diagnostic.present),
            "takenAt": int(diagnostic.taken_at) if diagnostic.present else None,
        },
    }


# --- one-tap review launch ---------------------------------------------------

# Only "mcq" (parents Free Response / Passages / Passages::CARS) and
# "passage" (parents Passages::CARS) have nested children that a native
# per-deck review would otherwise pull in; "fr" and "cars" are leaves.
_KEYS_WITH_NESTED_CHILDREN = {"mcq", "passage"}


def isolating_search_for(deck_names: dict[str, str], key: str) -> str | None:
    """Search string that matches exactly one format's cards, excluding any
    nested child deck — or ``None`` when the deck is already a leaf and a
    plain deck selection is isolated on its own.

    ``deck_names`` must contain "mcq", "fr", "passage" and "cars" (see
    :func:`default_deck_names`). Kept as a pure string builder so the exact
    query used to isolate a tile's review session is unit-testable without a
    live filtered deck.
    """
    if key == "mcq":
        name = deck_names["mcq"]
        return f'deck:"{name}" -deck:"{name}::*"'
    if key == "passage":
        return f'deck:"{deck_names["passage"]}" -deck:"{deck_names["cars"]}"'
    return None


# --- launch routing (pure decision logic) -----------------------------------


def should_open_diagnostic_on_launch(
    diagnostic_already_taken: bool,
    quiz_available: bool,
    skip_diagnostic: bool,
) -> bool:
    """Decide, once per launch, whether the diagnostic should be shown.

    True only for a genuinely first-time student: the diagnostic hasn't
    been taken yet, a question bank is actually available, and the
    dev/e2e escape hatch isn't set. Every other launch — including one
    where the bank simply isn't available — routes to the home hub instead
    (see ``should_open_home_on_launch``), so exactly one of the two ever
    auto-opens."""
    if skip_diagnostic:
        return False
    return (not diagnostic_already_taken) and quiz_available


def should_open_home_on_launch(
    diagnostic_already_taken: bool,
    quiz_available: bool,
    skip_diagnostic: bool,
) -> bool:
    """The complement of ``should_open_diagnostic_on_launch``: every launch
    that doesn't route to the diagnostic opens the home hub instead, so the
    student always lands somewhere useful and the two auto-opens never
    double-open together."""
    return not should_open_diagnostic_on_launch(
        diagnostic_already_taken, quiz_available, skip_diagnostic
    )
