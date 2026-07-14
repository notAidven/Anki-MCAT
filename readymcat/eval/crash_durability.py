#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Crash / durability test — kill the engine mid-review N times on a THROWAWAY
profile and confirm no data corruption and no lost (committed) reviews.

The Sunday rubric (§7g/§10) asks that killing the app mid-review many times
leaves the collection intact. This drives the SAME engine the app uses
(`anki.collection.Collection` over the shared Rust backend + SQLite) on a
DISPOSABLE copy of the bundled bank, never a real profile:

  for i in 1..N:
    * spawn a worker that reviews cards in a tight loop, committing each review
      (`col.save()`) and appending the committed revlog count to a fsync'd
      checkpoint file;
    * SIGKILL it at a random moment (often mid-write);
    * reopen the collection and assert:
        - SQLite `pragma integrity_check` == "ok"     (no corruption)
        - Anki `check_database` reports no problems    (engine-level integrity)
        - revlog count >= the last committed checkpoint (no committed review lost)
        - revlog count is monotonic across kills       (nothing ever disappears)

SIGKILL (not SIGTERM) gives the process no chance to clean up — the exact
"pulled the plug mid-review" case. Durability then rests on SQLite's atomic
commit (WAL/rollback-journal): a committed review survives; an in-flight,
uncommitted one may be dropped (correct) but never corrupts the file.

Safety: everything runs in a fresh temp dir; the user's real "User 1" profile is
never opened or touched.

Run: `just crash-test`  (or: PYTHONPATH=out/pylib out/pyenv/bin/python \
      readymcat/eval/crash_durability.py --kills 20)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BANK = _REPO_ROOT / "ios" / "ReadyMCAT" / "Resources" / "collection.anki2"


# ---------------------------------------------------------------------------
# Worker: review in a tight loop, committing + checkpointing each review, until
# it is killed. Invoked as a subprocess (`--worker`).
# ---------------------------------------------------------------------------


def run_worker(col_path: str, checkpoint_path: str) -> int:
    from anki.collection import Collection
    from anki.scheduler.v3 import CardAnswer

    col = Collection(col_path)
    ck = open(checkpoint_path, "a", encoding="utf-8")
    deck_ids = [d.id for d in col.decks.all_names_and_ids(include_filtered=False)]
    random.shuffle(deck_ids)
    di = 0
    try:
        while True:
            card = None
            # find a deck with a due/new card
            for _ in range(len(deck_ids)):
                col.decks.set_current(deck_ids[di % len(deck_ids)])
                di += 1
                card = col.sched.getCard()
                if card is not None:
                    break
            if card is None:
                # nothing left to review anywhere; keep the process alive so the
                # driver's SIGKILL still lands on a live (idle) engine.
                time.sleep(0.05)
                continue
            states = col._backend.get_scheduling_states(card.id)
            answer = col.sched.build_answer(
                card=card, states=states, rating=CardAnswer.GOOD
            )
            col.sched.answer_card(answer)
            col.save()  # commit this review durably to SQLite
            n = col.db.scalar("select count() from revlog")
            ck.write(f"{n}\n")
            ck.flush()
            os.fsync(ck.fileno())
    finally:  # pragma: no cover - usually killed before reaching here
        try:
            col.close()
        except Exception:
            pass
    return 0


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _max_checkpoint(path: str) -> int:
    try:
        vals = [int(x) for x in Path(path).read_text().split() if x.strip()]
        return max(vals) if vals else 0
    except Exception:
        return 0


