# ReadyMCAT C/P Question Bank — Sources, Licensing, and Coverage

This document accompanies `chem_phys.json`, the pre-loaded, ORIGINAL multiple-choice
question bank for the MCAT **Chemical and Physical Foundations of Biological
Systems (C/P)** section. It covers AAMC Foundational Concepts 4 and 5 (content
categories **4A–4E** and **5A–5E**).

- **Bank:** `readymcat/content/chem_phys.json` (a JSON array of items)
- **Generator / validator:** `readymcat/content/build_chem_phys.py`
- **Main items:** 115
- **Guiding sub-questions (teach-on-miss ladder steps):** 345
- **Total MCQs:** 460
- **Every C/P content category is covered (10/10).**

---

## Authoring integrity and legal statement

- **All items are ORIGINAL**, authored for ReadyMCAT and grounded in free /
  openly licensed sources cited **per item** (see `source` on every item and its
  sub-questions are grounded in the same source).
- **No copying or close paraphrase** from any copyrighted or paid question bank
  (UWorld, Kaplan, Blueprint, AAMC paid/official prep, etc.). Facts, formulas, and
  answer keys are drawn from openly licensed textbooks; no source's _expression_
  (its specific wording or its specific questions) is reproduced. Facts, equations,
  and natural laws are not themselves copyrightable.
- **AAMC content outline** ("What's on the MCAT Exam?") is used **only** for the
  public topic list / content-category structure — the same category IDs and names
  already encoded in the repo's `taxonomy.json`. No confidential AAMC exam items
  are reproduced.
- **Deck independence:** these items are authored independently of the study deck
  (Aidan/community deck). The bank and the deck share no items, so studying one
  cannot leak answers to the other.
