#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Self-contained validator for the ReadyMCAT passage-based question banks.

Checks, with NO third-party dependencies, that a passage file conforms EXACTLY
to the agreed ReadyMCAT passage schema:

  Top level: a JSON array of passage objects, each with:
    id             : unique string, prefix "psg-bb-"
    section        : "B/B"
    passage        : non-empty string (the original passage text)
    passage_source : object with non-empty name, url, license
    questions      : list of 4-6 question objects

  Each question:
    id            : unique string
    aamc_category : an AAMC content-category ID valid for this section
    subtopic      : non-empty string
    stem          : non-empty string
    options       : list of EXACTLY 4 non-empty, unique strings
    correct_index : integer in [0, 3]
    explanation   : non-empty string
    difficulty    : one of easy | medium | hard
    cognitive_level : one of comprehension | application | data-analysis
    subquestions  : the teach-on-miss ladder, a list of 2-3 steps

  Each subquestion (ladder rung):
    stem          : non-empty string
    options       : list of >= 2 non-empty, unique strings
    correct_index : integer within range of its options
    explanation   : non-empty string

It also cross-checks each aamc_category against taxonomy.json if one is found
(walking up from this file), and prints a coverage report (passages, questions,
subquestions, per-category counts, difficulty and cognitive-level spread).

Word-count and question-count guidance from the spec (~200-350 word passages,
4-6 questions each) is reported as WARNINGS, not hard errors, so intentionally
short discrete-question sets do not fail the structural check.

Usage:
    python3 passage_bio_biochem_validate.py [--file PATH] [--taxonomy PATH] [--strict]

--strict promotes warnings to errors. Exits 0 on success, 1 on any failure.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

# AAMC content categories that belong to the Biological & Biochemical
# Foundations (B/B) section: Foundational Concepts 1-3. Copied from
# taxonomy.json (key: aamc_categories); taxonomy.json is the source of truth
# and is cross-checked below when available.
EXPECTED_BB_CATEGORIES = {
    "1A", "1B", "1C", "1D",
    "2A", "2B", "2C",
    "3A", "3B",
}

REQUIRED_QUESTION_FIELDS = (
    "id", "aamc_category", "subtopic", "stem", "options", "correct_index",
    "explanation", "difficulty", "cognitive_level", "subquestions",
)
REQUIRED_SOURCE_FIELDS = ("name", "url", "license")
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_COGNITIVE = {"comprehension", "application", "data-analysis"}

OPTIONS_PER_QUESTION = 4          # real MCAT-style: 4 options (A-D)
MIN_SUBQUESTIONS = 2             # teach-on-miss ladder: 2-3 rungs
MAX_SUBQUESTIONS = 3
MIN_QUESTIONS_PER_PASSAGE = 4    # spec guidance (warning only)
MAX_QUESTIONS_PER_PASSAGE = 6
PASSAGE_MIN_WORDS = 200          # spec guidance (warning only)
PASSAGE_MAX_WORDS = 350
SECTION = "B/B"
ID_PREFIX = "psg-bb-"

HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_taxonomy(explicit: str | None) -> str | None:
    if explicit:
        return explicit if os.path.exists(explicit) else None
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


def is_nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def check_options(options, loc, errors, *, exact=None, minimum=None):
    if not isinstance(options, list):
        errors.append(f"[{loc}] options must be a list.")
        return
    n = len(options)
    if exact is not None and n != exact:
        errors.append(f"[{loc}] expected {exact} options, found {n}.")
    if minimum is not None and n < minimum:
        errors.append(f"[{loc}] expected at least {minimum} options, found {n}.")
    for i, opt in enumerate(options):
        if not is_nonempty_str(opt):
            errors.append(f"[{loc}] option {i} is empty or not a string.")
    texts = [o.strip() for o in options if isinstance(o, str)]
    if len(set(texts)) != len(texts):
        errors.append(f"[{loc}] option texts are not unique.")


