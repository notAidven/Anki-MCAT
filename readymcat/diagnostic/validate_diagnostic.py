#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Self-contained validator for the ReadyMCAT diagnostic question bank.

Checks, with no third-party dependencies:
  1. Structural integrity of every item (required fields, 4 unique option keys,
     answer is one of those keys, source.ref resolves to the sources registry).
  2. Category coverage: every item's category is a real AAMC content category
     and all 31 categories are covered at least once.
  3. (Optional) Cross-checks the embedded category set against a taxonomy.json
     if one is found, so this stays correct even though taxonomy.json lives on
     another branch and is not present here.

Usage:
    python3 validate_diagnostic.py [--quiz PATH] [--taxonomy PATH]

Exits 0 on success, 1 on any validation failure.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

# The 31 AAMC content-category IDs, copied from taxonomy.json on branch
# readymcat-content-teach-on-miss (key: aamc_categories). taxonomy.json is the
# source of truth; this list is the offline fallback used for validation here.
EXPECTED_CATEGORIES = {
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

REQUIRED_ITEM_FIELDS = ("id", "category", "stem", "options", "answer",
                        "difficulty", "source", "rationale")
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}

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
    for _ in range(6):
        candidate = os.path.join(cur, "taxonomy.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiz", default=os.path.join(HERE, "diagnostic_quiz.json"))
    parser.add_argument("--taxonomy", default=None,
                        help="Optional path to taxonomy.json for cross-checking.")
    args = parser.parse_args()

    errors: list[str] = []
    quiz = load_json(args.quiz)

    sources = quiz.get("sources", {})
    if not sources:
        fail(errors, "Top-level 'sources' registry is missing or empty.")

    items = quiz.get("items", [])
    if not items:
        fail(errors, "No items found in quiz.")

    seen_ids: set[str] = set()
    per_category: collections.Counter[str] = collections.Counter()

    for idx, item in enumerate(items):
        loc = item.get("id", f"index {idx}")

        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                fail(errors, f"[{loc}] missing required field '{field}'.")

        item_id = item.get("id")
        if item_id in seen_ids:
            fail(errors, f"[{loc}] duplicate item id.")
        if item_id:
            seen_ids.add(item_id)

        cat = item.get("category")
        if cat is not None:
            per_category[cat] += 1
            if cat not in EXPECTED_CATEGORIES:
                fail(errors, f"[{loc}] category '{cat}' is not a valid AAMC content category.")

        options = item.get("options", [])
        keys = [o.get("key") for o in options]
        if len(options) != 4:
            fail(errors, f"[{loc}] expected 4 options, found {len(options)}.")
        if len(set(keys)) != len(keys):
            fail(errors, f"[{loc}] option keys are not unique: {keys}.")
        for o in options:
            if not o.get("text"):
                fail(errors, f"[{loc}] an option has empty text.")

        ans = item.get("answer")
        if ans not in keys:
            fail(errors, f"[{loc}] answer '{ans}' is not one of the option keys {keys}.")

        diff = item.get("difficulty")
        if diff not in ALLOWED_DIFFICULTY:
            fail(errors, f"[{loc}] difficulty '{diff}' not in {sorted(ALLOWED_DIFFICULTY)}.")

        src = item.get("source", {})
        ref = src.get("ref") if isinstance(src, dict) else None
        if ref not in sources:
            fail(errors, f"[{loc}] source.ref '{ref}' is not in the sources registry.")
        if isinstance(src, dict) and not src.get("location"):
            fail(errors, f"[{loc}] source.location is missing.")

        if not item.get("rationale"):
            fail(errors, f"[{loc}] rationale is empty.")

    missing = sorted(EXPECTED_CATEGORIES - set(per_category))
    if missing:
        fail(errors, f"Categories with NO items: {missing}")

    # Optional cross-check against the real taxonomy.json if available.
    taxonomy_path = find_taxonomy(args.taxonomy)
    if taxonomy_path:
        taxonomy = load_json(taxonomy_path)
        tax_cats = set(taxonomy.get("aamc_categories", {}))
        if tax_cats and tax_cats != EXPECTED_CATEGORIES:
            only_tax = sorted(tax_cats - EXPECTED_CATEGORIES)
            only_here = sorted(EXPECTED_CATEGORIES - tax_cats)
            fail(errors, f"Embedded categories disagree with {taxonomy_path}: "
                         f"only in taxonomy={only_tax}, only in validator={only_here}")
        else:
            print(f"Cross-checked against taxonomy.json at: {taxonomy_path}")
    else:
        print("taxonomy.json not found locally; used embedded AAMC category set "
              "(expected on this branch).")

    # Report.
    print("\nCoverage report (items per AAMC content category):")
    for cat in sorted(EXPECTED_CATEGORIES, key=lambda c: (int(c[:-1]), c[-1])):
        print(f"  {cat:>3}: {per_category.get(cat, 0)}")
    print(f"\nCategories covered: {len(set(per_category) & EXPECTED_CATEGORIES)}/"
          f"{len(EXPECTED_CATEGORIES)}")
    print(f"Total items: {len(items)}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
