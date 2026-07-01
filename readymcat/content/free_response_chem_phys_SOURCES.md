# ReadyMCAT C/P Free-Response Question Bank — Sources, Licensing, and Coverage

This document accompanies `free_response_chem_phys.json`, the pre-loaded, ORIGINAL
**free-response (type-in answer)** question bank for the MCAT **Chemical and
Physical Foundations of Biological Systems (C/P)** section. It is the
free-response complement to the multiple-choice bank (`chem_phys.json`) and covers
AAMC Foundational Concepts 4 and 5 (content categories **4A–4E** and **5A–5E**).

- **Bank:** `readymcat/content/free_response_chem_phys.json` (a JSON array of items)
- **Generator:** `readymcat/content/build_free_response_chem_phys.py`
- **Standalone validator:** `readymcat/content/validate_free_response_chem_phys.py`
- **Main items:** 115
- **Guiding sub-questions (teach-on-miss ladder steps):** 345
- **Numeric items (value + unit, with tolerance):** 57
- **Every C/P content category is covered (10/10).**

---

## Auto-grading design (no AI at the grading layer)

Every item has a SHORT, well-defined answer so it can be graded deterministically
with normalized string / key-term / numeric matching — no model calls required.

- **`accepted_answers`** — a list of acceptable responses, primary first, plus
  variants that a correct student might type: symbol vs. word (`Ω` / `ohm`), unit
  spacing and notation (`m/s` / `m s^-1` / `m/s^1`), sign forms (`+1` / `1+`),
  scientific notation (`1.0 × 10^5 Pa` / `100000 Pa` / `100 kPa`), and common
  synonyms. A grader should normalize case, whitespace, and unicode before matching.
- **`key_terms`** — machine-readable grading hints:
  - For **numeric** items: a `unit: <U>` entry (the unit that must appear in the
    answer) and a `tolerance: ...` entry (e.g. `tolerance: ±0.5 m/s`, `±5%`, or
    `exact` for integer/counting answers). Dimensionless quantities (pH, pKa, Keq,
    Kw, Rf, magnification, counts, ratios, oxidation/formal charge) instead carry
    the literal token `dimensionless`.
  - For **conceptual** items: the must-appear term(s) (e.g. `carboxyl`, `resonance`).
- **`model_answer`** — the ideal concise answer, including the worked calculation
  for numeric items.
- **`subquestions`** — a 2–3 step teach-on-miss ladder (see below); each rung is
  itself a short-answer item with its own `accepted_answers`.

The validator enforces that every numeric item exposes a unit (or is explicitly
`dimensionless`) and a tolerance note, so numeric auto-grading always has the
metadata it needs. All 57 numeric answer keys were verified by re-computation.

### Teach-on-miss ladder

Every item carries a **3-step `subquestions` ladder** of guiding short-answer
questions — the scaffold ReadyMCAT shows when a learner misses the main question,
so they *retrieve* their way to the answer instead of reading it (see the
"TEACH-ON-MISS" / "LEARN MODE" sections of `ReadyMCAT-PRD.md`).

---

## Authoring integrity and legal statement

- **All items are ORIGINAL**, authored for ReadyMCAT and grounded in free /
  openly licensed sources cited **per item** (see `source` on every item).
- **No copying or close paraphrase** from any copyrighted or paid question bank
  (UWorld, Kaplan, Blueprint, AAMC paid/official prep, etc.). Facts, formulas, and
  answer keys are drawn from openly licensed textbooks; no source's *expression*
  (its specific wording or its specific questions) is reproduced. Facts, equations,
  and natural laws are not themselves copyrightable.
- **AAMC content outline** ("What's on the MCAT Exam?") is used **only** for the
  public topic list / content-category structure — the same category IDs and names
  already encoded in the repo's `taxonomy.json`. No confidential AAMC exam items
  are reproduced.
- **Deck independence:** these items are authored independently of the study deck
  (Aidan/community deck). The bank and the deck share no items, so studying one
  cannot leak answers to the other.
- **Verification:** `build_free_response_chem_phys.py` regenerates the JSON, and
  `validate_free_response_chem_phys.py` independently validates it (JSON validity,
  `aamc_category` cross-checked against `taxonomy.json`, `accepted_answers` +
  ladder present, numeric answers carry a unit/tolerance). All numeric answer keys
  were spot-checked numerically.

### Suggested content license

Original ReadyMCAT items © ReadyMCAT contributors, released under **CC BY-SA 4.0**
(consistent with the diagnostic and multiple-choice banks). Each item also cites
the open source whose concept it is grounded in.

