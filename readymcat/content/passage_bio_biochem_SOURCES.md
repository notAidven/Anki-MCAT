# ReadyMCAT — Biological & Biochemical Foundations (B/B) passage question bank

This document describes the sources, licensing, coverage, and counts for
[`passage_bio_biochem.json`](passage_bio_biochem.json): an **original**,
passage-based, exam-simulating multiple-choice question bank for the MCAT
**Biological and Biochemical Foundations of Living Systems (B/B)** section,
covering AAMC **Foundational Concepts 1–3** (content categories 1A–1D, 2A–2C,
3A–3B).

The real B/B section is mostly passage-based (an experiment or study with
described data, followed by a set of questions), interspersed with discrete
(standalone) questions. This bank mirrors that structure and adds ReadyMCAT's
**teach-on-miss ladder** to every question (see below).

---

## 1. Authoring integrity & legal sourcing

- **All passages and questions are original**, authored for ReadyMCAT.
- **No copyrighted or paid material was copied, scraped, or paraphrased.** In
  particular, nothing is taken from UWorld, Kaplan, Blueprint, or any AAMC
  paid/official practice question, passage, or exam. The public AAMC
  *"What's on the MCAT Exam?"* outline was used **only** as a format/coverage
  blueprint — i.e., the content-category IDs and names already encoded in
  `taxonomy.json`. No confidential AAMC content is reproduced.
- Passages are grounded in **free / openly licensed** textbooks (OpenStax and
  LibreTexts; see registry below). Facts and scientific concepts are not
  copyrightable; **no source's expression is reproduced** — the passages and
  questions are newly written, and the described experiments/data are original
  constructions built to illustrate standard, verifiable concepts.
- Each passage cites its conceptual grounding in `passage_source`
  (name, url, license). Facts were verified against these standard references.
- **Deck independence:** these items are authored independently of the study
  deck (Aidan/community decks), so studying the deck cannot leak answers here.

### Content license

Original ReadyMCAT items (c) ReadyMCAT, released under **CC BY-SA 4.0**,
consistent with the ReadyMCAT diagnostic bank. Where a passage is grounded in a
`CC BY-NC-SA 4.0` source (LibreTexts), only the underlying *concepts/facts*
were used (not any copyrightable expression), so the NonCommercial/ShareAlike
terms of that source do not attach to this original text. The same concepts are
also covered by `CC BY 4.0` OpenStax texts.

---

## 2. Source registry

| Key | Source | Publisher | License | URL | Used for |
| --- | ------ | --------- | ------- | --- | -------- |
| openstax_biology_2e | OpenStax Biology 2e | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/biology-2e | Proteins/denaturation (1A), gene expression & mutations (1B), linkage/recombination (1C), cellular respiration/oxidative phosphorylation (1D), membrane transport (2A), cell cycle & cancer (2C), discrete items |
| openstax_anatomy_physiology_2e | OpenStax Anatomy and Physiology 2e | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/anatomy-and-physiology-2e | Action potential & neuron/toxin physiology (3A), O2–hemoglobin dissociation / Bohr effect (3B), renal clearance & tubular handling (3B) |
| openstax_microbiology | OpenStax Microbiology | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/microbiology | Microbial growth curve & antibacterial drug mechanisms (2B) |
| libretexts_fundamentals_biochemistry | LibreTexts, *Fundamentals of Biochemistry* (Jakubowski and Flatt) | LibreTexts (bio.libretexts.org) | CC BY-NC-SA 4.0 (verify per page) | https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt) | Enzyme kinetics & inhibition — Michaelis–Menten, Km/Vmax, competitive vs noncompetitive, Lineweaver–Burk (1A) |
| aamc_content_outline | AAMC *"What's on the MCAT Exam?"* content outline | Association of American Medical Colleges | Free public outline; AAMC-copyrighted, NOT openly licensed | https://students-residents.aamc.org/prepare-mcat-exam/whats-mcat-exam | Public topic list / coverage blueprint only (category IDs & names, already in `taxonomy.json`). No AAMC questions/passages used. |

`taxonomy.json` (repo root) is the source of truth for the AAMC content-category
IDs/names and their exam weights; `passage_bio_biochem_validate.py` cross-checks every
`aamc_category` against it.

---

## 3. Format & the teach-on-miss ladder

Each top-level entry is a **question set**:

- an original **passage** (~200–350 words) describing an experiment or study,
  with figures/data rendered in words;
- a `passage_source` grounding block;
- **4–6 questions** mixing passage comprehension, content application, and
  data/experimental reasoning (`cognitive_level` = `comprehension` /
  `application` / `data-analysis`).

Every question additionally carries a **2–3 step `subquestions` ladder** — the
ReadyMCAT *teach-on-miss* scaffold (see `ReadyMCAT-PRD.md`, "TEACH-ON-MISS").
On a miss, the app does not reveal the answer; instead it walks the student
through these smaller guiding MCQ steps (active retrieval), then re-shows the
main question. Each rung has its own `stem`, `options`, `correct_index`, and
`explanation`.

The final entry (`psg-bb-12`) is a **discrete (standalone) question set**,
mirroring the freestanding questions interleaved between passages on the real
exam; its passage field is a short framing note (hence the validator's single
word-count warning, which is expected).

### Schema (exact)

```json
{
  "id": "psg-bb-<n>",
  "section": "B/B",
  "passage": "<original ~200-350 word passage>",
  "passage_source": { "name": "...", "url": "...", "license": "..." },
  "questions": [
    {
      "id": "psg-bb-<n>-q<k>",
      "aamc_category": "<id from taxonomy.json>",
      "subtopic": "<label>",
      "stem": "<question>",
      "options": ["A", "B", "C", "D"],
      "correct_index": 0,
      "explanation": "<why correct + why distractors wrong; references passage/data>",
      "difficulty": "easy|medium|hard",
      "cognitive_level": "comprehension|application|data-analysis",
      "subquestions": [
        { "stem": "<guiding step>", "options": ["..."], "correct_index": 0, "explanation": "<...>" }
      ]
    }
  ]
}
```

