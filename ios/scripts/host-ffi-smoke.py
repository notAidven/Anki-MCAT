#!/usr/bin/env python3
# Copyright: ReadyMCAT contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
#
# Host-side FFI smoke test for the NATIVE iOS app's engine calls. It drives the
# SAME backend dispatch the Swift app drives over rsios — Backend
# run_service_method(service, method, protobuf_bytes), exposed in Python as
# `col._backend._run_command(service, method, bytes)` — using the exact
# service/method indices AnkiEngine.swift uses, against a THROWAWAY COPY of the
# bundled collection. It validates every new index (deck tree, set-current-deck,
# get-queued-cards, get-note, answer-card grading, points-at-stake, diagnostic)
# without touching the app, the Simulator, or the user's profile.
#
# Usage:
#   ANKI_PYLIB=/path/to/anki/out/pylib \
#   /path/to/anki/out/pyenv/bin/python ios/scripts/host-ffi-smoke.py
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "ios" / "ReadyMCAT" / "Resources"

import anki.collection as anki_collection  # noqa: E402
import anki.decks_pb2 as decks_pb2  # noqa: E402
import anki.notes_pb2 as notes_pb2  # noqa: E402
import anki.points_at_stake_pb2 as pas_pb2  # noqa: E402
import anki.scheduler_pb2 as sched_pb2  # noqa: E402
import anki.diagnostic_pb2 as diag_pb2  # noqa: E402

# Indices copied verbatim from AnkiEngine.swift (which took them from the
# generated out/pylib/anki/_backend_generated.py).
DECKS, M_DECK_TREE, M_SET_CURRENT = 7, 4, 22
SCHED, M_GET_QUEUED, M_ANSWER = 13, 3, 4
NOTES, M_GET_NOTE = 25, 6
POINTS, M_POINTS = 45, 0
DIAG, M_DIAG_QUIZ = 29, 0


def find_deck(node, name, prefix=""):
    full = node.name if not prefix else f"{prefix}::{node.name}"
    if node.name == "":
        full = ""
    if full == name:
        return node
    for c in node.children:
        hit = find_deck(c, name, full)
        if hit is not None:
            return hit
    return None


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="rmcat-smoke-"))
    shutil.copy(RES / "collection.anki2", tmp / "collection.anki2")
    shutil.copy(RES / "taxonomy.json", tmp / "taxonomy.json")
    shutil.copy(RES / "diagnostic_quiz.json", tmp / "diagnostic_quiz.json")

    col = anki_collection.Collection(str(tmp / "collection.anki2"))
    be = col._backend

    def run(svc, method, msg):
        return be._run_command(svc, method, msg.SerializeToString())

    # 1. deck tree (7/4) -> the four format decks with due counts
    tree = decks_pb2.DeckTreeNode()
    tree.ParseFromString(run(DECKS, M_DECK_TREE, decks_pb2.DeckTreeRequest(now=int(time.time()))))
    counts = {}
    for name in ["ReadyMCAT::Multiple Choice", "ReadyMCAT::Free Response",
                 "ReadyMCAT::Passages", "ReadyMCAT::CARS"]:
        node = find_deck(tree, name)
        assert node is not None, f"deck not found: {name}"
        due = (node.new_uncapped + node.review_uncapped + node.intraday_learning
               + node.interday_learning_uncapped)
        counts[name] = (due, node.total_in_deck)
    print("[1] deck_tree OK:", counts)
    mcq_did = find_deck(tree, "ReadyMCAT::Multiple Choice").deck_id

    # 2. set current deck (7/22) + get queued cards (13/3)
    run(DECKS, M_SET_CURRENT, decks_pb2.DeckId(did=mcq_did))
    q = sched_pb2.QueuedCards()
    q.ParseFromString(run(SCHED, M_GET_QUEUED, sched_pb2.GetQueuedCardsRequest(fetch_limit=10)))
    assert q.cards, "no queued MCQ cards"
    first = q.cards[0]
    print(f"[2] set_current_deck + get_queued_cards OK: new={q.new_count} first_card={first.card.id}")

    # 3. get note (25/6) -> the MCQ fields
    note = notes_pb2.Note()
    note.ParseFromString(run(NOTES, M_GET_NOTE, notes_pb2.NoteId(nid=first.card.note_id)))
    assert len(note.fields) == 10, f"expected 10 MCQ fields, got {len(note.fields)}"
    print(f"[3] get_note OK: 10 fields; Q={note.fields[0][:48]!r} correctIndex={note.fields[5]!r}")

    # 4. answer card (13/4) -> grade Good, echoing the good scheduling state
    before = q.new_count
    ans = sched_pb2.CardAnswer(
        card_id=first.card.id,
        current_state=first.states.current,
        new_state=first.states.good,
        rating=sched_pb2.CardAnswer.GOOD,
        answered_at_millis=int(time.time() * 1000),
        milliseconds_taken=1500,
    )
    run(SCHED, M_ANSWER, ans)
    q2 = sched_pb2.QueuedCards()
    q2.ParseFromString(run(SCHED, M_GET_QUEUED, sched_pb2.GetQueuedCardsRequest(fetch_limit=10)))
    print(f"[4] answer_card OK: graded Good; new {before} -> {q2.new_count}")
    assert q2.cards and q2.cards[0].card.id != first.card.id, "queue did not advance after grading"

    # 5. points-at-stake (45/0) -> the three honest scores + coverage
    pas = pas_pb2.PointsAtStakeResponse()
    pas.ParseFromString(run(POINTS, M_POINTS, pas_pb2.PointsAtStakeRequest(
        taxonomy_path=str(tmp / "taxonomy.json"))))
    print(f"[5] points_at_stake OK: coverage {pas.coverage.categories_covered}/"
          f"{pas.coverage.categories_total}, {len(pas.topics)} topics, "
          f"memory_ready={pas.meets_data_threshold}")
    assert len(pas.topics) > 0, "no topics returned"

    # 6. diagnostic quiz (29/0)
    quiz = diag_pb2.DiagnosticQuiz()
    quiz.ParseFromString(run(DIAG, M_DIAG_QUIZ, diag_pb2.DiagnosticQuizRequest(
        quiz_path=str(tmp / "diagnostic_quiz.json"), mode="short")))
    print(f"[6] get_diagnostic_quiz OK: present={quiz.present}, {len(quiz.items)} items")
    assert quiz.present and quiz.items, "diagnostic quiz empty"

    col.close()
    shutil.rmtree(tmp, ignore_errors=True)
    print("HOST FFI SMOKE OK — all native-app engine indices validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
