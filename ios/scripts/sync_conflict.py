# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
#
# Same-card offline sync-conflict proof. Two independent clients (A and B) — the
# SAME shared Rust sync engine both the desktop app and the iOS app drive — start
# from one synced collection, then BOTH review the SAME card while offline with
# different grades at different times, and sync through a self-hosted
# anki-sync-server. It then verifies the documented conflict rule:
#
#   "the later review by timestamp wins, while the loser's review-log entry is
#    preserved so history is never silently dropped."
#
# This exercises Anki's OWN sync protocol / merge (no custom logic). It is a
# sibling to verify-sync.sh (which proves the two-way, different-card round trip
# with the real iOS Simulator); the same-card MERGE it checks lives in the shared
# engine, so two headless clients test it faithfully and controllably (we can
# target one specific card and order the timestamps).
#
# Prints a single JSON object of evidence + PASS/FAIL to stdout.

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

from anki.collection import Collection
from anki.scheduler.v3 import CardAnswer

NO_CHANGES, NORMAL_SYNC, FULL_SYNC, FULL_DOWNLOAD, FULL_UPLOAD = 0, 1, 2, 3, 4
RATING = {"again": CardAnswer.AGAIN, "good": CardAnswer.GOOD}


def sync(col: Collection, auth, prefer_upload: bool) -> str:
    out = col.sync_collection(auth, sync_media=False)
    req = out.required
    if req == NO_CHANGES:
        return "up-to-date"
    if req == NORMAL_SYNC:
        return "normal"
    if req == FULL_UPLOAD:
        col.full_upload_or_download(auth=auth, server_usn=None, upload=True)
        return "full-upload"
    if req == FULL_DOWNLOAD:
        col.full_upload_or_download(auth=auth, server_usn=None, upload=False)
        return "full-download"
    col.full_upload_or_download(auth=auth, server_usn=None, upload=prefer_upload)
    return "full-%s" % ("upload" if prefer_upload else "download")


def review_card(col: Collection, cid: int, rating: int) -> int:
    """Grade ONE specific card via the shared v3 scheduler (real revlog row)."""
    card = col.get_card(cid)
    card.start_timer()
    col.decks.set_current(card.current_deck_id())
    states = col._backend.get_scheduling_states(cid)
    answer = col.sched.build_answer(card=card, states=states, rating=rating)
    col.sched.answer_card(answer)
    return col.db.scalar("select max(id) from revlog where cid=?", cid)


def card_state(col: Collection, cid: int) -> dict:
    row = col.db.first(
        "select queue,type,ivl,due,reps,lapses,mod from cards where id=?", cid
    )
    q, t, ivl, due, reps, lapses, mod = row
    return {
        "queue": q, "type": t, "ivl": ivl, "due": due,
        "reps": reps, "lapses": lapses, "mod": mod,
    }


def card_revlog(col: Collection, cid: int) -> list[int]:
    return col.db.list("select id from revlog where cid=? order by id", cid)


def all_revlog(col: Collection) -> list[int]:
    return col.db.list("select id from revlog order by id")


