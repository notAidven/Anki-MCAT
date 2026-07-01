#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Self-contained validator for the ReadyMCAT C/P passage bank.

Checks, with no third-party dependencies (stdlib only):

  1. The file is valid JSON and a non-empty array of passage sets.
  2. Each passage set has the required fields; a unique id matching
     ``psg-cp-<n>``; ``section == "C/P"``; a non-empty passage; a complete
     ``passage_source`` (name + url + license); and at least 4 questions.
  3. Each question has the required fields; a unique id matching
     ``psg-cp-<n>-q<k>``; an ``aamc_category`` that is a real AAMC content
     category (cross-checked against ``taxonomy.json`` when found) AND is one of
     the Chemical/Physical Foundations categories (4A-4E, 5A-5E); exactly 4
     non-empty, unique options; a ``correct_index`` in range [0, 3]; a valid
     ``difficulty`` and ``cognitive_level``; and a teach-on-miss ladder of 2-3
     subquestions.
  4. Each subquestion has a non-empty stem; at least 2 non-empty, unique
     options; a ``correct_index`` in range; and a non-empty explanation.
  5. Coverage: all ten C/P categories (4A-4E, 5A-5E) appear at least once.

Usage:
    python3 passage_chem_phys_validate.py [--bank PATH] [--taxonomy PATH]

Exits 0 on success, 1 on any validation failure.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

# The ten Chemical and Physical Foundations content categories this bank covers
# (AAMC Foundational Concepts 4 and 5).
CP_CATEGORIES = {
    "4A", "4B", "4C", "4D", "4E",
    "5A", "5B", "5C", "5D", "5E",
}

# The full set of 31 AAMC content-category IDs, copied from taxonomy.json as an
# OFFLINE FALLBACK. taxonomy.json is the source of truth; when it is found this
# set is cross-checked against it.
ALL_AAMC_CATEGORIES = {
    "1A", "1B", "1C", "1D",
    "2A", "2B", "2C",
    "3A", "3B",
    "4A", "4B", "4C", "4D", "4E",
    "5A", "5B", "5C", "5D", "5E",
    "6A", "6B", "6C",
    "7A", "7B", "7C",
    "8A", "8B", "8C",
    "9A", "9B",
    "10A",
}

ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_COGNITIVE = {"comprehension", "application", "data-analysis"}

REQUIRED_SET_FIELDS = ("id", "section", "passage", "passage_source", "questions")
REQUIRED_QUESTION_FIELDS = (
    "id", "aamc_category", "subtopic", "stem", "options", "correct_index",
    "explanation", "difficulty", "cognitive_level", "subquestions",
)
REQUIRED_SUBQUESTION_FIELDS = ("stem", "options", "correct_index", "explanation")

SET_ID_RE = re.compile(r"^psg-cp-\d+$")

