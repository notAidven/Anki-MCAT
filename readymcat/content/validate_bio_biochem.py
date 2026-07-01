#!/usr/bin/env python3
"""Validate readymcat/content/bio_biochem.json.

Checks (fail-fast, non-zero exit on any error):
  - file is valid JSON and a non-empty array
  - every item conforms to the ReadyMCAT B/B item schema
  - every aamc_category exists in taxonomy.json (repo root)
  - correct_index values are in range for their options
  - ids are unique and match their aamc_category
  - every item has a 2-3 step subquestions ladder (each a valid MCQ)

Also prints a coverage summary (items per AAMC category and per subtopic,
plus difficulty / cognitive-level distributions).

Usage: python3 validate_bio_biochem.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BANK_PATH = os.path.join(HERE, "bio_biochem.json")
TAXONOMY_PATH = os.path.normpath(os.path.join(HERE, "..", "..", "taxonomy.json"))

SECTION = "B/B"
BB_CATEGORIES = {"1A", "1B", "1C", "1D", "2A", "2B", "2C", "3A", "3B"}
DIFFICULTIES = {"easy", "medium", "hard"}
COGNITIVE = {"recall", "application"}
REQUIRED_KEYS = {
    "id", "section", "aamc_category", "subtopic", "stem", "options",
    "correct_index", "explanation", "difficulty", "cognitive_level",
    "source", "subquestions",
}
SOURCE_KEYS = {"name", "url", "license"}
SUBQ_KEYS = {"stem", "options", "correct_index", "explanation"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    errors = []

    if not os.path.exists(TAXONOMY_PATH):
        print(f"ERROR: taxonomy.json not found at {TAXONOMY_PATH}")
        return 1
    taxonomy = load_json(TAXONOMY_PATH)
    valid_categories = set(taxonomy.get("aamc_categories", {}).keys())

    if not os.path.exists(BANK_PATH):
        print(f"ERROR: bio_biochem.json not found at {BANK_PATH}")
        return 1
    try:
        bank = load_json(BANK_PATH)
    except json.JSONDecodeError as exc:
        print(f"ERROR: bio_biochem.json is not valid JSON: {exc}")
        return 1

    if not isinstance(bank, list) or not bank:
        print("ERROR: bio_biochem.json must be a non-empty JSON array")
        return 1

    seen_ids = set()
    per_cat = Counter()
    per_subtopic = defaultdict(Counter)
    diff_dist = Counter()
    cog_dist = Counter()
    subq_total = 0

    for idx, item in enumerate(bank):
        tag = f"item[{idx}] id={item.get('id', '?')}"

        missing = REQUIRED_KEYS - set(item)
        if missing:
            errors.append(f"{tag}: missing keys {sorted(missing)}")
            continue

        cat = item["aamc_category"]
        if cat not in valid_categories:
            errors.append(f"{tag}: aamc_category '{cat}' not in taxonomy.json")
        if cat not in BB_CATEGORIES:
            errors.append(f"{tag}: aamc_category '{cat}' is not a B/B category")

        if item["section"] != SECTION:
            errors.append(f"{tag}: section must be '{SECTION}', got '{item['section']}'")

        iid = item["id"]
        if iid in seen_ids:
            errors.append(f"{tag}: duplicate id")
        seen_ids.add(iid)
        if not iid.startswith(f"bb-{cat}-"):
            errors.append(f"{tag}: id should start with 'bb-{cat}-'")

        opts = item["options"]
        if not isinstance(opts, list) or len(opts) != 4:
            errors.append(f"{tag}: options must be a list of exactly 4 choices")
        elif not all(isinstance(o, str) and o.strip() for o in opts):
            errors.append(f"{tag}: all options must be non-empty strings")

        ci = item["correct_index"]
        if not isinstance(ci, int) or not (0 <= ci <= 3):
            errors.append(f"{tag}: correct_index must be int in 0..3")

        if not item.get("stem", "").strip():
            errors.append(f"{tag}: empty stem")
        if not item.get("explanation", "").strip():
            errors.append(f"{tag}: empty explanation")

        if item["difficulty"] not in DIFFICULTIES:
            errors.append(f"{tag}: bad difficulty '{item['difficulty']}'")
        if item["cognitive_level"] not in COGNITIVE:
            errors.append(f"{tag}: bad cognitive_level '{item['cognitive_level']}'")

        src = item["source"]
        if not isinstance(src, dict) or (SOURCE_KEYS - set(src)):
            errors.append(f"{tag}: source must have keys {sorted(SOURCE_KEYS)}")
        else:
            if not src["url"].startswith("http"):
                errors.append(f"{tag}: source.url must be a URL")
            for k in SOURCE_KEYS:
                if not str(src.get(k, "")).strip():
                    errors.append(f"{tag}: source.{k} is empty")

        subqs = item["subquestions"]
        if not isinstance(subqs, list) or not (2 <= len(subqs) <= 3):
            errors.append(f"{tag}: subquestions must be a ladder of 2-3 steps")
        else:
            for j, sq in enumerate(subqs):
                stag = f"{tag} subq[{j}]"
                if not isinstance(sq, dict) or (SUBQ_KEYS - set(sq)):
                    errors.append(f"{stag}: must have keys {sorted(SUBQ_KEYS)}")
                    continue
                sopts = sq["options"]
                if not isinstance(sopts, list) or not (2 <= len(sopts) <= 4):
                    errors.append(f"{stag}: options must be a list of 2-4 choices")
                elif not all(isinstance(o, str) and o.strip() for o in sopts):
                    errors.append(f"{stag}: all options must be non-empty strings")
                sci = sq["correct_index"]
                if not isinstance(sci, int) or not isinstance(sopts, list) or not (0 <= sci < len(sopts)):
                    errors.append(f"{stag}: correct_index out of range")
                if not str(sq.get("stem", "")).strip():
                    errors.append(f"{stag}: empty stem")
                if not str(sq.get("explanation", "")).strip():
                    errors.append(f"{stag}: empty explanation")
            subq_total += len(subqs)

        per_cat[cat] += 1
        per_subtopic[cat][item.get("subtopic", "?")] += 1
        diff_dist[item["difficulty"]] += 1
        cog_dist[item["cognitive_level"]] += 1

    print("=" * 66)
    print("ReadyMCAT B/B question bank - validation & coverage")
    print("=" * 66)
    print(f"taxonomy.json : {TAXONOMY_PATH}")
    print(f"bio_biochem   : {BANK_PATH}")
    print(f"total items   : {len(bank)}")
    print(f"subquestions  : {subq_total}")
    print(f"difficulty    : {dict(diff_dist)}")
    print(f"cognitive_lvl : {dict(cog_dist)}")
    print("-" * 66)
    print("Items per AAMC content category (B/B):")
    for cat in sorted(per_cat, key=lambda c: (c[0], c)):
        name = taxonomy["aamc_categories"].get(cat, {}).get("name", "")
        print(f"  {cat}: {per_cat[cat]:>3}  {name[:52]}")
    missing_cats = sorted(BB_CATEGORIES - set(per_cat))
    if missing_cats:
        errors.append(f"No items authored for B/B categories: {missing_cats}")
    print("-" * 66)
    print("Subtopics covered per category:")
    for cat in sorted(per_subtopic, key=lambda c: (c[0], c)):
        subs = per_subtopic[cat]
        print(f"  {cat} ({len(subs)} subtopics):")
        for sub, n in sorted(subs.items()):
            print(f"      - {sub} ({n})")
    print("=" * 66)

    if errors:
        print(f"FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASSED: all items conform to schema; all categories valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
