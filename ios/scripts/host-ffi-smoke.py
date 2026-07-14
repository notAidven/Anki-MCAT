#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
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
import anki.collection_pb2 as collection_pb2  # noqa: E402
import anki.decks_pb2 as decks_pb2  # noqa: E402
import anki.notes_pb2 as notes_pb2  # noqa: E402
import anki.points_at_stake_pb2 as pas_pb2  # noqa: E402
import anki.scheduler_pb2 as sched_pb2  # noqa: E402
import anki.diagnostic_pb2 as diag_pb2  # noqa: E402

# Indices copied verbatim from AnkiEngine.swift (which took them from the
# generated out/pylib/anki/_backend_generated.py).
DECKS, M_DECK_TREE, M_SET_CURRENT = 7, 4, 22
M_GET_OR_CREATE_FILTERED, M_ADD_OR_UPDATE_FILTERED = 19, 20  # DecksService
SCHED, M_GET_QUEUED, M_ANSWER = 13, 3, 4
M_EMPTY_FILTERED, M_REBUILD_FILTERED = 15, 16  # BackendSchedulerService
NOTES, M_GET_NOTE = 25, 6
POINTS, M_POINTS = 45, 0
DIAG, M_DIAG_QUIZ = 29, 0

# Canonical ReadyMCAT deck layout (build_question_bank.py; synced to the phone).
MCQ_DECK = "ReadyMCAT"
FR_DECK = "ReadyMCAT::Free Response"
PASSAGE_DECK = "ReadyMCAT::Passages"
CARS_DECK = "ReadyMCAT::Passages::CARS"
MCQ_NOTETYPE = "ReadyMCAT MCQ"
# The isolating search AppModel.isolatingSearch builds for MCQ study.
MCQ_ISOLATING_SEARCH = f'deck:"{MCQ_DECK}" -deck:"{MCQ_DECK}::*"'


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

    # 1. deck tree (7/4) -> the four canonical format decks with due counts.
    #    total_in_deck is child-EXCLUDING, so the MCQ tile (top-level ReadyMCAT,
    #    parent of FR/Passages/CARS) reports only its direct MCQ cards, and the
    #    Passages tile never counts its CARS child (mirrors Content.swift).
    tree = decks_pb2.DeckTreeNode()
    tree.ParseFromString(run(DECKS, M_DECK_TREE, decks_pb2.DeckTreeRequest(now=int(time.time()))))
    counts = {}
    for name in [MCQ_DECK, FR_DECK, PASSAGE_DECK, CARS_DECK]:
        node = find_deck(tree, name)
        assert node is not None, f"deck not found: {name}"
        due = (node.new_uncapped + node.review_uncapped + node.intraday_learning
               + node.interday_learning_uncapped)
        counts[name] = (due, node.total_in_deck)
    print("[1] deck_tree OK:", counts)
    # The MCQ tile's total must be the 414 DIRECT MCQ cards (no double-count of
    # the FR/Passages/CARS children), and Passages must exclude its CARS child.
    mcq_total = counts[MCQ_DECK][1]
    n_mcq_notes = len(col.find_notes(f'note:"{MCQ_NOTETYPE}"'))
    assert mcq_total == n_mcq_notes, (
        f"MCQ tile total {mcq_total} != {n_mcq_notes} MCQ notes (child-excluding count wrong)")
    assert counts[PASSAGE_DECK][1] == len(
        col.find_cards(f'deck:"{PASSAGE_DECK}" -deck:"{CARS_DECK}"')
    ), "Passages tile total must exclude the CARS child"

    # 1b. MCQ study isolation: build the reused launcher filtered deck exactly as
    #     AppModel.studyDeckId does — GetOrCreateFilteredDeck (7/19) -> set one
    #     DUE-ordered search term + reschedule -> AddOrUpdateFilteredDeck (7/20)
    #     -> RebuildFilteredDeck (13/16) — and prove it holds ONLY the MCQ cards,
    #     so studying MCQ never pulls in a nested FR/Passage/CARS sibling.
    fd = decks_pb2.FilteredDeckForUpdate()
    fd.ParseFromString(run(DECKS, M_GET_OR_CREATE_FILTERED, decks_pb2.DeckId(did=0)))
    fd.name = "ReadyMCAT Launcher (smoke)"
    fd.config.reschedule = True
    del fd.config.search_terms[:]
    term = fd.config.search_terms.add()
    term.search = MCQ_ISOLATING_SEARCH
    term.limit = 9999
    term.order = decks_pb2.Deck.Filtered.SearchTerm.DUE
    op = collection_pb2.OpChangesWithId()
    op.ParseFromString(run(DECKS, M_ADD_OR_UPDATE_FILTERED, fd))
    launcher_id = op.id
    run(SCHED, M_REBUILD_FILTERED, decks_pb2.DeckId(did=launcher_id))
    launcher_cids = list(col.decks.cids(launcher_id))
    assert len(launcher_cids) == n_mcq_notes, (
        f"launcher holds {len(launcher_cids)} cards, expected {n_mcq_notes} MCQ cards")
    non_mcq = [c for c in launcher_cids
               if c not in set(col.find_cards(f'note:"{MCQ_NOTETYPE}"'))]
    assert not non_mcq, f"launcher pulled in {len(non_mcq)} non-MCQ cards"
    print(f"[1b] MCQ isolation OK: filtered deck holds {len(launcher_cids)} MCQ-only cards")

    # 2. set current deck (7/22) to the isolated launcher + get queued (13/3)
    run(DECKS, M_SET_CURRENT, decks_pb2.DeckId(did=launcher_id))
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

    # 7. empty the launcher filtered deck (13/15) -> cards return to their home
    #    deck, exactly as AppModel.returnLauncherCards does after a session, so
    #    the MCQ tile reads its honest count again.
    run(SCHED, M_EMPTY_FILTERED, decks_pb2.DeckId(did=launcher_id))
    assert not list(col.decks.cids(launcher_id)), "empty_filtered_deck left cards behind"
    print("[7] empty_filtered_deck OK: launcher returned its cards home")

    col.close()
    shutil.rmtree(tmp, ignore_errors=True)
    print("HOST FFI SMOKE OK — all native-app engine indices validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
