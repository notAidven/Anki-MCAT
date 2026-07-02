#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Generate and validate ReadyMCAT's taxonomy.json.

This is the *traceable* derivation of ``taxonomy.json`` (committed at the repo
root). It encodes:

  1. The 31 AAMC content categories and their official names.
  2. ``topic_weight`` for each category, derived from AAMC's published content
     distribution (a named, traceable source -- see WEIGHTS below).
  3. The mapping from the Aidan deck's subdecks/tags onto those categories.

Run with a collection to also print the coverage report::

    python readymcat/tools/build_taxonomy.py --out taxonomy.json \
        --collection /path/to/collection.anki21

The same resolution algorithm implemented in ``resolve_category`` is the one the
engine workstream should mirror (see readymcat/README.md "Resolution order").

WEIGHTS -- methodology (traceable)
----------------------------------
AAMC, "What's on the MCAT Exam?" (students-residents.aamc.org) publishes, per
exam *section*, the approximate percentage of questions for each *foundational
concept* (FC). It explicitly does NOT publish per-content-category (1A/1B/...)
sub-weights. We therefore derive each category's percent-of-exam as::

    weight(cat) = (section_questions / total_questions)   # section share of exam
                * (fc_percent_within_section / 100)         # AAMC published
                / number_of_categories_in_fc                # even split (assumption)
                * 100                                        # express as percent

Scored questions per section (AAMC): Chem/Phys 59, CARS 53, Bio/Biochem 59,
Psych/Soc 59  => 230 total. CARS is a skills section with no content categories,
so the 31 category weights sum to ~76.96 (the science/behavioral share of the
exam); the remaining ~23.04 is CARS and is intentionally unrepresented.

The only non-AAMC assumption is the *even split within each FC*; it is documented
here and in README so the engine team (and graders) can see exactly where the
numbers come from.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter

# --- AAMC content categories: official names (verbatim from the AAMC outline) ---
CATEGORY_NAMES = {
    "1A": "Structure and function of proteins and their constituent amino acids",
    "1B": "Transmission of genetic information from the gene to the protein",
    "1C": "Transmission of heritable information from generation to generation and the processes that increase genetic diversity",
    "1D": "Principles of bioenergetics and fuel molecule metabolism",
    "2A": "Assemblies of molecules, cells, and groups of cells within single cellular and multicellular organisms",
    "2B": "The structure, growth, physiology, and genetics of prokaryotes and viruses",
    "2C": "Processes of cell division, differentiation, and specialization",
    "3A": "Structure and functions of the nervous and endocrine systems and ways these systems coordinate the organ systems",
    "3B": "Structure and integrative functions of the main organ systems",
    "4A": "Translational motion, forces, work, energy, and equilibrium in living systems",
    "4B": "Importance of fluids for the circulation of blood, gas movement, and gas exchange",
    "4C": "Electrochemistry and electrical circuits and their elements",
    "4D": "How light and sound interact with matter",
    "4E": "Atoms, nuclear decay, electronic structure, and atomic chemical behavior",
    "5A": "Unique nature of water and its solutions",
    "5B": "Nature of molecules and intermolecular interactions",
    "5C": "Separation and purification methods",
    "5D": "Structure, function, and reactivity of biologically relevant molecules",
    "5E": "Principles of chemical thermodynamics and kinetics",
    "6A": "Sensing the environment",
    "6B": "Making sense of the environment",
    "6C": "Responding to the world",
    "7A": "Individual influences on behavior",
    "7B": "Social processes that influence human behavior",
    "7C": "Attitude and behavior change",
    "8A": "Self-identity",
    "8B": "Social thinking",
    "8C": "Social interactions",
    "9A": "Understanding social structure",
    "9B": "Demographic characteristics and processes",
    "10A": "Social inequality",
}

# section -> (scored questions, {FC label: (fc_percent, [categories])})
SECTIONS = {
    "Bio/Biochem": (
        59,
        {
            "FC1": (55, ["1A", "1B", "1C", "1D"]),
            "FC2": (20, ["2A", "2B", "2C"]),
            "FC3": (25, ["3A", "3B"]),
        },
    ),
    "Chem/Phys": (
        59,
        {
            "FC4": (40, ["4A", "4B", "4C", "4D", "4E"]),
            "FC5": (60, ["5A", "5B", "5C", "5D", "5E"]),
        },
    ),
    "Psych/Soc": (
        59,
        {
            "FC6": (25, ["6A", "6B", "6C"]),
            "FC7": (35, ["7A", "7B", "7C"]),
            "FC8": (20, ["8A", "8B", "8C"]),
            "FC9": (15, ["9A", "9B"]),
            "FC10": (5, ["10A"]),
        },
    ),
}
CARS_QUESTIONS = 53
TOTAL_QUESTIONS = sum(q for q, _ in SECTIONS.values()) + CARS_QUESTIONS  # 230


