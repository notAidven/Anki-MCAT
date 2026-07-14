#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Self-contained validator for the ReadyMCAT B/B free-response bank.

No third-party dependencies. Checks:
  1. JSON validity + top-level shape (a non-empty array of item objects).
  2. Per-item schema: all required fields present and well-typed; id format
     ``fr-bb-<category>-<n>`` and unique; ``section`` == "B/B";
     ``answer_type`` == "free_response"; difficulty/cognitive_level in range;
     ``source`` has name + url + license.
  3. AUTO-GRADABILITY: every item has a non-empty ``accepted_answers`` list of
     strings, and ``key_terms`` is a list.
  4. TEACH-ON-MISS LADDER: every item has a ``subquestions`` ladder with >= 2
     rungs, each rung a free_response step with its own non-empty
     ``accepted_answers``.
  5. Category IDs are valid AAMC content categories cross-checked against
     ``taxonomy.json`` (found by walking up from this file), AND restricted to
     the Biological & Biochemical Foundations (B/B) set (1A-1D, 2A-2C, 3A-3B).
     Reports coverage of all nine B/B categories.

Usage:
    python3 free_response_validate.py [--items PATH] [--taxonomy PATH]

Exits 0 on success, 1 on any validation failure.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

# The nine Biological & Biochemical Foundations (B/B) content categories.
# taxonomy.json (repo root) is the source of truth; this is the offline
# fallback / scope restriction used when validating.
BB_CATEGORIES = {"1A", "1B", "1C", "1D", "2A", "2B", "2C", "3A", "3B"}

REQUIRED_ITEM_FIELDS = (
    "id", "section", "aamc_category", "subtopic", "answer_type", "prompt",
    "accepted_answers", "key_terms", "model_answer", "explanation",
    "difficulty", "cognitive_level", "source", "subquestions",
)
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_COGNITIVE = {"recall", "application"}
MIN_LADDER_RUNGS = 2

HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_taxonomy(explicit):
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


def is_nonempty_str_list(value):
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(x, str) and x.strip() for x in value)
    )


def validate_subquestions(subq, loc, errors):
    if not isinstance(subq, list):
        errors.append(f"[{loc}] 'subquestions' must be a list.")
        return
    if len(subq) < MIN_LADDER_RUNGS:
        errors.append(
            f"[{loc}] teach-on-miss ladder has {len(subq)} rung(s); "
            f"needs at least {MIN_LADDER_RUNGS}."
        )
    for j, rung in enumerate(subq):
        rloc = f"{loc} > subquestion[{j}]"
        if not isinstance(rung, dict):
            errors.append(f"[{rloc}] sub-question must be an object.")
            continue
        if not rung.get("stem"):
            errors.append(f"[{rloc}] missing/empty 'stem'.")
        if rung.get("answer_type") != "free_response":
            errors.append(f"[{rloc}] answer_type must be 'free_response'.")
        if not is_nonempty_str_list(rung.get("accepted_answers")):
            errors.append(f"[{rloc}] 'accepted_answers' must be a non-empty list of strings.")
        if not rung.get("explanation"):
            errors.append(f"[{rloc}] missing/empty 'explanation'.")


