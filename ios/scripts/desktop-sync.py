# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
#
# Headless "desktop" sync client for the round-trip proof. This IS the desktop
# engine: it uses the same pylib Collection API (anki.collection.Collection) the
# Qt app drives, against a throwaway collection directory, and syncs with Anki's
# OWN protocol (sync_login -> sync_collection -> full_upload_or_download). No
# custom sync logic. Run it via ios/scripts/verify-sync.sh, which sets PYTHONPATH
# to the built pylib and points it at the self-hosted server.
#
# It prints a single JSON line to stdout describing what happened plus the
# revlog fingerprint (count + id list) so the caller can prove no review was lost
# or double-counted.

from __future__ import annotations

import argparse
import json
import os
import sys

from anki.collection import Collection
from anki.scheduler.v3 import CardAnswer

# anki.sync_pb2.SyncCollectionResponse.ChangesRequired
NO_CHANGES, NORMAL_SYNC, FULL_SYNC, FULL_DOWNLOAD, FULL_UPLOAD = 0, 1, 2, 3, 4


def revlog_fingerprint(path: str) -> dict:
    """Open the collection fresh and read the revlog, so the count reflects a
    fully-committed on-disk state (important right after a full download)."""
    col = Collection(path)
    try:
        ids = col.db.list("select id from revlog order by id")
        cards = col.db.scalar("select count() from cards")
        notes = col.db.scalar("select count() from notes")
        return {
            "revlog_count": len(ids),
            "revlog_unique": len(set(ids)),
            "revlog_ids": ids,
            "cards": cards,
            "notes": notes,
        }
    finally:
        col.close()


def do_sync(col: Collection, auth, prefer_upload: bool) -> str:
    out = col.sync_collection(auth, sync_media=False)
    required = out.required
    if required in (NO_CHANGES, NORMAL_SYNC):
        return "up to date" if required == NO_CHANGES else "normal sync"
    if required == FULL_UPLOAD:
        col.full_upload_or_download(auth=auth, server_usn=None, upload=True)
        return "full upload"
    if required == FULL_DOWNLOAD:
        col.full_upload_or_download(auth=auth, server_usn=None, upload=False)
        return "full download"
    # FULL_SYNC: both sides diverged; resolve by the caller's preference.
    col.full_upload_or_download(auth=auth, server_usn=None, upload=prefer_upload)
    return "full sync -> %s" % ("upload" if prefer_upload else "download")


def do_review(col: Collection, target: int) -> int:
    """Grade up to `target` due cards Good across every deck (mirrors the phone's
    autoReview). Uses the shared v3 scheduler, producing real revlog rows."""
    graded = 0
    for nid in col.decks.all_names_and_ids(include_filtered=False):
        if graded >= target:
            break
        col.decks.set_current(nid.id)
        while graded < target:
            card = col.sched.getCard()
            if card is None:
                break
            states = col._backend.get_scheduling_states(card.id)
            answer = col.sched.build_answer(
                card=card, states=states, rating=CardAnswer.GOOD
            )
            col.sched.answer_card(answer)
            graded += 1
    return graded


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="throwaway collection directory")
    p.add_argument("--endpoint", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument(
        "--action",
        required=True,
        choices=["sync", "review", "review_sync", "full_upload", "full_download", "count"],
    )
    p.add_argument("--review", type=int, default=0)
    p.add_argument("--full", choices=["upload", "download"], default="upload")
    args = p.parse_args()

    os.makedirs(args.base, exist_ok=True)
    col_path = os.path.join(args.base, "collection.anki2")

    result = {"ok": True, "action": args.action, "steps": [], "reviewed": 0, "error": None}

    if args.action == "count":
        result.update(revlog_fingerprint(col_path))
        print(json.dumps(result))
        return 0

    col = Collection(col_path)
    prefer_upload = args.full == "upload"
    try:
        auth = None

        def authed():
            nonlocal auth
            if auth is None:
                auth = col.sync_login(args.user, args.password, args.endpoint or None)
                result["steps"].append("login ok")
            return auth

        if args.action == "sync":
            result["steps"].append("sync: " + do_sync(col, authed(), prefer_upload))
        elif args.action == "full_upload":
            col.full_upload_or_download(auth=authed(), server_usn=None, upload=True)
            result["steps"].append("full upload")
        elif args.action == "full_download":
            col.full_upload_or_download(auth=authed(), server_usn=None, upload=False)
            result["steps"].append("full download")
        elif args.action == "review":
            result["reviewed"] = do_review(col, args.review)
            result["steps"].append("reviewed %d" % result["reviewed"])
        elif args.action == "review_sync":
            result["steps"].append("pre-sync: " + do_sync(col, authed(), prefer_upload))
            result["reviewed"] = do_review(col, args.review)
            result["steps"].append("reviewed %d" % result["reviewed"])
            result["steps"].append("post-sync: " + do_sync(col, authed(), prefer_upload))
    except Exception as e:  # noqa: BLE001 - report any failure as JSON
        result["ok"] = False
        result["error"] = "%s: %s" % (type(e).__name__, e)
    finally:
        col.close()

    # Reopen fresh to report the committed revlog fingerprint.
    try:
        result.update(revlog_fingerprint(col_path))
    except Exception as e:  # noqa: BLE001
        result["ok"] = False
        result["error"] = (result["error"] or "") + " | fingerprint: %s" % e

    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