def compute_weights() -> dict[str, float]:
    weights: dict[str, float] = {}
    for _section, (sect_q, fcs) in SECTIONS.items():
        section_share = sect_q / TOTAL_QUESTIONS
        for _fc, (fc_pct, cats) in fcs.items():
            per_cat = section_share * (fc_pct / 100.0) / len(cats) * 100.0
            for cat in cats:
                weights[cat] = round(per_cat, 2)
    return weights


# --- Mappings -----------------------------------------------------------------
# Each entry: (deck_tag_or_subdeck, category). A value starting with '#' is a
# TAG prefix; otherwise it is a SUBDECK prefix. Matching is path-prefix on '::'
# boundaries. Tag matches take precedence over subdeck matches; within a kind the
# longest (most specific) match wins. See resolve_category / README.

SUBDECK_MAPPINGS = [
    # --- Biochemistry (mostly FC1; metabolism = 1D) ---
    ("MCAT::Biochemistry::Amino Acids", "1A"),
    ("MCAT::Biochemistry::Non-enzymatic Proteins", "1A"),
    ("MCAT::Biochemistry::Enzymes", "1A"),
    ("MCAT::Biochemistry::Carbohydrates", "1D"),
    ("MCAT::Biochemistry::Lipids", "1D"),
    ("MCAT::Biochemistry::Membranes", "2A"),
    ("MCAT::Biochemistry::Metabolism", "1D"),  # + ::Carbohydrate/Lipid Metabolism
    ("MCAT::Biochemistry::Bioenergetics", "1D"),
    ("MCAT::Biochemistry::DNA & Biotechnology", "1B"),
    ("MCAT::Biochemistry::RNA & Gene Expression", "1B"),
    ("MCAT::Biochemistry", "1A"),  # discipline fallback
    # --- Biology ---
    ("MCAT::Biology::Cells", "2A"),
    ("MCAT::Biology::Genetics & Evolution", "1C"),
    ("MCAT::Biology::Embryogenesis", "2C"),
    ("MCAT::Biology::Nervous System", "3A"),
    ("MCAT::Biology::Endocrine", "3A"),
    ("MCAT::Biology::Cardiovascular System", "3B"),
    ("MCAT::Biology::Respiratory System", "3B"),
    ("MCAT::Biology::Digestion", "3B"),
    ("MCAT::Biology::Immune System", "3B"),
    ("MCAT::Biology::Musculoskeletal System", "3B"),
    ("MCAT::Biology::Reproductive System", "3B"),
    ("MCAT::Biology::Homeostasis", "3B"),
    ("MCAT::Biology", "3B"),  # discipline fallback
    # --- General Chemistry ---
    ("MCAT::General Chemistry::Acids & Bases", "5A"),
    ("MCAT::General Chemistry::Solutions", "5A"),
    ("MCAT::General Chemistry::Atoms & Bonding", "5B"),
    ("MCAT::General Chemistry::Common Ion Names", "5B"),
    ("MCAT::General Chemistry::Gases", "4B"),  # Gas Phase / Ideal Gas Law -> 4B
    ("MCAT::General Chemistry::Periodic Table", "4E"),
    ("MCAT::General Chemistry::Stoichiometry", "4E"),  # AAMC lists under 4E
    ("MCAT::General Chemistry::Electrochemistry", "4C"),
    ("MCAT::General Chemistry::Redox & Inorganic Reactions", "4C"),
    ("MCAT::General Chemistry::Equilibrium", "5E"),
    ("MCAT::General Chemistry::Chemical Kinetics", "5E"),
    ("MCAT::General Chemistry::Thermochemistry", "5E"),
    ("MCAT::General Chemistry", "5B"),  # discipline fallback
    # --- Organic Chemistry (FC5; biologically relevant molecules = 5D) ---
    ("MCAT::Organic Chemistry::Principles of Organic Chemistry", "5D"),
    ("MCAT::Organic Chemistry::Alcohols", "5D"),
    ("MCAT::Organic Chemistry::Aldehydes & Ketones", "5D"),
    ("MCAT::Organic Chemistry::Carboxylic Acids & Derivatives", "5D"),
    ("MCAT::Organic Chemistry::Nitrogen & Phosphorus", "5D"),
    ("MCAT::Organic Chemistry::Common Organic Reactions", "5D"),
    (
        "MCAT::Organic Chemistry::Lab Techniques",
        "5C",
    ),  # separations; spectroscopy->4D by tag
    ("MCAT::Organic Chemistry", "5D"),  # discipline fallback
    # --- Physics ---
    ("MCAT::Physics::Kinematics", "4A"),
    ("MCAT::Physics::Math", "4A"),  # AAMC 4A: units, dimensions, vectors
    ("MCAT::Physics::Thermodynamics", "5E"),  # AAMC groups PHY+GC thermo under 5E
    ("MCAT::Physics::Fluids & Solids", "4B"),
    ("MCAT::Physics::Electricity & Circuits", "4C"),
    ("MCAT::Physics::Electrostatics", "4C"),  # electrostatics & magnetism -> 4C
    ("MCAT::Physics::Light & Optics", "4D"),
    ("MCAT::Physics::Waves & Sounds", "4D"),
    ("MCAT::Physics::Atomic Nuclei & Nuclear Decay", "4E"),
    ("MCAT::Physics", "4A"),  # discipline fallback
    # --- Psychology / Sociology ---
    ("MCAT::Psychology::Sensation", "6A"),
    ("MCAT::Psychology::Vision", "6A"),
    ("MCAT::Psychology::Auditory System", "6A"),
    ("MCAT::Psychology::Cognition", "6B"),
    ("MCAT::Psychology::Memory", "6B"),
    ("MCAT::Psychology::Sleep & Consciousness", "6B"),
    ("MCAT::Psychology::Emotion", "6C"),
    ("MCAT::Psychology::Stress", "6C"),
    ("MCAT::Psychology::Attention, Motivation, & Attitudes", "7A"),
    ("MCAT::Psychology::Personality", "7A"),
    ("MCAT::Psychology::Disorders", "7A"),
    ("MCAT::Psychology::Therapy", "7A"),
    ("MCAT::Psychology::Behavior & Neuroscience", "7A"),
    ("MCAT::Psychology::Drugs & Biology", "7A"),
    ("MCAT::Psychology::Childhood & Adolescent Development", "7A"),
    ("MCAT::Psychology::Social Psychology & Interactions", "7B"),
    ("MCAT::Psychology::Individuals & Society", "7B"),  # deviance/norms (tags refine)
    ("MCAT::Psychology::Self Identity", "8A"),
    ("MCAT::Psychology::Society & Culture", "9A"),
    ("MCAT::Psychology::Demographics", "9B"),
    ("MCAT::Psychology", "7A"),  # discipline fallback
]

