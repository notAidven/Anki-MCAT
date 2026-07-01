#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Self-contained validator for the ReadyMCAT P/S FREE-RESPONSE item bank.

No third-party dependencies. It checks:
  1. JSON validity of free_response_psych_soc.json (loads as a JSON array).
  2. Structural integrity of every item (all required fields present; correct
     literal values for section/answer_type; difficulty and cognitive_level in
     range; id format fr-ps-<category>-<n> with unique, gap-free numbering per
     category; source has name/url/license).
  3. Auto-grading readiness: accepted_answers is a non-empty list of non-empty
     strings on every item AND on every teach-on-miss sub-question; key_terms is
     a list; model_answer/explanation/prompt are non-empty.
  4. Teach-on-miss ladder present on every item: 2-3 sub-questions, each with a
     stem, answer_type == free_response, accepted_answers, and an explanation.
  5. Category IDs are valid P/S AAMC content categories, cross-checked against
     the repository taxonomy.json (aamc_categories) when it can be located, and
     that all 12 P/S categories (6A-6C, 7A-7C, 8A-8C, 9A-9B, 10A) are covered.

Usage:
    python3 free_response_psych_soc_validate.py [--bank PATH] [--taxonomy PATH]

Exits 0 on success, 1 on any validation failure.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

# The 12 P/S AAMC content categories this bank targets. taxonomy.json is the
# source of truth; this set is the offline fallback and the coverage target.
PS_CATEGORIES = {
    "6A", "6B", "6C",
    "7A", "7B", "7C",
    "8A", "8B", "8C",
    "9A", "9B",
    "10A",
}

REQUIRED_ITEM_FIELDS = (
    "id", "section", "aamc_category", "subtopic", "answer_type", "prompt",
    "accepted_answers", "key_terms", "model_answer", "explanation",
    "difficulty", "cognitive_level", "source", "subquestions",
)
REQUIRED_SOURCE_FIELDS = ("name", "url", "license")
REQUIRED_SUBQ_FIELDS = ("stem", "answer_type", "accepted_answers", "explanation")

ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_COGNITIVE = {"recall", "application"}
LADDER_MIN, LADDER_MAX = 2, 3
ID_RE = re.compile(r"^fr-ps-(10A|[6-9][A-C])-(\d+)$")

HERE = os.path.dirname(os.path.abspath(__file__))


def fail(errors: "list[str]", msg: str) -> None:
    errors.append(msg)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def is_nonempty_str_list(value) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(x, str) and x.strip() for x in value)
    )