HERE = os.path.dirname(os.path.abspath(__file__))


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_taxonomy(explicit: str | None) -> str | None:
    if explicit:
        return explicit if os.path.exists(explicit) else None
    # Walk up from this file looking for a repo-root taxonomy.json.
    cur = HERE
    for _ in range(8):
        candidate = os.path.join(cur, "taxonomy.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def check_options(options, loc: str, errors: list[str], expected_count: int | None) -> None:
    """Validate a list of option strings (question or subquestion)."""
    if not isinstance(options, list):
        fail(errors, f"[{loc}] 'options' must be a list.")
        return
    if expected_count is not None and len(options) != expected_count:
        fail(errors, f"[{loc}] expected {expected_count} options, found {len(options)}.")
    if len(options) < 2:
        fail(errors, f"[{loc}] needs at least 2 options, found {len(options)}.")
    if not all(isinstance(o, str) and o.strip() for o in options):
        fail(errors, f"[{loc}] contains an empty or non-string option.")
    if len(set(options)) != len(options):
        fail(errors, f"[{loc}] options are not unique.")


def check_index(value, options, loc: str, errors: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        fail(errors, f"[{loc}] correct_index must be an integer, got {value!r}.")
        return
    if not (0 <= value < len(options)):
        fail(errors, f"[{loc}] correct_index {value} out of range for {len(options)} options.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", default=os.path.join(HERE, "passage_chem_phys.json"))
    parser.add_argument("--taxonomy", default=None,
                        help="Optional explicit path to taxonomy.json for cross-checking.")
    args = parser.parse_args()

    errors: list[str] = []

    # 1. Valid JSON + top-level array.
    try:
        bank = load_json(args.bank)
    except json.JSONDecodeError as exc:
        print(f"FAILED: {args.bank} is not valid JSON: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"FAILED: bank file not found: {args.bank}", file=sys.stderr)
        return 1

    if not isinstance(bank, list) or not bank:
        print("FAILED: top-level JSON must be a non-empty array of passage sets.", file=sys.stderr)
        return 1

    # Determine the valid AAMC category set (taxonomy.json is source of truth).
    taxonomy_path = find_taxonomy(args.taxonomy)
    if taxonomy_path:
        taxonomy = load_json(taxonomy_path)
        valid_categories = set(taxonomy.get("aamc_categories", {}))
        if not valid_categories:
            valid_categories = set(ALL_AAMC_CATEGORIES)
        # Sanity: the embedded fallback should agree with taxonomy.json.
        if valid_categories and not CP_CATEGORIES <= valid_categories:
            fail(errors, f"C/P categories missing from taxonomy.json: "
                         f"{sorted(CP_CATEGORIES - valid_categories)}")
    else:
        valid_categories = set(ALL_AAMC_CATEGORIES)

    seen_set_ids: set[str] = set()
    seen_q_ids: set[str] = set()
    per_category: collections.Counter[str] = collections.Counter()
    total_questions = 0
    total_subquestions = 0

    for s_idx, s in enumerate(bank):
        s_loc = s.get("id", f"set index {s_idx}") if isinstance(s, dict) else f"set index {s_idx}"

        if not isinstance(s, dict):
            fail(errors, f"[{s_loc}] passage set must be an object.")
            continue

        for field in REQUIRED_SET_FIELDS:
            if field not in s:
                fail(errors, f"[{s_loc}] missing required field '{field}'.")

        set_id = s.get("id")
        if isinstance(set_id, str) and not SET_ID_RE.match(set_id):
            fail(errors, f"[{s_loc}] id does not match 'psg-cp-<n>'.")
        if set_id in seen_set_ids:
            fail(errors, f"[{s_loc}] duplicate set id.")
        if isinstance(set_id, str):
            seen_set_ids.add(set_id)

        if s.get("section") != "C/P":
            fail(errors, f"[{s_loc}] section must be 'C/P', got {s.get('section')!r}.")

        passage = s.get("passage")
        if not (isinstance(passage, str) and passage.strip()):
            fail(errors, f"[{s_loc}] passage is empty or missing.")

        ps = s.get("passage_source")
        if not isinstance(ps, dict):
            fail(errors, f"[{s_loc}] passage_source must be an object.")
        else:
            for key in ("name", "url", "license"):
                if not (isinstance(ps.get(key), str) and ps.get(key).strip()):
                    fail(errors, f"[{s_loc}] passage_source.{key} is missing or empty.")

        questions = s.get("questions")
        if not isinstance(questions, list):
            fail(errors, f"[{s_loc}] questions must be a list.")
            continue
        if len(questions) < 4:
            fail(errors, f"[{s_loc}] needs at least 4 questions, found {len(questions)}.")

        for q_idx, question in enumerate(questions, start=1):
            q_loc = question.get("id", f"{set_id}-q{q_idx}") if isinstance(question, dict) else f"{set_id}-q{q_idx}"
            if not isinstance(question, dict):
                fail(errors, f"[{q_loc}] question must be an object.")
                continue

            total_questions += 1

            for field in REQUIRED_QUESTION_FIELDS:
                if field not in question:
                    fail(errors, f"[{q_loc}] missing required field '{field}'.")

            q_id = question.get("id")
            expected_qid = f"{set_id}-q{q_idx}" if isinstance(set_id, str) else None
            if expected_qid and q_id != expected_qid:
                fail(errors, f"[{q_loc}] id should be '{expected_qid}'.")
            if q_id in seen_q_ids:
                fail(errors, f"[{q_loc}] duplicate question id.")
            if isinstance(q_id, str):
                seen_q_ids.add(q_id)

            cat = question.get("aamc_category")
            if isinstance(cat, str):
                per_category[cat] += 1
                if cat not in valid_categories:
                    fail(errors, f"[{q_loc}] aamc_category '{cat}' is not a real AAMC category.")
                elif cat not in CP_CATEGORIES:
                    fail(errors, f"[{q_loc}] aamc_category '{cat}' is outside the C/P set (4A-4E, 5A-5E).")
            else:
                fail(errors, f"[{q_loc}] aamc_category missing or non-string.")

            if not (isinstance(question.get("subtopic"), str) and question.get("subtopic").strip()):
                fail(errors, f"[{q_loc}] subtopic is empty or missing.")
            if not (isinstance(question.get("stem"), str) and question.get("stem").strip()):
                fail(errors, f"[{q_loc}] stem is empty or missing.")
            if not (isinstance(question.get("explanation"), str) and question.get("explanation").strip()):
                fail(errors, f"[{q_loc}] explanation is empty or missing.")

            options = question.get("options", [])
            check_options(options, q_loc, errors, expected_count=4)
            check_index(question.get("correct_index"), options, q_loc, errors)

            if question.get("difficulty") not in ALLOWED_DIFFICULTY:
                fail(errors, f"[{q_loc}] difficulty '{question.get('difficulty')}' invalid.")
            if question.get("cognitive_level") not in ALLOWED_COGNITIVE:
                fail(errors, f"[{q_loc}] cognitive_level '{question.get('cognitive_level')}' invalid.")

            subs = question.get("subquestions")
            if not isinstance(subs, list):
                fail(errors, f"[{q_loc}] subquestions must be a list.")
                continue
            if not (2 <= len(subs) <= 3):
                fail(errors, f"[{q_loc}] teach-on-miss ladder must have 2-3 steps, found {len(subs)}.")
            for sub_idx, subq in enumerate(subs, start=1):
                sub_loc = f"{q_loc}-sub{sub_idx}"
                total_subquestions += 1
                if not isinstance(subq, dict):
                    fail(errors, f"[{sub_loc}] subquestion must be an object.")
                    continue
                for field in REQUIRED_SUBQUESTION_FIELDS:
                    if field not in subq:
                        fail(errors, f"[{sub_loc}] missing required field '{field}'.")
                if not (isinstance(subq.get("stem"), str) and subq.get("stem").strip()):
                    fail(errors, f"[{sub_loc}] stem is empty or missing.")
                if not (isinstance(subq.get("explanation"), str) and subq.get("explanation").strip()):
                    fail(errors, f"[{sub_loc}] explanation is empty or missing.")
                sub_options = subq.get("options", [])
                check_options(sub_options, sub_loc, errors, expected_count=None)
                check_index(subq.get("correct_index"), sub_options, sub_loc, errors)

    # 5. Coverage of the ten C/P categories.
    missing = sorted(CP_CATEGORIES - set(per_category))
    if missing:
        fail(errors, f"C/P categories with NO questions: {missing}")

    # Report.
    if taxonomy_path:
        print(f"Cross-checked category IDs against taxonomy.json at: {taxonomy_path}")
    else:
        print("taxonomy.json not found locally; used embedded AAMC category set.")

    print("\nCoverage report (questions per C/P content category):")
    for cat in sorted(CP_CATEGORIES, key=lambda c: (int(c[:-1]), c[-1])):
        print(f"  {cat:>3}: {per_category.get(cat, 0)}")
    print(f"\nC/P categories covered: {len(set(per_category) & CP_CATEGORIES)}/{len(CP_CATEGORIES)}")
    print(f"Passage sets: {len(bank)}")
    print(f"Total questions: {total_questions}")
    print(f"Total teach-on-miss subquestions: {total_subquestions}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