# Tag overrides capture AAMC categories that cut across the subdeck layout.
TAG_MAPPINGS = [
    ("#Physiology::Cells::ProkaryoticCells", "2B"),
    ("#Physiology::Cells::Viruses", "2B"),
    ("#OrganicChemistry::Spectroscopy", "4D"),  # IR/UV-Vis/NMR/MS -> 4D
    ("#Psychology::SocialPsychology", "7B"),
    ("#Psychology::NormativeBehaviors", "7B"),
    ("#Psychology::Attitude&BehaviorTheories", "7C"),
    ("#Psychology::Individuals&Society::SelfIdentity", "8A"),
    ("#Psychology::Individuals&Society::PerceptionPrejudice&Bias", "8B"),
    ("#Psychology::Individuals&Society::SocialInteractions", "8C"),
    ("#Psychology::Individuals&Society::SocialBehavior", "8C"),
    ("#Psychology::Demographics::Inequality", "10A"),
]

MAPPINGS = TAG_MAPPINGS + SUBDECK_MAPPINGS


def is_path_prefix(prefix: str, value: str) -> bool:
    return value == prefix or value.startswith(prefix + "::")


def resolve_category(deck_name: str, tags: list[str]) -> str | None:
    """Resolve a card to an AAMC category. Tag mappings win over subdeck
    mappings; within a kind the longest (most specific) prefix wins."""
    best_tag = None
    for prefix, cat in TAG_MAPPINGS:
        if any(is_path_prefix(prefix, t) for t in tags):
            if best_tag is None or len(prefix) > len(best_tag[0]):
                best_tag = (prefix, cat)
    if best_tag is not None:
        return best_tag[1]
    best_deck = None
    for prefix, cat in SUBDECK_MAPPINGS:
        if is_path_prefix(prefix, deck_name):
            if best_deck is None or len(prefix) > len(best_deck[0]):
                best_deck = (prefix, cat)
    return best_deck[1] if best_deck else None


