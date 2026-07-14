#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Shared helpers for the ReadyMCAT model-evaluation harnesses.

These wrap Anki's REAL Rust engine (the exact code that ships) so the evals
score what the app actually computes, never a re-implementation:

* :class:`FsrsEngine` fits an FSRS memory state from a review history via the
  backend ``compute_memory_state`` RPC and reads back the model's predicted
  recall via the ``extract_fsrs_retrievability`` SQL function — the same
  function the points-at-stake dashboard uses for the Memory score.

Everything runs against a throwaway, in-temp-dir collection; nothing here
touches a real profile.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]


def ensure_anki_importable() -> None:
    """Make ``anki`` importable when run as a plain script from the repo.

    ``anki`` is a NAMESPACE package split across two dirs — source in ``pylib``
    and generated protobuf/bridge modules in ``out/pylib`` — so BOTH must be on
    ``sys.path`` for the package's ``__path__`` to span them. A bare
    ``import anki`` can succeed from ``pylib`` alone yet still be missing the
    generated ``*_pb2`` modules, so we always add both (idempotently) rather
    than early-returning.
    """
    for rel in ("out/pylib", "pylib"):
        path = _REPO_ROOT / rel
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


# A single review in a card's history: days elapsed since the previous review
# (0 for the first) and whether the student recalled it (pass/fail).
class Review:
    __slots__ = ("gap_days", "passed")

    def __init__(self, gap_days: float, passed: bool) -> None:
        self.gap_days = gap_days
        self.passed = passed


class FsrsEngine:
    """Fit FSRS states and read predicted recall through Anki's real engine.

    One throwaway collection with one reusable scratch card; the scratch card's
    revlog is rewritten per prediction. ``predict_next_recall`` returns the
    model's recall probability for the *next* review given only the reviews
    *before* it — i.e. a genuine one-step-ahead (held-out) prediction.
    """

    #: A pass (recall success) is graded Good; a miss is graded Again. Mirrors
    #: the reviewer's grading (see rslib PERFORMANCE_HIT_MIN_EASE / the demo
    #: seeder), so the fitted state matches what the app would learn.
    EASE_PASS = 3
    EASE_FAIL = 1

    def __init__(self) -> None:
        ensure_anki_importable()
        from anki.collection import Collection
        from anki.consts import CARD_TYPE_REV, QUEUE_TYPE_REV

        self._dir = tempfile.mkdtemp(prefix="readymcat-cal-")
        self.col = Collection(str(Path(self._dir) / "collection.anki2"))
        notetype = self.col.models.by_name("Basic") or self.col.models.all()[0]
        deck_id = self.col.decks.id("ReadyMCAT calibration (scratch)")
        note = self.col.new_note(notetype)
        note.fields[0] = "scratch"
        if len(note.fields) > 1:
            note.fields[1] = "scratch"
        self.col.add_note(note, deck_id)
        self._cid = note.cards()[0].id
        card = self.col.get_card(self._cid)
        card.type = CARD_TYPE_REV
        card.queue = QUEUE_TYPE_REV
        card.ivl = 1
        self.col.update_cards([card], skip_undo_entry=True)
        # A fixed reference "wall clock" the synthetic revlog timestamps hang off.
        self._t0_ms = int(time.time() * 1000) - 400 * 86_400_000

    def close(self) -> None:
        try:
            self.col.close()
        except Exception:
            pass

    # -- internals -----------------------------------------------------------

    def _write_history(self, reviews: list[Review]) -> int:
        """Replace the scratch card's revlog with ``reviews`` and return the
        wall-clock (seconds) of the LAST review, so a follow-up prediction can
        be dated relative to it. Revlog ids double as ms timestamps and must be
        strictly increasing, so cumulative gaps drive the ids."""
        self.col.db.execute("delete from revlog where cid = ?", self._cid)
        rows = []
        cum_days = 0.0
        prev_ivl = 1
        last_ms = self._t0_ms
        for i, rv in enumerate(reviews):
            cum_days += rv.gap_days
            rid = self._t0_ms + int(round(cum_days * 86_400_000)) + i
            ease = self.EASE_PASS if rv.passed else self.EASE_FAIL
            ivl = max(1, int(round(rv.gap_days)) or prev_ivl)
            rows.append((rid, self._cid, 0, ease, ivl, prev_ivl, 2500, 8000, 1))
            prev_ivl = ivl
            last_ms = rid
        self.col.db.executemany(
            "insert into revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        return last_ms // 1000

    def fit_state(self, reviews: list[Review]) -> Optional[tuple[float, float, float]]:
        """Fit an FSRS memory state from ``reviews`` via the real backend.

        Returns ``(stability, difficulty, decay)`` or ``None`` if the engine
        produced no state (e.g. too little history)."""
        self._write_history(reviews)
        resp = self.col._backend.compute_memory_state(self._cid)
        if not resp.state or resp.state.stability <= 0:
            return None
        return (resp.state.stability, resp.state.difficulty, resp.decay)

    def recall_at(
        self, state: tuple[float, float, float], last_review_secs: int, gap_days: float
    ) -> Optional[float]:
        """The model's predicted recall ``gap_days`` after ``last_review_secs``,
        computed by Anki's ``extract_fsrs_retrievability`` SQL function (the same
        the dashboard's Memory score uses)."""
        from anki.cards import FSRSMemoryState

        stability, difficulty, decay = state
        card = self.col.get_card(self._cid)
        card.memory_state = FSRSMemoryState(stability=stability, difficulty=difficulty)
        card.decay = decay
        card.last_review_time = last_review_secs
        self.col.update_cards([card], skip_undo_entry=True)
        data = self.col.db.scalar("select data from cards where id = ?", self._cid)
        now = last_review_secs + int(round(gap_days * 86_400))
        # extract_fsrs_retrievability(data, due, ivl, days_elapsed, next_day_at, now):
        # with last_review_time present in `data`, only `now` matters — it yields
        # R over (now - last_review_time) seconds.
        return self.col.db.scalar(
            "select extract_fsrs_retrievability(?, ?, ?, ?, ?, ?)",
            data,
            0,
            0,
            0,
            0,
            now,
        )

    def predict_next_recall(
        self, prefix: list[Review], next_gap_days: float
    ) -> Optional[float]:
        """One-step-ahead held-out prediction: fit on ``prefix`` (the reviews
        BEFORE the target), then predict recall ``next_gap_days`` later."""
        state = self.fit_state(prefix)
        if state is None:
            return None
        # The last review's wall-clock is the largest revlog id _write_history
        # just wrote (ids are ms timestamps).
        last_ms = self.col.db.scalar(
            "select max(id) from revlog where cid = ?", self._cid
        )
        return self.recall_at(state, int(last_ms) // 1000, next_gap_days)