def check_correct_index(value, options, loc, errors):
    n = len(options) if isinstance(options, list) else 0
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"[{loc}] correct_index must be an integer, got {value!r}.")
        return
    if n and not (0 <= value < n):
        errors.append(f"[{loc}] correct_index {value} out of range 0..{n - 1}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", default=os.path.join(HERE, "passage_bio_biochem.json"))
    parser.add_argument("--taxonomy", default=None,
                        help="Optional path to taxonomy.json for cross-checking.")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings (word/question counts) as errors.")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    data = load_json(args.file)
    if not isinstance(data, list) or not data:
        print("FAILED: top-level JSON must be a non-empty array.", file=sys.stderr)
        return 1

    seen_passage_ids: set[str] = set()
    seen_question_ids: set[str] = set()
    per_category: collections.Counter[str] = collections.Counter()
    difficulty_counts: collections.Counter[str] = collections.Counter()
    cognitive_counts: collections.Counter[str] = collections.Counter()
    total_questions = 0
    total_subquestions = 0

    for p_idx, entry in enumerate(data):
        ploc = entry.get("id", f"passage index {p_idx}") if isinstance(entry, dict) else f"index {p_idx}"
        if not isinstance(entry, dict):
            errors.append(f"[{ploc}] passage entry is not an object.")
            continue

        pid = entry.get("id")
        if not is_nonempty_str(pid):
            errors.append(f"[{ploc}] missing/empty passage id.")
        else:
            if not pid.startswith(ID_PREFIX):
                errors.append(f"[{ploc}] id should start with '{ID_PREFIX}'.")
            if pid in seen_passage_ids:
                errors.append(f"[{ploc}] duplicate passage id.")
            seen_passage_ids.add(pid)

        if entry.get("section") != SECTION:
            errors.append(f"[{ploc}] section must be '{SECTION}', got {entry.get('section')!r}.")

        passage = entry.get("passage")
        if not is_nonempty_str(passage):
            errors.append(f"[{ploc}] passage text is missing or empty.")
        else:
            words = len(passage.split())
            if not (PASSAGE_MIN_WORDS <= words <= PASSAGE_MAX_WORDS):
                warnings.append(
                    f"[{ploc}] passage is {words} words (guideline "
                    f"{PASSAGE_MIN_WORDS}-{PASSAGE_MAX_WORDS}).")

        src = entry.get("passage_source")
        if not isinstance(src, dict):
            errors.append(f"[{ploc}] passage_source must be an object.")
        else:
            for f in REQUIRED_SOURCE_FIELDS:
                if not is_nonempty_str(src.get(f)):
                    errors.append(f"[{ploc}] passage_source.{f} is missing or empty.")

        questions = entry.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append(f"[{ploc}] questions must be a non-empty list.")
            continue
        if not (MIN_QUESTIONS_PER_PASSAGE <= len(questions) <= MAX_QUESTIONS_PER_PASSAGE):
            warnings.append(
                f"[{ploc}] has {len(questions)} questions (guideline "
                f"{MIN_QUESTIONS_PER_PASSAGE}-{MAX_QUESTIONS_PER_PASSAGE}).")

        for q_idx, q in enumerate(questions):
            qloc = q.get("id", f"{ploc} q{q_idx}") if isinstance(q, dict) else f"{ploc} q{q_idx}"
            if not isinstance(q, dict):
                errors.append(f"[{qloc}] question is not an object.")
                continue
            total_questions += 1

            for field in REQUIRED_QUESTION_FIELDS:
                if field not in q:
                    errors.append(f"[{qloc}] missing required field '{field}'.")

            qid = q.get("id")
            if is_nonempty_str(qid):
                if qid in seen_question_ids:
                    errors.append(f"[{qloc}] duplicate question id.")
                seen_question_ids.add(qid)
            else:
                errors.append(f"[{qloc}] missing/empty question id.")

            cat = q.get("aamc_category")
            if cat is not None:
                per_category[cat] += 1
                if cat not in EXPECTED_BB_CATEGORIES:
                    errors.append(
                        f"[{qloc}] aamc_category '{cat}' is not a valid B/B "
                        f"(FC 1-3) content category.")

            if not is_nonempty_str(q.get("subtopic")):
                errors.append(f"[{qloc}] subtopic is missing or empty.")
            if not is_nonempty_str(q.get("stem")):
                errors.append(f"[{qloc}] stem is missing or empty.")
            if not is_nonempty_str(q.get("explanation")):
                errors.append(f"[{qloc}] explanation is missing or empty.")

            options = q.get("options", [])
            check_options(options, qloc, errors, exact=OPTIONS_PER_QUESTION)
            check_correct_index(q.get("correct_index"), options, qloc, errors)

            if q.get("difficulty") not in ALLOWED_DIFFICULTY:
                errors.append(f"[{qloc}] difficulty '{q.get('difficulty')}' not in "
                              f"{sorted(ALLOWED_DIFFICULTY)}.")
            else:
                difficulty_counts[q["difficulty"]] += 1

            if q.get("cognitive_level") not in ALLOWED_COGNITIVE:
                errors.append(f"[{qloc}] cognitive_level '{q.get('cognitive_level')}' "
                              f"not in {sorted(ALLOWED_COGNITIVE)}.")
            else:
                cognitive_counts[q["cognitive_level"]] += 1

            subqs = q.get("subquestions")
            if not isinstance(subqs, list):
                errors.append(f"[{qloc}] subquestions must be a list (teach-on-miss ladder).")
                continue
            if not (MIN_SUBQUESTIONS <= len(subqs) <= MAX_SUBQUESTIONS):
                errors.append(
                    f"[{qloc}] has {len(subqs)} subquestions; the teach-on-miss "
                    f"ladder must have {MIN_SUBQUESTIONS}-{MAX_SUBQUESTIONS}.")
            for s_idx, sq in enumerate(subqs):
                sloc = f"{qloc} sub{s_idx}"
                if not isinstance(sq, dict):
                    errors.append(f"[{sloc}] subquestion is not an object.")
                    continue
                total_subquestions += 1
                if not is_nonempty_str(sq.get("stem")):
                    errors.append(f"[{sloc}] stem is missing or empty.")
                if not is_nonempty_str(sq.get("explanation")):
                    errors.append(f"[{sloc}] explanation is missing or empty.")
                s_options = sq.get("options", [])
                check_options(s_options, sloc, errors, minimum=2)
                check_correct_index(sq.get("correct_index"), s_options, sloc, errors)

    # Coverage: every B/B category should be represented at least once.
    missing = sorted(EXPECTED_BB_CATEGORIES - set(per_category),
                     key=lambda c: (int(c[:-1]), c[-1]))
    if missing:
        errors.append(f"B/B categories with NO questions: {missing}")

    # Optional cross-check against taxonomy.json.
    taxonomy_path = find_taxonomy(args.taxonomy)
    if taxonomy_path:
        taxonomy = load_json(taxonomy_path)
        tax_cats = set(taxonomy.get("aamc_categories", {}))
        not_in_tax = sorted(c for c in per_category if c not in tax_cats)
        if not_in_tax:
            errors.append(f"aamc_category values absent from {taxonomy_path}: {not_in_tax}")
        else:
            print(f"Cross-checked all categories against taxonomy.json at: {taxonomy_path}")
    else:
        print("taxonomy.json not found locally; used embedded B/B category set.")

    # ---- Report ----
    print("\nCoverage report (questions per B/B AAMC content category):")
    for cat in sorted(EXPECTED_BB_CATEGORIES, key=lambda c: (int(c[:-1]), c[-1])):
        print(f"  {cat:>3}: {per_category.get(cat, 0)}")
    print(f"\nPassages / question sets : {len(data)}")
    print(f"Total questions          : {total_questions}")
    print(f"Total subquestions       : {total_subquestions}")
    print(f"Categories covered       : {len(set(per_category) & EXPECTED_BB_CATEGORIES)}/"
          f"{len(EXPECTED_BB_CATEGORIES)}")
    print(f"Difficulty spread        : {dict(sorted(difficulty_counts.items()))}")
    print(f"Cognitive-level spread   : {dict(sorted(cognitive_counts.items()))}")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")

    if args.strict:
        errors.extend(warnings)

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nOK: all structural checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
