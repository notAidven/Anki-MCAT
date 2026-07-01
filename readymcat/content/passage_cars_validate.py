#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Self-contained validator for the ReadyMCAT CARS passage bank.

No third-party dependencies. Verifies that ``passage_cars.json`` conforms to
the ReadyMCAT CARS schema and to the sourcing rules from the PRD/assignment:

  1. The file is valid JSON and a non-empty array of passage sets.
  2. Each set has: a unique ``id`` (``psg-cars-<n>``), ``section == "CARS"``,
     a non-empty ``passage`` string, a ``passage_source`` whose ``license`` is
     public-domain / openly-licensed / original, and **>= 5 questions**.
  3. Each question has: a unique id, ``aamc_category == "CARS"``, a valid
     ``skill``/``difficulty``, exactly 4 unique non-empty ``options``, a
     ``correct_index`` that is in range, a non-empty ``explanation``, and a
     2-3 rung teach-on-miss ``subquestions`` ladder whose every rung has
     ``options`` + an in-range ``correct_index`` + an ``explanation``.

Usage:
    python3 passage_cars_validate.py [--file PATH]

Exits 0 on success, 1 on any validation failure. Always prints a report
(passage/question counts, skill + difficulty spread, per-passage word counts,
and the licenses seen) so gaps are visible even when everything passes.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

ID_RE = re.compile(r"^psg-cars-\d+$")
QID_RE = re.compile(r"^psg-cars-\d+-q\d+$")

ALLOWED_SKILLS = {"comprehension", "reasoning-within", "reasoning-beyond"}
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}

# Passage length: the MCAT CARS target is ~500-600 words. We hard-fail only on
# clearly-wrong lengths and warn on the soft band, so a slightly long/short
# adapted excerpt is reported but not rejected.
WORD_MIN_HARD = 350
WORD_MAX_HARD = 800
WORD_MIN_SOFT = 480
WORD_MAX_SOFT = 680

# A license string is acceptable if it is public-domain, an open CC license, or
# explicitly original. Substring match keeps it robust to version suffixes
# (e.g. "CC BY-SA 4.0") and phrasing (e.g. "public domain (Project Gutenberg)").
_OPEN_LICENSE_MARKERS = ("public domain", "cc0", "cc by", "creative commons", "open")


def is_open_license(text: str) -> bool:
    if not isinstance(text, str):
        return False
    t = text.strip().lower()
    if t == "original":
        return True
    return any(marker in t for marker in _OPEN_LICENSE_MARKERS)


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def check_subquestions(errors: list[str], qloc: str, subs) -> None:
    if not isinstance(subs, list):
        fail(errors, f"[{qloc}] 'subquestions' must be a list.")
        return
    if not (2 <= len(subs) <= 3):
        fail(errors, f"[{qloc}] teach-on-miss ladder must have 2-3 rungs, found {len(subs)}.")
    for j, sub in enumerate(subs):
        sloc = f"{qloc}.sub[{j}]"
        if not isinstance(sub, dict):
            fail(errors, f"[{sloc}] rung is not an object.")
            continue
        if not sub.get("stem"):
            fail(errors, f"[{sloc}] missing/empty 'stem'.")
        opts = sub.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            fail(errors, f"[{sloc}] 'options' must be a list of >= 2 choices.")
            opts = opts if isinstance(opts, list) else []
        if any((not isinstance(o, str) or not o.strip()) for o in opts):
            fail(errors, f"[{sloc}] has an empty option.")
        if len(set(opts)) != len(opts):
            fail(errors, f"[{sloc}] options are not unique.")
        ci = sub.get("correct_index")
        if not isinstance(ci, int) or isinstance(ci, bool) or not (0 <= ci < len(opts)):
            fail(errors, f"[{sloc}] correct_index {ci!r} out of range for {len(opts)} options.")
        if not sub.get("explanation"):
            fail(errors, f"[{sloc}] missing/empty 'explanation'.")