def reopen_and_check(col_path: str) -> dict:
    """Reopen the (possibly just-killed) collection and check integrity."""
    from anki.collection import Collection

    col = Collection(col_path)
    try:
        integrity = col.db.scalar("pragma integrity_check")
        revlog = col.db.scalar("select count() from revlog")
        cards = col.db.scalar("select count() from cards")
        # engine-level check (card/note/deck consistency)
        try:
            problems = list(col._backend.check_database())
        except Exception as e:  # noqa: BLE001
            problems = [f"check_database raised: {e}"]
        return {
            "integrity": integrity,
            "revlog": int(revlog),
            "cards": int(cards),
            "db_problems": problems,
        }
    finally:
        col.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, metavar=("COL", "CKPT"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--kills", type=int, default=20)
    parser.add_argument("--bank", default=str(DEFAULT_BANK))
    parser.add_argument("--json", default=str(_REPO_ROOT / "readymcat" / "eval" / "crash_durability.json"))
    parser.add_argument("--seed", type=int, default=20260703)
    args = parser.parse_args(argv)

    if args.worker:
        return run_worker(args.worker[0], args.worker[1])

    rng = random.Random(args.seed)
    bank = Path(args.bank)
    if not bank.exists():
        print(f"error: bank not found: {bank}", file=sys.stderr)
        return 2

    # THROWAWAY profile — never the user's real Anki2/User 1.
    work = Path(_REPO_ROOT / "out" / "crash-durability")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    col_path = str(work / "collection.anki2")
    ckpt_path = str(work / "committed.log")
    shutil.copy(bank, col_path)
    # copy taxonomy sidecar too (harmless if unused)
    for side in ("taxonomy.json",):
        src = bank.parent / side
        if src.exists():
            shutil.copy(src, work / side)
    Path(ckpt_path).write_text("", encoding="utf-8")

    print(f"Crash/durability test — THROWAWAY profile at {work}")
    print(f"bank: {bank.name}   kills: {args.kills}\n")

    iterations = []
    prev_revlog = 0
    corruption = 0
    lost = 0
    for i in range(args.kills):
        proc = subprocess.Popen(
            [sys.executable, __file__, "--worker", col_path, ckpt_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": os.environ.get("PYTHONPATH", "")},
        )
        # let it review for a random slice, then pull the plug (SIGKILL).
        time.sleep(rng.uniform(0.35, 1.4))
        proc.send_signal(signal.SIGKILL)
        proc.wait()

        chk = reopen_and_check(col_path)
        committed = _max_checkpoint(ckpt_path)
        ok_integrity = chk["integrity"] == "ok"
        no_db_problems = not chk["db_problems"]
        no_lost = chk["revlog"] >= committed and chk["revlog"] >= prev_revlog
        if not ok_integrity or not no_db_problems:
            corruption += 1
        if not no_lost:
            lost += 1
        iterations.append({
            "kill": i + 1,
            "integrity": chk["integrity"],
            "db_problems": chk["db_problems"],
            "revlog_after": chk["revlog"],
            "committed_checkpoint": committed,
            "monotonic": chk["revlog"] >= prev_revlog,
            "no_committed_review_lost": chk["revlog"] >= committed,
        })
        status = "ok" if (ok_integrity and no_db_problems and no_lost) else "PROBLEM"
        print(f"  kill {i+1:2d}: integrity={chk['integrity']:<3} "
              f"revlog={chk['revlog']:<5} committed>={committed:<5} "
              f"cards={chk['cards']} problems={len(chk['db_problems'])}  [{status}]")
        prev_revlog = max(prev_revlog, chk["revlog"])

    passed = corruption == 0 and lost == 0
    result = {
        "source": "SIGKILL x N on a throwaway copy of the bundled bank (real engine)",
        "kills": args.kills,
        "bank": bank.name,
        "final_revlog": prev_revlog,
        "corruption_events": corruption,
        "lost_review_events": lost,
        "passed": passed,
        "iterations": iterations,
    }
    Path(args.json).write_text(json.dumps(result, indent=4) + "\n", encoding="utf-8")

    print(f"\n{args.kills} hard kills — corruption events: {corruption}, "
          f"lost-committed-review events: {lost}")
    print(f"final revlog rows: {prev_revlog}")
    print(f"integrity check: {'ALL OK (no corruption, no lost reviews)' if passed else 'FAILED'}")
    print(f"wrote {args.json}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
