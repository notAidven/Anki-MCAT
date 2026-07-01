#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Standalone standard-library validator for the ReadyMCAT Chemical & Physical
Foundations (C/P) FREE-RESPONSE question bank.

Uses only the Python standard library. Given ``free_response_chem_phys.json`` it
checks, and prints a per-category / per-subtopic coverage report:

  1. JSON validity        -- the file parses as a JSON array of objects.
  2. Category IDs         -- every item.aamc_category exists in the repo's
                             taxonomy.json AND is a C/P category (4A-4E, 5A-5E).
  3. Schema shape         -- required fields present; section == "C/P";
                             answer_type == "free_response"; accepted_answers is a
                             non-empty list of non-empty unique strings;
                             key_terms is a non-empty list; model_answer and
                             explanation non-empty; difficulty / cognitive_level in
                             the allowed enums; source has name/url/license;
                             id matches 'fr-cp-<cat>-<n>'; ids are unique.
  4. Teach-on-miss ladder -- subquestions is a 2-3 step ladder; each rung has a
                             non-empty stem, answer_type == "free_response", a
                             non-empty accepted_answers list, and an explanation.
  5. Numeric answers have units -- an item whose primary accepted answer is a
                             physical quantity (starts with a number) must either
                             declare a unit via a 'unit: <U>' key_term whose unit
                             text also appears in an accepted answer, OR be marked
                             'dimensionless' in key_terms; and it must carry a
                             tolerance note ('tolerance: ...' / '+/-' / 'exact').