---

## 4. Coverage & counts

- **Question sets:** 12 (11 passages + 1 discrete set)
- **Questions:** 53
- **Teach-on-miss subquestions:** 107
- **Categories covered:** 9 / 9 B/B (FC 1–3) content categories
- **Difficulty spread:** easy 4, medium 39, hard 10
- **Cognitive-level spread:** comprehension 13, application 23, data-analysis 17

### Questions per AAMC content category

| Category | Name (abbrev.) | AAMC weight | # questions |
| -------- | -------------- | ----------- | ----------- |
| 1A | Proteins & amino acids | 3.53 | 11 |
| 1B | Gene → protein | 3.53 | 5 |
| 1C | Heredity & genetic diversity | 3.53 | 5 |
| 1D | Bioenergetics & metabolism | 3.53 | 6 |
| 2A | Molecules/cells assemblies (membranes, transport) | 1.71 | 4 |
| 2B | Prokaryotes & viruses | 1.71 | 4 |
| 2C | Cell division & differentiation | 1.71 | 5 |
| 3A | Nervous & endocrine systems | 3.21 | 6 |
| 3B | Main organ systems | 3.21 | 7 |

Higher-weight Foundational Concept 1 receives proportionally more items, in the
spirit of ReadyMCAT's points-at-stake weighting.

### Passage inventory

| ID | Primary category | Topic (experiment/study) | Grounding | # Q |
| -- | ---------------- | ------------------------ | --------- | --- |
| psg-bb-1 | 1A | Enzyme kinetics & inhibition (competitive vs noncompetitive; Km/Vmax; Lineweaver–Burk) | LibreTexts Biochemistry | 5 |
| psg-bb-2 | 1A | Protein folding, disulfide bonds & denaturation (Tm, urea) | OpenStax Biology 2e | 4 |
| psg-bb-3 | 1B | Mutation strains: promoter, nonsense, frameshift, silent (mRNA vs protein) | OpenStax Biology 2e | 4 |
| psg-bb-4 | 1C | Linkage & recombination testcross (map distance) | OpenStax Biology 2e | 4 |
| psg-bb-5 | 1D | Isolated-mitochondria respiration: oligomycin & DNP (chemiosmosis) | OpenStax Biology 2e | 5 |
| psg-bb-6 | 2A | Membrane transport: simple vs facilitated diffusion vs active transport | OpenStax Biology 2e | 4 |
| psg-bb-7 | 2B | Bacterial growth curve & antibiotic mechanisms | OpenStax Microbiology | 4 |
| psg-bb-8 | 2C | Flow-cytometry cell cycle, checkpoints & cancer | OpenStax Biology 2e | 4 |
| psg-bb-9 | 3A | Action potential dissected with TTX/TEA; saltatory conduction | OpenStax A&P 2e | 5 |
| psg-bb-10 | 3B (+1A) | O2–hemoglobin dissociation, cooperativity & Bohr effect | OpenStax A&P 2e | 4 |
| psg-bb-11 | 3B | Renal clearance: inulin/PAH/glucose, GFR & transport maximum | OpenStax A&P 2e | 4 |
| psg-bb-12 | discrete (1A,1B,1C,1D,2C,3A) | Standalone items across FC 1–3 | OpenStax Biology 2e / A&P 2e | 6 |

Note: a passage's questions may be tagged to more than one category when
appropriate (e.g., the hemoglobin-cooperativity item in `psg-bb-10` is a
protein-structure question tagged `1A`), exactly as the real exam blends
content across a passage.

---

## 5. Validation

`passage_bio_biochem_validate.py` is a **stdlib-only** (no third-party deps) structural
validator. It checks the exact schema (ids, `section` = `B/B`, source block,
4 unique options per question, `correct_index` in range, difficulty/
cognitive-level enums, 2–3 rung teach-on-miss ladders with valid rungs),
verifies every B/B category is covered, cross-checks `aamc_category` against
`taxonomy.json`, and prints the coverage report. Passage word-count and
question-count guidance are reported as warnings (not hard errors).

```bash
python3 readymcat/content/passage_bio_biochem_validate.py
# strict mode also fails on word/question-count warnings:
python3 readymcat/content/passage_bio_biochem_validate.py --strict
```

Exit code 0 = pass, 1 = failure. Current status: **passes** (1 expected
word-count warning for the short discrete-set framing note in `psg-bb-12`).

---

## 6. Known gaps / limitations & future work

- **3B breadth:** Category 3B spans many organ systems. This bank covers
  cardiovascular/respiratory (O2 transport) and renal in depth; digestive,
  immune, musculoskeletal, reproductive, and integumentary systems are only
  lightly touched and are natural targets for expansion.
- **2A/2B/2C depth:** Foundational Concept 2 (lower AAMC weight) has one passage
  per category; viruses (lytic/lysogenic cycles, retroviruses) and
  differentiation/stem-cell biology could each gain a dedicated passage.
- **Difficulty mix** skews to `medium`; a few more `easy` on-ramp items and
  additional `hard` multi-step data-analysis items would round out the curve.
- **Answer-position balance:** answer positions vary but are not perfectly
  uniform; the reviewer is expected to shuffle options at render time.
- **Figures:** all data/figures are described in words (per the schema). If the
  reviewer later supports images, native charts could supplement the prose.
- **Scope:** this file is B/B only. Sibling banks cover the other sections
  (see the `readymcat-passage-*` branches).