def open_login(base: str, endpoint: str, user: str, pw: str):
    col = Collection(os.path.join(base, "collection.anki2"))
    auth = col.sync_login(user, pw, endpoint or None)
    return col, auth


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True)
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--a-base", required=True)
    p.add_argument("--b-base", required=True)
    p.add_argument("--bank", required=True, help="seed collection.anki2 to upload")
    p.add_argument("--evidence", default="")
    args = p.parse_args()

    ev: dict = {"ok": True, "steps": [], "error": None}
    os.makedirs(args.a_base, exist_ok=True)
    os.makedirs(args.b_base, exist_ok=True)

    try:
        # 1. A seeds the server with the bank (full upload), and picks card X.
        shutil.copy(args.bank, os.path.join(args.a_base, "collection.anki2"))
        col, auth = open_login(args.a_base, args.endpoint, args.user, args.password)
        ev["steps"].append("A first sync: " + sync(col, auth, prefer_upload=True))
        cid = col.db.scalar("select id from cards order by id limit 1")
        ev["card_id"] = cid
        col.close()

        # 2. B joins: full download of the same collection.
        col, auth = open_login(args.b_base, args.endpoint, args.user, args.password)
        ev["steps"].append("B first sync: " + sync(col, auth, prefer_upload=False))
        assert col.db.scalar("select count() from cards where id=?", cid) == 1, (
            "card X missing on B after download"
        )
        col.close()

        # 3. OFFLINE: A reviews X GOOD at T1.
        col = Collection(os.path.join(args.a_base, "collection.anki2"))
        r1 = review_card(col, cid, RATING["good"])
        a_offline = card_state(col, cid)
        ev["A_review"] = {"rating": "good", "revlog_id": r1, "state": a_offline}
        col.close()

        # ensure B's review lands a distinct, LATER second (mod is in seconds).
        time.sleep(2.2)

        # 4. OFFLINE: B reviews the SAME card X AGAIN at T2 (> T1).
        col = Collection(os.path.join(args.b_base, "collection.anki2"))
        r2 = review_card(col, cid, RATING["again"])
        b_offline = card_state(col, cid)
        ev["B_review"] = {"rating": "again", "revlog_id": r2, "state": b_offline}
        col.close()

        assert b_offline["mod"] > a_offline["mod"], (
            "B's review must be later by timestamp (mod %s !> %s)"
            % (b_offline["mod"], a_offline["mod"])
        )
        ev["later_by_timestamp"] = "B (again)"

        # 5. Sync dance: A up (Good@T1) -> B merge+up (Again@T2 wins) -> A down.
        col, auth = open_login(args.a_base, args.endpoint, args.user, args.password)
        ev["steps"].append("A sync (push Good@T1): " + sync(col, auth, True))
        col.close()
        col, auth = open_login(args.b_base, args.endpoint, args.user, args.password)
        ev["steps"].append("B sync (merge, push Again@T2): " + sync(col, auth, True))
        col.close()
        col, auth = open_login(args.a_base, args.endpoint, args.user, args.password)
        ev["steps"].append("A sync (pull merged): " + sync(col, auth, False))
        col.close()

        # 6. Read final converged state on both sides.
        colA = Collection(os.path.join(args.a_base, "collection.anki2"))
        colB = Collection(os.path.join(args.b_base, "collection.anki2"))
        finalA, finalB = card_state(colA, cid), card_state(colB, cid)
        revA_card, revB_card = card_revlog(colA, cid), card_revlog(colB, cid)
        revA_all, revB_all = all_revlog(colA), all_revlog(colB)
        colA.close()
        colB.close()

        ev["final_A"] = finalA
        ev["final_B"] = finalB
        ev["card_revlog_A"] = revA_card
        ev["card_revlog_B"] = revB_card

        # 7. Assertions.
        def sched_sig(s: dict) -> tuple:
            return (s["queue"], s["type"], s["ivl"], s["reps"], s["lapses"], s["mod"])

        checks = {
            # loser's (A's Good) revlog row survives, and so does the winner's.
            "loser_revlog_preserved": (r1 in revA_card and r1 in revB_card),
            "winner_revlog_present": (r2 in revA_card and r2 in revB_card),
            "both_revlog_rows_on_card": sorted(revA_card) == sorted(revB_card) == sorted({r1, r2} | set(revA_card)),
            # devices converge to one identical card record.
            "card_converged": sched_sig(finalA) == sched_sig(finalB),
            # the winner is the LATER review by timestamp (B's Again@T2),
            # NOT A's earlier Good — i.e. winner-by-timestamp, history kept.
            "winner_is_later_timestamp": sched_sig(finalA) == sched_sig(b_offline),
            "loser_state_not_final": sched_sig(finalA) != sched_sig(a_offline),
            # whole-collection revlog id sets identical (no loss/double-count).
            "revlog_sets_identical": revA_all == revB_all,
            "both_rows_in_collection": (r1 in revA_all and r2 in revA_all),
        }
        ev["checks"] = checks
        ev["ok"] = all(checks.values())
        ev["revlog_total"] = len(revA_all)
    except Exception as e:  # noqa: BLE001
        ev["ok"] = False
        ev["error"] = "%s: %s" % (type(e).__name__, e)
        import traceback

        ev["traceback"] = traceback.format_exc()

    text = json.dumps(ev, indent=4)
    print(text)
    if args.evidence:
        os.makedirs(os.path.dirname(args.evidence) or ".", exist_ok=True)
        with open(args.evidence, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0 if ev["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