def check_question(errors: list[str], ploc: str, q, seen_qids: set[str]) -> str | None:
    qid = q.get("id")
    qloc = qid if qid else f"{ploc}.q?"
    if not qid or not QID_RE.match(str(qid)):
        fail(errors, f"[{qloc}] question id missing or not of form 'psg-cars-<n>-q<k>'.")
    if qid in seen_qids:
        fail(errors, f"[{qloc}] duplicate question id.")
    if qid:
        seen_qids.add(qid)

    if q.get("aamc_category") != "CARS":
        fail(errors, f"[{qloc}] aamc_category must be 'CARS'.")
    skill = q.get("skill")
    if skill not in ALLOWED_SKILLS:
        fail(errors, f"[{qloc}] skill {skill!r} not in {sorted(ALLOWED_SKILLS)}.")
    if not q.get("stem"):
        fail(errors, f"[{qloc}] missing/empty 'stem'.")

    options = q.get("options")
    if not isinstance(options, list) or len(options) != 4:
        n = len(options) if isinstance(options, list) else "n/a"
        fail(errors, f"[{qloc}] expected exactly 4 options, found {n}.")
        options = options if isinstance(options, list) else []
    if any((not isinstance(o, str) or not o.strip()) for o in options):
        fail(errors, f"[{qloc}] has an empty option.")
    if len(set(options)) != len(options):
        fail(errors, f"[{qloc}] options are not unique.")

    ci = q.get("correct_index")
    if not isinstance(ci, int) or isinstance(ci, bool) or not (0 <= ci < len(options)):
        fail(errors, f"[{qloc}] correct_index {ci!r} out of range for {len(options)} options.")

    if not q.get("explanation"):
        fail(errors, f"[{qloc}] missing/empty 'explanation'.")
    if q.get("difficulty") not in ALLOWED_DIFFICULTY:
        fail(errors, f"[{qloc}] difficulty {q.get('difficulty')!r} not in {sorted(ALLOWED_DIFFICULTY)}.")

    check_subquestions(errors, qloc, q.get("subquestions"))
    return skill if skill in ALLOWED_SKILLS else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=os.path.join(HERE, "passage_cars.json"))
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    try:
        with open(args.file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(f"FAILED: file not found: {args.file}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAILED: {args.file} is not valid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, list) or not data:
        print("FAILED: top-level JSON must be a non-empty array of passage sets.", file=sys.stderr)
        return 1

    seen_pids: set[str] = set()
    seen_qids: set[str] = set()
    skill_counts: collections.Counter[str] = collections.Counter()
    diff_counts: collections.Counter[str] = collections.Counter()
    license_counts: collections.Counter[str] = collections.Counter()
    total_questions = 0
    word_report: list[tuple[str, int]] = []

    for idx, p in enumerate(data):
        pid = p.get("id")
        ploc = pid if pid else f"index {idx}"
        if not pid or not ID_RE.match(str(pid)):
            fail(errors, f"[{ploc}] passage id missing or not of form 'psg-cars-<n>'.")
        if pid in seen_pids:
            fail(errors, f"[{ploc}] duplicate passage id.")
        if pid:
            seen_pids.add(pid)

        if p.get("section") != "CARS":
            fail(errors, f"[{ploc}] section must be 'CARS'.")

        passage = p.get("passage")
        if not isinstance(passage, str) or not passage.strip():
            fail(errors, f"[{ploc}] missing/empty 'passage'.")
            words = 0
        else:
            words = len(passage.split())
            if words < WORD_MIN_HARD or words > WORD_MAX_HARD:
                fail(errors, f"[{ploc}] passage is {words} words; must be within "
                             f"[{WORD_MIN_HARD}, {WORD_MAX_HARD}].")
            elif words < WORD_MIN_SOFT or words > WORD_MAX_SOFT:
                warnings.append(f"[{ploc}] passage is {words} words; CARS target is "
                                f"~500-600 (soft band [{WORD_MIN_SOFT}, {WORD_MAX_SOFT}]).")
        word_report.append((pid or ploc, words))

        src = p.get("passage_source")
        if not isinstance(src, dict):
            fail(errors, f"[{ploc}] 'passage_source' must be an object.")
        else:
            if not src.get("name"):
                fail(errors, f"[{ploc}] passage_source.name is missing/empty.")
            if "url" not in src or not isinstance(src.get("url"), str):
                fail(errors, f"[{ploc}] passage_source.url must be a string (may be empty).")
            lic = src.get("license", "")
            license_counts[str(lic).strip().lower()] += 1
            if not is_open_license(lic):
                fail(errors, f"[{ploc}] passage_source.license {lic!r} is not "
                             f"public-domain / openly-licensed / original.")

        questions = p.get("questions")
        if not isinstance(questions, list) or len(questions) < 5:
            n = len(questions) if isinstance(questions, list) else "n/a"
            fail(errors, f"[{ploc}] must have >= 5 questions, found {n}.")
            questions = questions if isinstance(questions, list) else []

        for q in questions:
            if not isinstance(q, dict):
                fail(errors, f"[{ploc}] a question is not an object.")
                continue
            total_questions += 1
            skill = check_question(errors, ploc, q, seen_qids)
            if skill:
                skill_counts[skill] += 1
            if q.get("difficulty") in ALLOWED_DIFFICULTY:
                diff_counts[q["difficulty"]] += 1

    # ---- Report -----------------------------------------------------------
    print("ReadyMCAT CARS passage bank — validation report")
    print(f"  file:            {args.file}")
    print(f"  passages:        {len(data)}")
    print(f"  questions:       {total_questions}")
    print(f"  skill spread:    " + ", ".join(
        f"{s}={skill_counts.get(s, 0)}" for s in sorted(ALLOWED_SKILLS)))
    print(f"  difficulty:      " + ", ".join(
        f"{d}={diff_counts.get(d, 0)}" for d in ("easy", "medium", "hard")))
    print(f"  licenses:        " + ", ".join(
        f"{lic}={n}" for lic, n in sorted(license_counts.items())))
    print("  passage words:")
    for pid, words in word_report:
        print(f"      {pid}: {words}")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
