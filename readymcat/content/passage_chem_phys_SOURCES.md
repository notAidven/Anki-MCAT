# ReadyMCAT C/P Passage Bank — Sources, Licensing & Coverage

This document accompanies `passage_chem_phys.json`, an **original**, passage-based,
exam-simulating multiple-choice question bank for the MCAT **Chemical and Physical
Foundations of Biological Systems (C/P)** section. It records the grounding sources,
licensing, authoring integrity, coverage, and counts, and how to validate the bank.

| File                            | What it is                                                                                          |
| ------------------------------- | --------------------------------------------------------------------------------------------------- |
| `passage_chem_phys.json`        | The question bank: a JSON array of 12 passage sets (10 passages + 2 discrete-question groups).      |
| `passage_chem_phys_validate.py` | Self-contained, dependency-free validator (structure + category IDs vs `taxonomy.json` + coverage). |
| `passage_chem_phys_SOURCES.md`  | This document.                                                                                      |

## What this is

The real MCAT C/P section is **mostly passage-based**: short experiment/scenario
passages, each followed by several questions that mix passage comprehension, content
application, and data analysis, interspersed with freestanding **discrete** questions.
This bank simulates that format across AAMC **Foundational Concepts 4 and 5**
(content categories 4A-4E and 5A-5E).

Every question also carries a **teach-on-miss ladder** (`subquestions`): a 2-3 step
sequence of guiding multiple-choice sub-questions that walk a student to the answer by
retrieval, per the "TEACH-ON-MISS" / "LEARN MODE" sections of the
[ReadyMCAT PRD](../../ReadyMCAT-PRD.md). The ladder is content only; wiring it into the
reviewer is a separate feature build.

## Authoring integrity — original content, no leakage (non-negotiable)

- **All passages and questions are ORIGINAL**, authored for ReadyMCAT.
- **No copying, scraping, or paraphrasing** from any copyrighted or paid question bank
  (UWorld, Kaplan, Blueprint) or from AAMC's paid/official practice questions, passages,
  or answer choices. None of those materials were used as a source.
- The public **AAMC "What's on the MCAT Exam?" content outline** was used **only** as a
  format/coverage blueprint — i.e., for the content-category IDs/names already encoded in
  `taxonomy.json`. No confidential or copyrighted AAMC exam content is reproduced.
- Passages are grounded in the **facts and concepts** of free / openly-licensed sources
  (facts are not copyrightable); **no source's expression is reproduced**. Each passage
  cites its grounding in a `passage_source` object (`name`, `url`, `license`).
- **All science and calculations were verified.** The bank is emitted by a builder that
  computes each numeric answer in Python and derives the keyed `correct_index` from that
  computed value, so a mis-keyed calculation or an explanation/answer mismatch would fail
  the build. `passage_chem_phys_validate.py` independently re-checks structure and
  category IDs.

## Sources & licensing

All grounding sources are free and, except where noted, openly licensed. Primary
grounding is **OpenStax** (CC BY 4.0), the most permissive base for authored derivatives.

| Source                                                        | Publisher                    | License                                                     | Use here                                                                                                                       |
| ------------------------------------------------------------- | ---------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **OpenStax College Physics 2e**                               | OpenStax, Rice Univ.         | **CC BY 4.0**                                               | Primary grounding for physics (4A-4E): mechanics, fluids, circuits, sound/optics.                                              |
| **OpenStax Chemistry 2e**                                     | OpenStax, Rice Univ.         | **CC BY 4.0**                                               | Primary grounding for general chemistry (4C electrochem, 4E nuclear/atomic, 5A/5B/5E).                                         |
| **OpenStax Organic Chemistry**                                | OpenStax, Rice Univ.         | **CC BY 4.0**                                               | Primary grounding for organic topics (5C separations, 5D reactivity/stereochemistry).                                          |
| **OpenStax Biology 2e**                                       | OpenStax, Rice Univ.         | **CC BY 4.0**                                               | Secondary grounding for gel electrophoresis (discrete item).                                                                   |
| **LibreTexts (Chemistry / Organic Chemistry Lab Techniques)** | LibreTexts (UC Davis et al.) | Openly licensed (CC BY-NC-SA / CC BY-SA)                    | Secondary conceptual reference for separation/purification methods. No text reproduced.                                        |
| **AAMC "What's on the MCAT Exam?" outline**                   | AAMC                         | Free public outline; AAMC-copyrighted (NOT openly licensed) | Used **only** for the public content-category IDs/names (already in `taxonomy.json`). No AAMC questions/passages/answers used. |

