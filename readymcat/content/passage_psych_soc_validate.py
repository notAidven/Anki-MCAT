#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Self-contained validator for the ReadyMCAT P/S passage question bank.

Validates `passage_psych_soc.json` with no third-party dependencies. Checks:

  1. Top-level shape: a non-empty JSON array of passage objects.
  2. Every passage: required fields present; `id` matches `psg-ps-<n>` and is
     unique; `section == "P/S"`; `passage_source` has non-empty name/url/license;
     narrative (non-discrete) passages are 200-350 words and hold 4-6 questions.
  3. Every question: required fields; `id` is `psg-ps-<n>-q<k>`, unique, and
     prefixed by its passage id; exactly 4 unique non-empty options; a valid
     `correct_index`; a non-trivial explanation; allowed `difficulty` and
     `cognitive_level`; and a 2-3 rung teach-on-miss `subquestions` ladder.
  4. Every sub-question: stem, 2-4 unique non-empty options, valid
     `correct_index`, and a non-empty explanation.
  5. Coverage: every question's `aamc_category` is a P/S content category
     (AAMC Foundational Concepts 6-10) and all 12 are covered at least once.
  6. (Optional) Cross-checks the used categories against a real `taxonomy.json`
     if one is found by walking up from this file.

Usage:
    python3 passage_psych_soc_validate.py [--bank PATH] [--taxonomy PATH]

Exits 0 on success, 1 on any validation failure.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re

# AAMC content categories for the P/S section (Foundational Concepts 6-10).
# taxonomy.json is the source of truth; this is the offline fallback used here.
PS_CATEGORIES = {
    "6A", "6B", "6C",
    "7A", "7B", "7C",
    "8A", "8B", "8C",
    "9A", "9B",
    "10A",
}

REQUIRED_PASSAGE_FIELDS = ("id", "section", "passage", "passage_source", "questions")
REQUIRED_QUESTION_FIELDS = (
    "id", "aamc_category", "subtopic", "stem", "options", "correct_index",
    "explanation", "difficulty", "cognitive_level", "subquestions",
)
REQUIRED_SUBQ_FIELDS = ("stem", "options", "correct_index", "explanation")

ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_COGNITIVE = {"comprehension", "application", "data-analysis"}

PASSAGE_ID_RE = re.compile(r"^psg-ps-\d+$")
QUESTION_ID_RE = re.compile(r"^psg-ps-\d+-q\d+$")

PASSAGE_MIN_WORDS = 200
PASSAGE_MAX_WORDS = 350
PASSAGE_MIN_QUESTIONS = 4
PASSAGE_MAX_QUESTIONS = 6
SUBQ_MIN = 2
SUBQ_MAX = 3

HERE = os.path.dirname(os.path.abspath(__file__))


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def is_discrete(passage_text: str) -> bool:
    """Discrete (non-passage) sets are flagged by a sentinel opening phrase."""
    return passage_text.strip().startswith("Discrete questions")