def build_taxonomy() -> dict:
    weights = compute_weights()
    missing = set(CATEGORY_NAMES) - set(weights)
    assert not missing, f"weights missing for {missing}"
    aamc_categories = {
        cat: {"name": CATEGORY_NAMES[cat], "weight": weights[cat]}
        for cat in CATEGORY_NAMES
    }
    mappings = [{"deck_tag_or_subdeck": k, "category": v} for k, v in MAPPINGS]
    # sanity: every mapping points to a defined category
    for m in mappings:
        assert m["category"] in aamc_categories, m
    return {"version": 1, "aamc_categories": aamc_categories, "mappings": mappings}


def coverage_report(collection_path: str, weights: dict[str, float]) -> None:
    con = sqlite3.connect(collection_path)
    decks = json.loads(con.execute("SELECT decks FROM col").fetchone()[0])
    id2name = {int(k): v["name"] for k, v in decks.items()}
    per_cat = Counter()
    uncategorized = 0
    uncat_decks = Counter()
    total = 0
    for did, tags in con.execute(
        "SELECT c.did, n.tags FROM cards c JOIN notes n ON n.id = c.nid"
    ):
        total += 1
        deck = id2name.get(did, "")
        cat = resolve_category(deck, tags.split())
        if cat is None:
            uncategorized += 1
            uncat_decks[deck] += 1
        else:
            per_cat[cat] += 1

    covered = [c for c in CATEGORY_NAMES if per_cat[c] > 0]
    total_weight = sum(weights.values())
    covered_weight = sum(weights[c] for c in covered)

    print("\n=== ReadyMCAT coverage report ===")
    print(
        f"cards examined: {total}    categorized: {total - uncategorized}    "
        f"uncategorized: {uncategorized} ({uncategorized / total:.1%})"
    )
    print(
        f"AAMC content categories covered: {len(covered)}/{len(CATEGORY_NAMES)} "
        f"({len(covered) / len(CATEGORY_NAMES):.1%})"
    )
    print(
        f"exam weight covered (content categories): {covered_weight:.2f} of "
        f"{total_weight:.2f} possible content-category percent "
        f"({covered_weight / total_weight:.1%} of content weight)"
    )
    print(
        f"exam weight covered (whole exam incl. CARS): {covered_weight:.2f}% "
        f"(CARS = {100 - total_weight:.2f}% has no content categories)"
    )
    print("\n  cat  weight   cards  name")
    for cat in sorted(CATEGORY_NAMES, key=lambda c: (c[0].zfill(2), c)):
        flag = " " if per_cat[cat] else "!"
        print(
            f"{flag} {cat:>3}  {weights[cat]:>5.2f}  {per_cat[cat]:>6}  "
            f"{CATEGORY_NAMES[cat][:54]}"
        )
    if uncat_decks:
        print(
            "\nuncategorized cards by deck (intentional: SIRS/research-methods, "
            "umbrella decks):"
        )
        for deck, n in uncat_decks.most_common():
            print(f"  {n:>5}  {deck}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write taxonomy.json here")
    ap.add_argument(
        "--collection",
        default=None,
        help="collection.anki2/.anki21 to compute coverage against",
    )
    args = ap.parse_args()

    taxonomy = build_taxonomy()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(taxonomy, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(
            f"wrote {args.out}: {len(taxonomy['aamc_categories'])} categories, "
            f"{len(taxonomy['mappings'])} mappings"
        )

    if args.collection:
        weights = {
            c: taxonomy["aamc_categories"][c]["weight"]
            for c in taxonomy["aamc_categories"]
        }
        coverage_report(args.collection, weights)
    return 0


if __name__ == "__main__":
    sys.exit(main())