def validate_source(src, loc, errors):
    if not isinstance(src, dict):
        errors.append(f"[{loc}] 'source' must be an object.")
        return
    for key in ("name", "url", "license"):
        if not src.get(key):
            errors.append(f"[{loc}] source.{key} is missing/empty.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", default=os.path.join(HERE, "free_response_bio_biochem.json"))
    parser.add_argument("--taxonomy", default=None,
                        help="Optional explicit path to taxonomy.json.")
    args = parser.parse_args()

    errors = []

    # 1. JSON validity + top-level shape.
    try:
        items = load_json(args.items)
    except json.JSONDecodeError as exc:
        print(f"FAILED: {args.items} is not valid JSON: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"FAILED: cannot read {args.items}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(items, list) or not items:
        print("FAILED: top-level JSON must be a non-empty array of items.", file=sys.stderr)
        return 1

    seen_ids = set()
    per_category = collections.Counter()
    ladder_rungs = 0
    difficulty_counts = collections.Counter()
    cognitive_counts = collections.Counter()

    for idx, item in enumerate(items):
        loc = item.get("id", f"index {idx}") if isinstance(item, dict) else f"index {idx}"

        if not isinstance(item, dict):
            errors.append(f"[{loc}] item must be an object.")
            continue

        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                errors.append(f"[{loc}] missing required field '{field}'.")

        item_id = item.get("id")
        if item_id in seen_ids:
            errors.append(f"[{loc}] duplicate item id.")
        elif item_id:
            seen_ids.add(item_id)

        cat = item.get("aamc_category")
        if cat is not None:
            per_category[cat] += 1
            if cat not in BB_CATEGORIES:
                errors.append(
                    f"[{loc}] aamc_category '{cat}' is not a B/B content category "
                    f"{sorted(BB_CATEGORIES)}."
                )
            # id must encode the same category: fr-bb-<cat>-<n>
            if item_id and not str(item_id).startswith(f"fr-bb-{cat}-"):
                errors.append(f"[{loc}] id should start with 'fr-bb-{cat}-'.")

        if item.get("section") != "B/B":
            errors.append(f"[{loc}] section must be 'B/B' (got {item.get('section')!r}).")

        if item.get("answer_type") != "free_response":
            errors.append(f"[{loc}] answer_type must be 'free_response'.")

        if not is_nonempty_str_list(item.get("accepted_answers")):
            errors.append(f"[{loc}] 'accepted_answers' must be a non-empty list of strings.")

        if not isinstance(item.get("key_terms"), list):
            errors.append(f"[{loc}] 'key_terms' must be a list.")

        if not item.get("model_answer"):
            errors.append(f"[{loc}] 'model_answer' is missing/empty.")
        if not item.get("prompt"):
            errors.append(f"[{loc}] 'prompt' is missing/empty.")
        if not item.get("explanation"):
            errors.append(f"[{loc}] 'explanation' is missing/empty.")

        diff = item.get("difficulty")
        difficulty_counts[diff] += 1
        if diff not in ALLOWED_DIFFICULTY:
            errors.append(f"[{loc}] difficulty '{diff}' not in {sorted(ALLOWED_DIFFICULTY)}.")

        cog = item.get("cognitive_level")
        cognitive_counts[cog] += 1
        if cog not in ALLOWED_COGNITIVE:
            errors.append(f"[{loc}] cognitive_level '{cog}' not in {sorted(ALLOWED_COGNITIVE)}.")

        validate_source(item.get("source"), loc, errors)

        subq = item.get("subquestions")
        validate_subquestions(subq, loc, errors)
        if isinstance(subq, list):
            ladder_rungs += len(subq)

    # 5. Cross-check categories against taxonomy.json + B/B coverage.
    taxonomy_path = find_taxonomy(args.taxonomy)
    if taxonomy_path:
        taxonomy = load_json(taxonomy_path)
        tax_cats = set(taxonomy.get("aamc_categories", {}))
        unknown = sorted(set(per_category) - tax_cats)
        if unknown:
            errors.append(
                f"Categories not found in taxonomy.json ({taxonomy_path}): {unknown}"
            )
        missing_bb_in_tax = sorted(BB_CATEGORIES - tax_cats)
        if missing_bb_in_tax:
            errors.append(
                f"B/B categories missing from taxonomy.json: {missing_bb_in_tax}"
            )
        print(f"Cross-checked category IDs against taxonomy.json at: {taxonomy_path}")
    else:
        print("taxonomy.json not found locally; used embedded B/B category set.")

    uncovered = sorted(BB_CATEGORIES - set(per_category))
    if uncovered:
        errors.append(f"B/B categories with NO items: {uncovered}")

    # Report.
    print("\nCoverage (items per B/B content category):")
    for cat in sorted(BB_CATEGORIES, key=lambda c: (int(c[:-1]), c[-1])):
        print(f"  {cat:>3}: {per_category.get(cat, 0)}")
    print(f"\nB/B categories covered: {len(set(per_category) & BB_CATEGORIES)}/{len(BB_CATEGORIES)}")
    print(f"Total items: {len(items)}")
    print(f"Total teach-on-miss ladder rungs: {ladder_rungs}")
    print(f"Difficulty mix: {dict(difficulty_counts)}")
    print(f"Cognitive mix: {dict(cognitive_counts)}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