**Attribution notice (OpenStax):** "Download for free at openstax.org." OpenStax content
is licensed under CC BY 4.0.

### License of the authored content

Original passages and questions in `passage_chem_phys.json` are
**(c) ReadyMCAT, released under CC BY-SA 4.0**, consistent with the repository's
educational content. This is compatible with the CC BY 4.0 grounding sources. The
repository itself is an AGPL-3.0-or-later fork of Anki.

"MCAT" is a registered trademark of the AAMC. ReadyMCAT is unaffiliated with and
unendorsed by the AAMC, OpenStax, LibreTexts, or Khan Academy.

## Coverage

### Per passage set (grounding + AAMC category)

| Set id      | Type     | Scenario                                       | AAMC category  | Primary grounding                                    |
| ----------- | -------- | ---------------------------------------------- | -------------- | ---------------------------------------------------- |
| `psg-cp-1`  | passage  | Vertical jump / force platform                 | 4A             | College Physics 2e (mechanics, work-energy, impulse) |
| `psg-cp-2`  | passage  | Arterial stenosis + alveolar gas exchange      | 4B             | College Physics 2e (fluids, Poiseuille, Bernoulli)   |
| `psg-cp-3`  | passage  | Zn/Cu galvanic cell + DC resistor circuit      | 4C             | Chemistry 2e ch.16 + College Physics 2e (circuits)   |
| `psg-cp-4`  | passage  | Diagnostic ultrasound + fiber-optic endoscope  | 4D             | College Physics 2e (sound/Doppler, optics)           |
| `psg-cp-5`  | passage  | Nuclear medicine (Tc-99m, F-18 PET)            | 4E             | Chemistry 2e ch.21 (nuclear) + ch.6 (E = hf)         |
| `psg-cp-6`  | passage  | Blood bicarbonate buffer + weak-acid titration | 5A             | Chemistry 2e ch.14 (acid-base) + ch.11               |
| `psg-cp-7`  | passage  | Boiling points & intermolecular forces         | 5B             | Chemistry 2e ch.7-8 (VSEPR) + ch.10 (IMFs)           |
| `psg-cp-8`  | passage  | Chromatography, extraction, distillation       | 5C             | Organic Chemistry (lab techniques) + LibreTexts      |
| `psg-cp-9`  | passage  | SN1 vs SN2 substitution + stereochemistry      | 5D             | Organic Chemistry ch.11 (substitution) + ch.5        |
| `psg-cp-10` | passage  | Reaction kinetics + Gibbs free energy          | 5E             | Chemistry 2e ch.12 (kinetics) + ch.16 (thermo)       |
| `psg-cp-11` | discrete | 6 freestanding physics questions               | 4A,4B,4C,4D,4E | College Physics 2e (+ Chemistry 2e ch.6)             |
| `psg-cp-12` | discrete | 6 freestanding chemistry questions             | 5A,5B,5C,5D,5E | Chemistry 2e + Organic Chemistry (+ Biology 2e)      |

### Questions per AAMC content category