Run:  python3 validate_free_response_chem_phys.py [path/to/free_response_chem_phys.json]
Exit code 0 = all checks passed; 1 = one or more failures.
"""

from __future__ import annotations

import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON = os.path.join(HERE, "free_response_chem_phys.json")

CP_CATEGORIES = {"4A", "4B", "4C", "4D", "4E", "5A", "5B", "5C", "5D", "5E"}
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_COGNITIVE = {"recall", "application"}

# An accepted answer is treated as "numeric" (a quantity) when it begins with an
# optional sign and a digit (covers integers, decimals, scientific notation such
# as "6.02 x 10^23", fractions like "3/2", and ratios like "4:1"). The trailing
# negative lookahead keeps digit-led-but-non-numeric strings such as an electron
# configuration ("1s2 2s2 2p4") from being flagged as physical quantities.
NUMERIC_RE = re.compile(r"^\s*[+\-\u2212]?(?:\d[\d,]*\.?\d*|\.\d+)(?![A-Za-z])")


def load_taxonomy_categories():
    """Return (set_of_category_ids, path) from taxonomy.json searched upward, or
    (empty set, None) if not found."""
    cur = HERE
    for _ in range(8):
        candidate = os.path.join(cur, "taxonomy.json")
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as fh:
                tax = json.load(fh)
            return set(tax.get("aamc_categories", {})), candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return set(), None


def _is_numeric_answer(accepted):
    return bool(accepted) and bool(NUMERIC_RE.match(str(accepted[0])))


def _key_terms_lower(key_terms):
    return [str(k).strip().lower() for k in key_terms if isinstance(k, (str, int, float))]


def _declared_unit(key_terms):
    """Return the unit text from a 'unit: <U>' key_term, else ''."""
    for k in key_terms:
        ks = str(k).strip()
        m = re.match(r"^unit\s*:\s*(.+)$", ks, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _has_tolerance_note(key_terms):
    for k in key_terms:
        ks = str(k).strip().lower()
        if ks.startswith("tolerance") or ks.startswith("tol:") or "\u00b1" in ks \
                or "+/-" in ks or ks == "exact" or ks.startswith("exact"):
            return True
    return False


def _check_accepted(loc, accepted, errors, where="accepted_answers"):
    if not isinstance(accepted, list) or not accepted:
        errors.append(f"[{loc}] {where} must be a non-empty list.")
        return False
    for a in accepted:
        if not isinstance(a, str) or not a.strip():
            errors.append(f"[{loc}] {where} contains an empty/non-string entry.")
            return False
    if len(set(a.strip() for a in accepted)) != len(accepted):
        errors.append(f"[{loc}] {where} entries are not unique.")
    return True


def validate(items):
    errors = []
    warnings = []
    tax_cats, tax_path = load_taxonomy_categories()
    valid_cats = tax_cats if tax_cats else CP_CATEGORIES

    seen_ids = set()
    per_category = collections.Counter()
    per_subtopic = collections.Counter()
    n_sub = 0
    n_numeric = 0

    if not isinstance(items, list):
        return ["Top-level JSON is not an array."], [], {}
    if not items:
        return ["JSON array is empty."], [], {}

    for idx, it in enumerate(items):
        loc = it.get("id", f"index {idx}") if isinstance(it, dict) else f"index {idx}"
        if not isinstance(it, dict):
            errors.append(f"[{loc}] item is not an object.")
            continue

        for field in ("id", "section", "aamc_category", "subtopic", "answer_type",
                      "prompt", "accepted_answers", "key_terms", "model_answer",
                      "explanation", "difficulty", "cognitive_level", "source",
                      "subquestions"):
            if field not in it:
                errors.append(f"[{loc}] missing required field '{field}'.")

        if it.get("section") != "C/P":
            errors.append(f"[{loc}] section must be 'C/P'.")
        if it.get("answer_type") != "free_response":
            errors.append(f"[{loc}] answer_type must be 'free_response'.")

        if it.get("id") in seen_ids:
            errors.append(f"[{loc}] duplicate id.")
        seen_ids.add(it.get("id"))

        cat = it.get("aamc_category")
        per_category[cat] += 1
        if cat not in valid_cats:
            errors.append(f"[{loc}] aamc_category '{cat}' not in taxonomy.json.")
        if cat not in CP_CATEGORIES:
            errors.append(f"[{loc}] aamc_category '{cat}' is not a C/P category.")

        if not str(it.get("id", "")).startswith(f"fr-cp-{cat}-"):
            errors.append(f"[{loc}] id should start with 'fr-cp-{cat}-'.")

        if not str(it.get("subtopic", "")).strip():
            errors.append(f"[{loc}] subtopic is empty.")
        per_subtopic[(cat, it.get("subtopic"))] += 1

        if not str(it.get("prompt", "")).strip():
            errors.append(f"[{loc}] prompt is empty.")

        accepted = it.get("accepted_answers", [])
        _check_accepted(loc, accepted, errors)

        key_terms = it.get("key_terms", [])
        if not isinstance(key_terms, list) or not key_terms:
            errors.append(f"[{loc}] key_terms must be a non-empty list.")
            key_terms = []

        if not str(it.get("model_answer", "")).strip():
            errors.append(f"[{loc}] model_answer is empty.")
        if not str(it.get("explanation", "")).strip():
            errors.append(f"[{loc}] explanation is empty.")

        if it.get("difficulty") not in ALLOWED_DIFFICULTY:
            errors.append(f"[{loc}] difficulty '{it.get('difficulty')}' invalid.")
        if it.get("cognitive_level") not in ALLOWED_COGNITIVE:
            errors.append(f"[{loc}] cognitive_level '{it.get('cognitive_level')}' invalid.")

        src = it.get("source", {})
        if not isinstance(src, dict) or not all(src.get(k) for k in ("name", "url", "license")):
            errors.append(f"[{loc}] source must have non-empty name/url/license.")

        # ---- numeric-answer unit / tolerance rule ----------------------------
        if isinstance(accepted, list) and _is_numeric_answer(accepted):
            n_numeric += 1
            kt_lower = _key_terms_lower(key_terms)
            is_dimensionless = "dimensionless" in kt_lower
            if not _has_tolerance_note(key_terms):
                errors.append(f"[{loc}] numeric item lacks a tolerance note in "
                              f"key_terms (e.g. 'tolerance: +/-0.5 m/s' or 'exact').")
            if not is_dimensionless:
                unit = _declared_unit(key_terms)
                if not unit:
                    errors.append(f"[{loc}] numeric item has no unit: add a "
                                  f"'unit: <U>' key_term or mark 'dimensionless'.")
                else:
                    # the declared unit text must also appear in an accepted answer
                    if not any(unit in str(a) for a in accepted):
                        errors.append(f"[{loc}] declared unit '{unit}' does not "
                                      f"appear in any accepted answer.")

        # ---- teach-on-miss ladder -------------------------------------------
        subs = it.get("subquestions", [])
        if not isinstance(subs, list) or not (2 <= len(subs) <= 3):
            errors.append(f"[{loc}] subquestions must be a 2-3 step ladder (found "
                          f"{len(subs) if isinstance(subs, list) else 'n/a'}).")
        else:
            for j, sq in enumerate(subs):
                sloc = f"{loc}#sub{j}"
                if not isinstance(sq, dict):
                    errors.append(f"[{sloc}] ladder step is not an object.")
                    continue
                for field in ("stem", "answer_type", "accepted_answers", "explanation"):
                    if field not in sq:
                        errors.append(f"[{sloc}] missing '{field}'.")
                if sq.get("answer_type") != "free_response":
                    errors.append(f"[{sloc}] answer_type must be 'free_response'.")
                if not str(sq.get("stem", "")).strip():
                    errors.append(f"[{sloc}] stem is empty.")
                _check_accepted(sloc, sq.get("accepted_answers", []), errors)
                if not str(sq.get("explanation", "")).strip():
                    errors.append(f"[{sloc}] explanation is empty.")
                n_sub += 1

    missing = sorted(CP_CATEGORIES - set(per_category))
    if missing:
        errors.append(f"C/P categories with NO items: {missing}")

    stats = {
        "n_items": len(items),
        "n_sub": n_sub,
        "n_numeric": n_numeric,
        "per_category": per_category,
        "per_subtopic": per_subtopic,
        "tax_path": tax_path,
    }
    return errors, warnings, stats


def _print_report(stats):
    print(f"Taxonomy source: {stats.get('tax_path') or '(none found; used embedded C/P set)'}")
    per_category = stats["per_category"]
    per_subtopic = stats["per_subtopic"]
    print("\nCoverage report (items per C/P content category):")
    for cat in sorted(CP_CATEGORIES, key=lambda c: (int(c[:-1]), c[-1])):
        subs_in_cat = sorted({s for (c, s) in per_subtopic if c == cat})
        print(f"  {cat}: {per_category.get(cat, 0):>2} items across {len(subs_in_cat)} subtopics")
        for s in subs_in_cat:
            print(f"        - {s} ({per_subtopic[(cat, s)]})")
    print(f"\nMain items: {stats['n_items']} | Ladder sub-questions: {stats['n_sub']} | "
          f"Numeric items: {stats['n_numeric']}")
    covered = len(set(per_category) & CP_CATEGORIES)
    print(f"C/P categories covered: {covered}/{len(CP_CATEGORIES)}")


def main(argv):
    path = argv[1] if len(argv) > 1 else DEFAULT_JSON
    if not os.path.exists(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    try:
        with open(path, "r", encoding="utf-8") as fh:
            items = json.load(fh)
    except json.JSONDecodeError as e:
        print(f"ERROR: {path} is not valid JSON: {e}", file=sys.stderr)
        return 1

    errors, warnings, stats = validate(items)
    if stats:
        _print_report(stats)

    for w in warnings:
        print(f"  WARNING: {w}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