---

## Schema (per item)

```json
{
  "id": "fr-cp-<category>-<n>",
  "section": "C/P",
  "aamc_category": "<id matching taxonomy.json, e.g. 4A>",
  "subtopic": "<subtopic label>",
  "answer_type": "free_response",
  "prompt": "<question requiring a short typed answer; states required units for numeric answers>",
  "accepted_answers": ["<primary>", "<variant>", "..."],
  "key_terms": ["<must-appear term OR 'unit: <U>' / 'tolerance: ...' / 'dimensionless'>", "..."],
  "model_answer": "<ideal concise answer, incl. the calculation for numeric items>",
  "explanation": "<why + brief elaboration>",
  "difficulty": "easy|medium|hard",
  "cognitive_level": "recall|application",
  "source": {"name": "...", "url": "...", "license": "..."},
  "subquestions": [
    {"stem": "<guiding step>", "answer_type": "free_response",
     "accepted_answers": ["..."], "explanation": "<...>"}
  ]
}
```

---

## Sources and licensing

All grounding sources are free to access and openly licensed.

| Source | Publisher | License | URL | Used for |
|---|---|---|---|---|
| OpenStax **College Physics 2e** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/college-physics-2e | Physics items (4A motion/energy, 4B fluids, 4C electrostatics/circuits/magnetism, 4D waves/optics, 4E quantum/nuclear) |
| OpenStax **Chemistry 2e** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/chemistry-2e | General-chemistry items (4B gases, 4C electrochemistry, 4E atomic/periodic/stoichiometry, 5A, 5B, 5E) |
| OpenStax **Organic Chemistry** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/organic-chemistry | Organic items (4D IR/UV-Vis spectroscopy, 5D reactivity/stereochemistry/biomolecules) |
| OpenStax **Biology 2e** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/biology-2e | Biochemistry-overlap items (5C gel electrophoresis, 5D protein/carbohydrate/lipid structure, 5E enzyme kinetics / bioenergetics) |
| **LibreTexts Chemistry** | LibreTexts (libretexts.org) | CC BY-NC-SA 4.0 (representative; individual pages vary) | https://chem.libretexts.org | Separation & purification lab techniques (5C) |
| **LibreTexts Physics** | LibreTexts (libretexts.org) | CC BY-NC-SA 4.0 (representative; individual pages vary) | https://phys.libretexts.org | Supplementary physics grounding |

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
each category. Every item carries a 3-step ladder.

| Category | Name | Weight | Items | Sub-Qs |
|---|---|---:|---:|---:|
| 4A | Translational motion, forces, work, energy, and equilibrium in living systems | 2.05 | 12 | 36 |
| 4B | Importance of fluids for the circulation of blood, gas movement, and gas exchange | 2.05 | 11 | 33 |
| 4C | Electrochemistry and electrical circuits and their elements | 2.05 | 12 | 36 |
| 4D | How light and sound interact with matter | 2.05 | 11 | 33 |
| 4E | Atoms, nuclear decay, electronic structure, and atomic chemical behavior | 2.05 | 12 | 36 |
| 5A | Unique nature of water and its solutions | 3.08 | 11 | 33 |
| 5B | Nature of molecules and intermolecular interactions | 3.08 | 11 | 33 |
| 5C | Separation and purification methods | 3.08 | 9 | 27 |
| 5D | Structure, function, and reactivity of biologically relevant molecules | 3.08 | 14 | 42 |
| 5E | Principles of chemical thermodynamics and kinetics | 3.08 | 12 | 36 |
| **Total** | | | **115** | **345** |

### Subtopics covered per category

- **4A** — Kinematics: free fall; Kinematics: projectile motion; Newton's second
  law; Friction; Inclined plane; Torque and static equilibrium; Work by a constant
  force; Kinetic energy; Conservation of mechanical energy; Power; Momentum and
  impulse; Simple harmonic motion (pendulum).
- **4B** — Density and specific gravity; Buoyancy (Archimedes' principle);
  Hydrostatic (gauge) pressure; Pascal's principle (hydraulics); Continuity
  equation; Bernoulli's principle; Viscous flow (Poiseuille's law); Ideal gas law;
  Dalton's law of partial pressures; Kinetic-molecular theory / Graham's law;
  Henry's law (gas solubility).