def find_taxonomy(explicit: "str | None") -> "str | None":
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate free_response_psych_soc.json")
    parser.add_argument("--bank", default=os.path.join(HERE, "free_response_psych_soc.json"))
    parser.add_argument("--taxonomy", default=None,
                        help="Optional explicit path to taxonomy.json for cross-checking.")
    args = parser.parse_args()

    errors: "list[str]" = []

    # 1. JSON validity.
    try:
        bank = load_json(args.bank)
    except (OSError, ValueError) as exc:
        print(f"FAILED: could not load {args.bank}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(bank, list) or not bank:
        print("FAILED: bank must be a non-empty JSON array.", file=sys.stderr)
        return 1

    seen_ids: "set[str]" = set()
    per_category: "collections.defaultdict[str, list[int]]" = collections.defaultdict(list)

    for idx, item in enumerate(bank):
        loc = item.get("id", f"index {idx}") if isinstance(item, dict) else f"index {idx}"
        if not isinstance(item, dict):
            fail(errors, f"[{loc}] item is not an object.")
            continue

        # 2. Required fields.
        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                fail(errors, f"[{loc}] missing required field '{field}'.")

        # Literal-valued fields.
        if item.get("section") != "P/S":
            fail(errors, f"[{loc}] section must be 'P/S' (found {item.get('section')!r}).")
        if item.get("answer_type") != "free_response":
            fail(errors, f"[{loc}] answer_type must be 'free_response'.")

        # id format + per-category numbering.
        item_id = item.get("id")
        cat = item.get("aamc_category")
        if isinstance(item_id, str):
            if item_id in seen_ids:
                fail(errors, f"[{loc}] duplicate item id.")
            seen_ids.add(item_id)
            m = ID_RE.match(item_id)
            if not m:
                fail(errors, f"[{loc}] id does not match fr-ps-<category>-<n>.")
            else:
                if cat is not None and m.group(1) != cat:
                    fail(errors, f"[{loc}] id category '{m.group(1)}' != aamc_category '{cat}'.")
                per_category[m.group(1)].append(int(m.group(2)))

        # Category validity (against the P/S set; taxonomy cross-check below).
        if cat is not None and cat not in PS_CATEGORIES:
            fail(errors, f"[{loc}] aamc_category '{cat}' is not a P/S content category.")

        # difficulty / cognitive_level.
        if item.get("difficulty") not in ALLOWED_DIFFICULTY:
            fail(errors, f"[{loc}] difficulty '{item.get('difficulty')}' not in {sorted(ALLOWED_DIFFICULTY)}.")
        if item.get("cognitive_level") not in ALLOWED_COGNITIVE:
            fail(errors, f"[{loc}] cognitive_level '{item.get('cognitive_level')}' not in {sorted(ALLOWED_COGNITIVE)}.")

        # 3. Auto-grading readiness.
        for field in ("prompt", "model_answer", "explanation", "subtopic"):
            if not (isinstance(item.get(field), str) and item.get(field).strip()):
                fail(errors, f"[{loc}] '{field}' must be a non-empty string.")
        if not is_nonempty_str_list(item.get("accepted_answers")):
            fail(errors, f"[{loc}] accepted_answers must be a non-empty list of non-empty strings.")
        if not isinstance(item.get("key_terms"), list) or not is_nonempty_str_list(item.get("key_terms")):
            fail(errors, f"[{loc}] key_terms must be a non-empty list of non-empty strings.")

        # source object.
        src = item.get("source")
        if not isinstance(src, dict):
            fail(errors, f"[{loc}] source must be an object.")
        else:
            for field in REQUIRED_SOURCE_FIELDS:
                if not (isinstance(src.get(field), str) and src.get(field).strip()):
                    fail(errors, f"[{loc}] source.{field} must be a non-empty string.")

        # 4. Teach-on-miss ladder.
        subs = item.get("subquestions")
        if not isinstance(subs, list):
            fail(errors, f"[{loc}] subquestions must be a list.")
        else:
            if not (LADDER_MIN <= len(subs) <= LADDER_MAX):
                fail(errors, f"[{loc}] ladder must have {LADDER_MIN}-{LADDER_MAX} steps (found {len(subs)}).")
            for j, sub in enumerate(subs):
                sloc = f"{loc} sub[{j}]"
                if not isinstance(sub, dict):
                    fail(errors, f"[{sloc}] sub-question is not an object.")
                    continue
                for field in REQUIRED_SUBQ_FIELDS:
                    if field not in sub:
                        fail(errors, f"[{sloc}] missing '{field}'.")
                if sub.get("answer_type") != "free_response":
                    fail(errors, f"[{sloc}] answer_type must be 'free_response'.")
                if not (isinstance(sub.get("stem"), str) and sub.get("stem").strip()):
                    fail(errors, f"[{sloc}] stem must be a non-empty string.")
                if not is_nonempty_str_list(sub.get("accepted_answers")):
                    fail(errors, f"[{sloc}] accepted_answers must be a non-empty list of non-empty strings.")
                if not (isinstance(sub.get("explanation"), str) and sub.get("explanation").strip()):
                    fail(errors, f"[{sloc}] explanation must be a non-empty string.")

    # Per-category numbering must be 1..N with no gaps or duplicates.
    for cat, nums in per_category.items():
        expected = list(range(1, len(nums) + 1))
        if sorted(nums) != expected:
            fail(errors, f"[{cat}] item numbers are not a gap-free 1..N sequence: {sorted(nums)}")

    # 5. Coverage + taxonomy cross-check.
    covered = set(per_category)
    missing = sorted(PS_CATEGORIES - covered, key=lambda c: (int(c[:-1]), c[-1]))
    if missing:
        fail(errors, f"P/S categories with NO items: {missing}")

    taxonomy_path = find_taxonomy(args.taxonomy)
    if taxonomy_path:
        try:
            taxonomy = load_json(taxonomy_path)
            tax_cats = set(taxonomy.get("aamc_categories", {}))
            not_in_taxonomy = sorted(covered - tax_cats)
            if not_in_taxonomy:
                fail(errors, f"Categories used but absent from taxonomy.json: {not_in_taxonomy}")
            ps_missing_from_taxonomy = sorted(PS_CATEGORIES - tax_cats)
            if ps_missing_from_taxonomy:
                fail(errors, f"P/S categories missing from taxonomy.json: {ps_missing_from_taxonomy}")
            if not not_in_taxonomy and not ps_missing_from_taxonomy:
                print(f"Cross-checked category IDs against taxonomy.json at: {taxonomy_path}")
        except (OSError, ValueError) as exc:
            fail(errors, f"Could not read taxonomy.json at {taxonomy_path}: {exc}")
    else:
        print("taxonomy.json not found locally; used embedded P/S category set.")

    # Report.
    total = len(bank)
    print("\nCoverage report (items per P/S content category):")
    for cat in sorted(PS_CATEGORIES, key=lambda c: (int(c[:-1]), c[-1])):
        print(f"  {cat:>3}: {len(per_category.get(cat, []))}")
    print(f"\nP/S categories covered: {len(covered & PS_CATEGORIES)}/{len(PS_CATEGORIES)}")
    print(f"Total items: {total}")
    ladders = sum(len(it.get('subquestions', [])) for it in bank if isinstance(it, dict))
    print(f"Total teach-on-miss ladder steps: {ladders}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