- **Verification:** `build_chem_phys.py` regenerates `chem_phys.json` and validates
  it (schema conformance, `aamc_category` membership cross-checked against the
  repo's `taxonomy.json`, ladder length, unique IDs). All calculation answer keys
  were spot-checked numerically.

### Suggested content license

Original ReadyMCAT items © ReadyMCAT contributors, released under **CC BY-SA 4.0**
(consistent with the diagnostic bank in `readymcat/diagnostic/`). Each item also
cites the open source whose concept it is grounded in.

---

## Schema (per item)

```json
{
    "id": "cp-<category>-<n>",
    "section": "C/P",
    "aamc_category": "<id matching taxonomy.json, e.g. 4A>",
    "subtopic": "<subtopic label>",
    "stem": "<question>",
    "options": ["<A>", "<B>", "<C>", "<D>"],
    "correct_index": 0,
    "explanation": "<why correct + why each distractor is wrong; shows the math>",
    "difficulty": "easy|medium|hard",
    "cognitive_level": "recall|application",
    "source": { "name": "...", "url": "...", "license": "..." },
    "subquestions": [
        {
            "stem": "...",
            "options": ["..."],
            "correct_index": 0,
            "explanation": "..."
        }
    ]
}
```

Every item carries a **2–3 step `subquestions` ladder** of guiding MCQs — the
teach-on-miss scaffold shown when a learner misses the main question (see the
"TEACH-ON-MISS" section of `ReadyMCAT-PRD.md`).

---

## Sources and licensing

All grounding sources are free to access and openly licensed.

| Source                          | Publisher                   | License                                                 | URL                                                   | Used for                                                                                             |
| ------------------------------- | --------------------------- | ------------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| OpenStax **College Physics 2e** | OpenStax, Rice University   | CC BY 4.0                                               | https://openstax.org/details/books/college-physics-2e | Physics items (4A, 4B fluids, 4C circuits/EM, 4D waves/optics, 4E quantum/nuclear)                   |
| OpenStax **Chemistry 2e**       | OpenStax, Rice University   | CC BY 4.0                                               | https://openstax.org/details/books/chemistry-2e       | General-chemistry items (4B gases, 4C electrochem, 4E atomic/periodic/stoich, 5A, 5B, 5E)            |
| OpenStax **Organic Chemistry**  | OpenStax, Rice University   | CC BY 4.0                                               | https://openstax.org/details/books/organic-chemistry  | Organic items (4D IR/UV-Vis spectroscopy, 5D reactivity/stereochemistry)                             |
| OpenStax **Biology 2e**         | OpenStax, Rice University   | CC BY 4.0                                               | https://openstax.org/details/books/biology-2e         | Biochemistry-overlap items (5C electrophoresis, 5D biomolecules, 5E enzyme kinetics / bioenergetics) |
| **LibreTexts Chemistry**        | LibreTexts (libretexts.org) | CC BY-NC-SA 4.0 (representative; individual pages vary) | https://chem.libretexts.org                           | Separation & purification lab techniques (5C)                                                        |
| **LibreTexts Physics**          | LibreTexts (libretexts.org) | CC BY-NC-SA 4.0 (representative; individual pages vary) | https://phys.libretexts.org                           | Supplementary physics grounding                                                                      |

**Concept reference only (not cited as a per-item source):**

- **Khan Academy MCAT collection** — used only as a free concept reference to
  confirm topic scope and typical MCAT framing. Khan Academy content is not openly
  licensed for redistribution, so it is **not** reproduced or cited as an item
  source. All citable grounding is OpenStax / LibreTexts.
- **AAMC "What's on the MCAT Exam?"** content outline — used only for the public
  topic list and the content-category IDs/names (already in `taxonomy.json`).

> **License note on LibreTexts:** LibreTexts pages carry a mix of Creative Commons
> licenses (most commonly CC BY-NC-SA 4.0). Because our items reproduce only facts
> and standard techniques — not any page's specific wording — the grounding is
> compatible with reuse; the CC BY-NC-SA 4.0 tag on LibreTexts-sourced items is the
> conservative representative license for the platform.

---

## Coverage summary

Item counts by AAMC content category (weights from `taxonomy.json`). Every item is
tagged with a distinct subtopic, so the subtopic count equals the item count in
each category.

| Category  | Name                                                                              | Weight |   Items |  Sub-Qs |
| --------- | --------------------------------------------------------------------------------- | -----: | ------: | ------: |
| 4A        | Translational motion, forces, work, energy, and equilibrium in living systems     |   2.05 |      12 |      36 |
| 4B        | Importance of fluids for the circulation of blood, gas movement, and gas exchange |   2.05 |      11 |      33 |
| 4C        | Electrochemistry and electrical circuits and their elements                       |   2.05 |      12 |      36 |
| 4D        | How light and sound interact with matter                                          |   2.05 |      11 |      33 |
| 4E        | Atoms, nuclear decay, electronic structure, and atomic chemical behavior          |   2.05 |      12 |      36 |
| 5A        | Unique nature of water and its solutions                                          |   3.08 |      11 |      33 |
| 5B        | Nature of molecules and intermolecular interactions                               |   3.08 |      11 |      33 |
| 5C        | Separation and purification methods                                               |   3.08 |       9 |      27 |
| 5D        | Structure, function, and reactivity of biologically relevant molecules            |   3.08 |      14 |      42 |
| 5E        | Principles of chemical thermodynamics and kinetics                                |   3.08 |      12 |      36 |
| **Total** |                                                                                   |        | **115** | **345** |

### Subtopics covered per category

- **4A** — Kinematics: free fall; Kinematics: projectile motion; Newton's second law;
  Friction; Inclined plane / force components; Torque and static equilibrium; Work;
  Kinetic energy; Conservation of mechanical energy; Power; Momentum and impulse;
  Simple harmonic motion.
- **4B** — Density and specific gravity; Buoyancy (Archimedes' principle);
  Hydrostatic pressure; Pascal's principle (hydraulics); Continuity equation;
  Bernoulli's principle; Viscous flow (Poiseuille's law); Ideal gas law; Dalton's law
  of partial pressures; Kinetic-molecular theory / Graham's law; Henry's law
  (gas solubility / gas exchange).
- **4C** — Coulomb's law; Electric field; Ohm's law; Resistors in series; Resistors in
  parallel; Electrical power; Capacitance; Magnetic force on a moving charge;
  Galvanic cell / cell potential; Electrolysis (Faraday's laws); Electric potential
  and energy; Resistivity.
- **4D** — Wave speed, frequency, wavelength; Sound intensity and decibels; Doppler
  effect; Standing waves and harmonics; Electromagnetic spectrum; Refraction (Snell's
  law); Total internal reflection; Thin lens equation; Magnification; Infrared
  spectroscopy; UV-Vis absorption and conjugation.
- **4E** — Atomic structure and isotopes; Electron configuration; Quantum numbers;
  Bohr model / photon emission; Photoelectric effect; Periodic trend: atomic radius;
  Periodic trend: ionization energy; Periodic trend: electronegativity; Radioactive
  decay (alpha and beta); Half-life; Stoichiometry: the mole; Stoichiometry: limiting
  reagent.
- **5A** — pH of a strong acid; pH and pOH relationship; Strong vs weak acids;
  Conjugate acid-base pairs; Buffers (Henderson-Hasselbalch); Titration equivalence
  point; Solubility product (Ksp); Properties of water (hydrogen bonding);
  Autoionization of water; Lewis acids and bases; Molarity and solution preparation.
- **5B** — Ionic vs covalent bonding; Lewis structures (valence electron count);
  VSEPR molecular geometry; VSEPR with lone pairs; Hybridization; Molecular polarity;
  Sigma and pi bonds; Intermolecular forces (ranking); Intermolecular forces and
  boiling point; Formal charge; Resonance.
- **5C** — Liquid-liquid extraction; Acid-base extraction; Distillation; Thin-layer
  chromatography (Rf); Chromatography principles; Recrystallization; Gel
  electrophoresis; Size-exclusion chromatography; Centrifugation.
- **5D** — Functional groups; Chirality and stereocenters; Isomer relationships;
  Oxidation of alcohols; Nucleophilic addition to carbonyls; Carboxylic acid acidity;
  Esterification and hydrolysis; Substitution reactions (SN1/SN2); Electrophilic
  addition (Markovnikov); Amino acids (zwitterions); Peptide bonds; Protein
  structure; Carbohydrates; Lipids.
- **5E** — Enthalpy (endo/exothermic); Hess's law; Gibbs free energy and spontaneity;
  Entropy; Calorimetry (specific heat); Rate laws and reaction order; Activation
  energy and catalysis; Reaction mechanisms (rate-determining step); Equilibrium
  constant expression; Le Chatelier's principle; Enzyme kinetics (Michaelis-Menten);
  Bioenergetics (energy coupling).

### Difficulty and cognitive-level mix

Items span `easy` / `medium` / `hard` and both `recall` and `application` cognitive
levels, with an emphasis on `application` (calculation and reasoning) items that
mirror the exam's discrete-question style. Every calculation item shows the worked
solution in its `explanation`.

---

## Rebuilding and validating

```bash
cd readymcat/content
python3 build_chem_phys.py   # regenerates chem_phys.json and validates it
```

The script exits non-zero on any validation failure and prints a per-category /
per-subtopic coverage report. It cross-checks every `aamc_category` against the
repo-root `taxonomy.json` (the source of truth for category IDs).

---

## Known gaps and future work

- **Nucleic acids** are intentionally **not** placed in 5D here: although the AAMC
  5D outline lists nucleotides, this repo's `taxonomy.json` maps DNA/RNA topics to
  category **1B** (a B/B — biochemistry — category, out of C/P scope for this bank).
  Nucleic-acid items belong in the sibling bank that owns 1B, to avoid mis-tagging.
- **Depth vs. breadth:** the bank guarantees breadth (every category and its major
  subtopics represented) with 9–14 items per category. High-yield categories
  (5A–5E, weight 3.08) and the broad 5D received extra items. Additional items per
  subtopic (e.g., multiple difficulty tiers of the same concept) are a natural
  follow-up.
- **Passage-based sets** are out of scope: all items are discrete (non-passage)
  MCQs, consistent with the MVP's unambiguous auto-grading and with the diagnostic
  bank's format.
- **LibreTexts licensing** varies page-to-page; the representative CC BY-NC-SA 4.0
  tag is used for LibreTexts-grounded items (5C). Because only facts/techniques are
  used, this does not restrict reuse of the original ReadyMCAT wording.