| Category | Name (from `taxonomy.json`)                                                       | Questions |
| -------- | --------------------------------------------------------------------------------- | --------- |
| 4A       | Translational motion, forces, work, energy, and equilibrium in living systems     | 7         |
| 4B       | Importance of fluids for the circulation of blood, gas movement, and gas exchange | 6         |
| 4C       | Electrochemistry and electrical circuits and their elements                       | 6         |
| 4D       | How light and sound interact with matter                                          | 6         |
| 4E       | Atoms, nuclear decay, electronic structure, and atomic chemical behavior          | 6         |
| 5A       | Unique nature of water and its solutions                                          | 6         |
| 5B       | Nature of molecules and intermolecular interactions                               | 6         |
| 5C       | Separation and purification methods                                               | 6         |
| 5D       | Structure, function, and reactivity of biologically relevant molecules            | 7         |
| 5E       | Principles of chemical thermodynamics and kinetics                                | 6         |

### Totals

- **12** passage sets (10 passages + 2 discrete-question groups).
- **62** exam-style questions (each with 4 options and one keyed answer).
- **186** teach-on-miss sub-questions (2-3 per question).
- **10 / 10** C/P content categories (4A-4E, 5A-5E) covered.
- Passages run **~239-261 words** each (target ~200-350). Discrete sets carry a short
  framing note (~85 words) instead of a full passage, as those questions are, by design,
  passage-independent.
- Question mix spans **comprehension**, **application**, and **data-analysis** cognitive
  levels and **easy / medium / hard** difficulty.

## Schema

Each element of the top-level array is a passage set:

```json
{
    "id": "psg-cp-<n>",
    "section": "C/P",
    "passage": "<original ~200-350 word passage; figures/tables described in words>",
    "passage_source": {
        "name": "<grounding>",
        "url": "<url>",
        "license": "<e.g. CC BY 4.0>"
    },
    "questions": [
        {
            "id": "psg-cp-<n>-q<k>",
            "aamc_category": "<id from taxonomy.json, one of 4A-4E/5A-5E>",
            "subtopic": "<label>",
            "stem": "<question>",
            "options": ["<A>", "<B>", "<C>", "<D>"],
            "correct_index": 0,
            "explanation": "<why correct + why distractors wrong; references passage/data>",
            "difficulty": "easy|medium|hard",
            "cognitive_level": "comprehension|application|data-analysis",
            "subquestions": [
                {
                    "stem": "<guiding MCQ step>",
                    "options": ["..."],
                    "correct_index": 0,
                    "explanation": "<...>"
                }
            ]
        }
    ]
}
```

## Validation

`passage_chem_phys_validate.py` is stdlib-only (no third-party dependencies) and checks:
valid JSON and a non-empty array; each set's required fields, id format/uniqueness,
`section == "C/P"`, a non-empty passage, a complete `passage_source`, and >= 4 questions;
each question's fields, id, `aamc_category` (a real AAMC category **cross-checked against
`taxonomy.json`** and within the C/P set), exactly 4 unique options, in-range
`correct_index`, valid difficulty/cognitive level, and a 2-3 step ladder; each
subquestion's stem, >= 2 unique options, in-range index, and explanation; and that all
ten C/P categories are covered.

```bash
# From the repository root (auto-discovers taxonomy.json by walking up):
python3 readymcat/content/passage_chem_phys_validate.py

# Or point at explicit files:
python3 readymcat/content/passage_chem_phys_validate.py \
    --bank readymcat/content/passage_chem_phys.json \
    --taxonomy taxonomy.json
```

Current status: **OK — all checks pass**; 12 sets, 62 questions, 186 sub-questions,
10/10 C/P categories, category IDs verified against `taxonomy.json`.

## Gaps & future work

- **Coverage depth vs breadth:** the bank covers all ten C/P categories with 6-7 questions
  each; a production bank would author many more passages per category and calibrate item
  difficulty against real response data.
- **No figures/images:** figures and tables are described in words (consistent with a
  text-only content format); rendered diagrams are a later enhancement.
- **CARS is out of scope** (it is a separate MCAT section with no content categories).
- **Biochemistry-flavored C/P items** (amino-acid/enzyme-heavy passages that also draw on
  Foundational Concept 1) are only lightly represented here to avoid overlap with the
  Bio/Biochem bank; the split follows the taxonomy category assignment.
- **Empirical recalibration:** authored `difficulty` labels should be re-estimated once
  real student response data exists.