def find_taxonomy(explicit: str | None) -> str | None:
    if explicit:
        return explicit if os.path.exists(explicit) else None
    cur = HERE
    for _ in range(6):
        candidate = os.path.join(cur, "taxonomy.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def check_options(errors: list[str], loc: str, options, *, exact: int | None,
                  lo: int, hi: int, correct_index) -> None:
    if not isinstance(options, list):
        fail(errors, f"[{loc}] options must be a list.")
        return
    n = len(options)
    if exact is not None and n != exact:
        fail(errors, f"[{loc}] expected {exact} options, found {n}.")
    elif exact is None and not (lo <= n <= hi):
        fail(errors, f"[{loc}] expected {lo}-{hi} options, found {n}.")
    if any((not isinstance(o, str) or not o.strip()) for o in options):
        fail(errors, f"[{loc}] an option is empty or not a string.")
    if len({o.strip() for o in options if isinstance(o, str)}) != n:
        fail(errors, f"[{loc}] option texts are not unique.")
    if not isinstance(correct_index, bool) and isinstance(correct_index, int):
        if not (0 <= correct_index < n):
            fail(errors, f"[{loc}] correct_index {correct_index} out of range for {n} options.")
    else:
        fail(errors, f"[{loc}] correct_index must be an integer.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", default=os.path.join(HERE, "passage_psych_soc.json"))
    parser.add_argument("--taxonomy", default=None,
                        help="Optional path to taxonomy.json for cross-checking.")
    args = parser.parse_args()

    errors: list[str] = []
    bank = load_json(args.bank)

    if not isinstance(bank, list) or not bank:
        print("FAILED: top-level JSON must be a non-empty array of passages.")
        return 1

    seen_passage_ids: set[str] = set()
    seen_question_ids: set[str] = set()
    per_category: collections.Counter[str] = collections.Counter()
    per_difficulty: collections.Counter[str] = collections.Counter()
    per_cognitive: collections.Counter[str] = collections.Counter()
    n_questions = 0
    n_subquestions = 0
    n_discrete = 0

    for pidx, p in enumerate(bank):
        ploc = p.get("id", f"passage index {pidx}") if isinstance(p, dict) else f"passage index {pidx}"
        if not isinstance(p, dict):
            fail(errors, f"[{ploc}] passage is not an object.")
            continue

        for field in REQUIRED_PASSAGE_FIELDS:
            if field not in p:
                fail(errors, f"[{ploc}] missing required field '{field}'.")

        pid = p.get("id")
        if isinstance(pid, str):
            if not PASSAGE_ID_RE.match(pid):
                fail(errors, f"[{ploc}] id '{pid}' does not match psg-ps-<n>.")
            if pid in seen_passage_ids:
                fail(errors, f"[{ploc}] duplicate passage id.")
            seen_passage_ids.add(pid)

        if p.get("section") != "P/S":
            fail(errors, f"[{ploc}] section must be 'P/S' (found {p.get('section')!r}).")

        passage_text = p.get("passage", "")
        if not isinstance(passage_text, str) or not passage_text.strip():
            fail(errors, f"[{ploc}] passage text is empty.")
            passage_text = ""

        discrete = is_discrete(passage_text)
        if discrete:
            n_discrete += 1

        src = p.get("passage_source")
        if not isinstance(src, dict):
            fail(errors, f"[{ploc}] passage_source must be an object.")
        else:
            for key in ("name", "url", "license"):
                if not (isinstance(src.get(key), str) and src.get(key).strip()):
                    fail(errors, f"[{ploc}] passage_source.{key} is missing/empty.")
            url = src.get("url", "")
            if isinstance(url, str) and url and not url.startswith(("http://", "https://")):
                fail(errors, f"[{ploc}] passage_source.url should be a URL.")

        questions = p.get("questions", [])
        if not isinstance(questions, list) or not questions:
            fail(errors, f"[{ploc}] questions must be a non-empty list.")
            questions = []

        # Narrative passages: enforce word count + question count. Discrete sets
        # are standalone items with only a short header, so they are exempt.
        if not discrete and passage_text:
            wc = len(passage_text.split())
            if not (PASSAGE_MIN_WORDS <= wc <= PASSAGE_MAX_WORDS):
                fail(errors, f"[{ploc}] passage is {wc} words; expected "
                             f"{PASSAGE_MIN_WORDS}-{PASSAGE_MAX_WORDS}.")
            if not (PASSAGE_MIN_QUESTIONS <= len(questions) <= PASSAGE_MAX_QUESTIONS):
                fail(errors, f"[{ploc}] has {len(questions)} questions; expected "
                             f"{PASSAGE_MIN_QUESTIONS}-{PASSAGE_MAX_QUESTIONS}.")

        for q in questions:
            n_questions += 1
            qloc = q.get("id", f"{ploc} q?") if isinstance(q, dict) else f"{ploc} q?"
            if not isinstance(q, dict):
                fail(errors, f"[{qloc}] question is not an object.")
                continue

            for field in REQUIRED_QUESTION_FIELDS:
                if field not in q:
                    fail(errors, f"[{qloc}] missing required field '{field}'.")

            qid = q.get("id")
            if isinstance(qid, str):
                if not QUESTION_ID_RE.match(qid):
                    fail(errors, f"[{qloc}] id '{qid}' does not match psg-ps-<n>-q<k>.")
                if isinstance(pid, str) and not qid.startswith(pid + "-q"):
                    fail(errors, f"[{qloc}] id not prefixed by passage id '{pid}'.")
                if qid in seen_question_ids:
                    fail(errors, f"[{qloc}] duplicate question id.")
                seen_question_ids.add(qid)

            cat = q.get("aamc_category")
            if cat is not None:
                per_category[cat] += 1
                if cat not in PS_CATEGORIES:
                    fail(errors, f"[{qloc}] aamc_category '{cat}' is not a P/S category (FC 6-10).")

            if not (isinstance(q.get("subtopic"), str) and q.get("subtopic").strip()):
                fail(errors, f"[{qloc}] subtopic is missing/empty.")
            if not (isinstance(q.get("stem"), str) and q.get("stem").strip()):
                fail(errors, f"[{qloc}] stem is missing/empty.")

            check_options(errors, qloc, q.get("options"), exact=4, lo=4, hi=4,
                          correct_index=q.get("correct_index"))

            expl = q.get("explanation")
            if not (isinstance(expl, str) and len(expl.strip()) >= 30):
                fail(errors, f"[{qloc}] explanation missing or too short (>=30 chars).")

            per_difficulty[q.get("difficulty")] += 1
            if q.get("difficulty") not in ALLOWED_DIFFICULTY:
                fail(errors, f"[{qloc}] difficulty '{q.get('difficulty')}' invalid.")
            per_cognitive[q.get("cognitive_level")] += 1
            if q.get("cognitive_level") not in ALLOWED_COGNITIVE:
                fail(errors, f"[{qloc}] cognitive_level '{q.get('cognitive_level')}' invalid.")

            subs = q.get("subquestions", [])
            if not isinstance(subs, list) or not (SUBQ_MIN <= len(subs) <= SUBQ_MAX):
                fail(errors, f"[{qloc}] subquestions must be a {SUBQ_MIN}-{SUBQ_MAX} rung ladder "
                             f"(found {len(subs) if isinstance(subs, list) else 'non-list'}).")
                subs = subs if isinstance(subs, list) else []
            for sidx, sq in enumerate(subs):
                n_subquestions += 1
                sloc = f"{qloc} sub{sidx + 1}"
                if not isinstance(sq, dict):
                    fail(errors, f"[{sloc}] sub-question is not an object.")
                    continue
                for field in REQUIRED_SUBQ_FIELDS:
                    if field not in sq:
                        fail(errors, f"[{sloc}] missing required field '{field}'.")
                if not (isinstance(sq.get("stem"), str) and sq.get("stem").strip()):
                    fail(errors, f"[{sloc}] stem is missing/empty.")
                check_options(errors, sloc, sq.get("options"), exact=None, lo=2, hi=4,
                              correct_index=sq.get("correct_index"))
                if not (isinstance(sq.get("explanation"), str) and sq.get("explanation").strip()):
                    fail(errors, f"[{sloc}] explanation is missing/empty.")

    missing = sorted(PS_CATEGORIES - set(per_category),
                     key=lambda c: (int(c[:-1]), c[-1]))
    if missing:
        fail(errors, f"P/S categories with NO questions: {missing}")

    # Optional cross-check against the real taxonomy.json if available.
    taxonomy_path = find_taxonomy(args.taxonomy)
    if taxonomy_path:
        taxonomy = load_json(taxonomy_path)
        tax_cats = set(taxonomy.get("aamc_categories", {}))
        not_in_tax = sorted(c for c in per_category if c not in tax_cats)
        if not_in_tax:
            fail(errors, f"Categories used here but absent from {taxonomy_path}: {not_in_tax}")
        ps_missing_from_tax = sorted(PS_CATEGORIES - tax_cats)
        if ps_missing_from_tax:
            fail(errors, f"P/S categories missing from taxonomy.json: {ps_missing_from_tax}")
        if not not_in_tax and not ps_missing_from_tax:
            print(f"Cross-checked categories against taxonomy.json at: {taxonomy_path}")
    else:
        print("taxonomy.json not found locally; used embedded P/S category set.")

    # Report.
    print(f"\nPassages: {len(bank)} ({n_discrete} discrete)  "
          f"Questions: {n_questions}  Sub-questions: {n_subquestions}")
    print("\nCoverage (questions per AAMC P/S content category):")
    for cat in sorted(PS_CATEGORIES, key=lambda c: (int(c[:-1]), c[-1])):
        print(f"  {cat:>3}: {per_category.get(cat, 0)}")
    print(f"Categories covered: {len(set(per_category) & PS_CATEGORIES)}/{len(PS_CATEGORIES)}")
    print("\nDifficulty mix:  " + ", ".join(
        f"{d}={per_difficulty.get(d, 0)}" for d in ("easy", "medium", "hard")))
    print("Cognitive mix:   " + ", ".join(
        f"{c}={per_cognitive.get(c, 0)}" for c in ("comprehension", "application", "data-analysis")))

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