- **4C** — Coulomb's law; Electric field; Ohm's law; Resistors in series; Resistors
  in parallel; Electrical power; Capacitance; Magnetic force on a moving charge;
  Galvanic cell potential; Electrolysis (Faraday's laws); Electric potential
  energy; Resistivity of a wire.
- **4D** — Wave speed, frequency, wavelength; Sound intensity and decibels; Doppler
  effect; Standing waves and harmonics; Electromagnetic spectrum; Refraction
  (Snell's law); Total internal reflection; Thin lens equation; Magnification;
  Infrared spectroscopy; UV-Vis absorption and conjugation.
- **4E** — Atomic structure and isotopes; Electron configuration; Quantum numbers /
  shells; Bohr model / photon energy; Photoelectric effect; Periodic trend: atomic
  radius; Periodic trend: ionization energy; Periodic trend: electronegativity;
  Radioactive decay (alpha); Half-life; Stoichiometry: the mole; Stoichiometry:
  limiting reagent.
- **5A** — pH of a strong acid; pH and pOH relationship; Strong vs weak acids;
  Conjugate acid-base pairs; Buffers (Henderson-Hasselbalch); Titration equivalence
  point; Solubility product (Ksp); Properties of water (hydrogen bonding);
  Autoionization of water (Kw); Lewis acids and bases; Molarity and solution
  preparation.
- **5B** — Ionic vs covalent bonding; Lewis structures (valence electron count);
  VSEPR molecular geometry; VSEPR with lone pairs; Hybridization; Molecular
  polarity; Sigma and pi bonds; Intermolecular forces (ranking); Intermolecular
  forces and boiling point; Formal charge; Resonance.
- **5C** — Liquid-liquid extraction; Acid-base extraction; Distillation; Thin-layer
  chromatography (Rf); Chromatography principles; Recrystallization; Gel
  electrophoresis; Size-exclusion chromatography; Centrifugation.
- **5D** — Functional groups; Chirality and stereocenters; Isomer relationships;
  Oxidation of alcohols; Nucleophilic addition to carbonyls; Carboxylic acid
  acidity; Esterification and hydrolysis; Substitution reactions (SN1/SN2);
  Electrophilic addition (Markovnikov); Amino acids (zwitterions); Peptide bonds;
  Protein structure; Carbohydrates; Lipids.
- **5E** — Enthalpy (endothermic/exothermic); Hess's law; Gibbs free energy and
  spontaneity; Entropy; Calorimetry (specific heat); Rate laws and reaction order;
  Activation energy and catalysis; Reaction mechanisms (rate-determining step);
  Equilibrium constant expression; Le Chatelier's principle; Enzyme kinetics
  (Michaelis-Menten); Bioenergetics (energy coupling).

### Difficulty and cognitive-level mix

Items span `easy` / `medium` / `hard` and both `recall` and `application` cognitive
levels, with an emphasis on `application` (calculation and reasoning). Every
numeric item shows the worked solution in its `model_answer`.

---

## Rebuilding and validating

```bash
cd readymcat/content
python3 build_free_response_chem_phys.py          # regenerates the JSON, then validates
python3 validate_free_response_chem_phys.py        # validate the committed JSON on its own
```

Both scripts use only the Python standard library. They exit non-zero on any
validation failure and print a per-category / per-subtopic coverage report. The
validator cross-checks every `aamc_category` against the repo-root `taxonomy.json`
(the source of truth for category IDs), confirms `accepted_answers` and the 2–3
step ladder are present, and confirms numeric items carry a unit (or `dimensionless`)
plus a tolerance note.

---

## Known gaps and future work

- **Nucleic acids** are intentionally **not** placed in 5D here: although the AAMC
  5D outline lists nucleotides, this repo's `taxonomy.json` maps DNA/RNA topics to
  category **1B** (a Bio/Biochem category, out of C/P scope for this bank).
  Nucleic-acid items belong in the sibling bank that owns 1B.
- **Depth vs. breadth:** the bank guarantees breadth (every category and its major
  subtopics, one distinct subtopic per item) with 9–14 items per category. The
  high-yield 5-series categories (weight 3.08) and the broad 5D received extra
  items. Additional items per subtopic (multiple difficulty tiers of the same
  concept) are a natural follow-up.
- **Answer variants:** `accepted_answers` aim to cover the common correct typings,
  but graders should still normalize case/whitespace/unicode and parse numeric
  values with the stated tolerance rather than relying on exact string equality.
- **Passage-based sets** are out of scope: all items are discrete (non-passage),
  consistent with the MVP's unambiguous auto-grading and the other ReadyMCAT banks.
- **LibreTexts licensing** varies page-to-page; the representative CC BY-NC-SA 4.0
  tag is used for LibreTexts-grounded items (5C). Because only facts/techniques are
  used, this does not restrict reuse of the original ReadyMCAT wording.
