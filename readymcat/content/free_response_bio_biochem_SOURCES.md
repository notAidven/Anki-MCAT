# ReadyMCAT — B/B Free-Response Bank: Sources, Licensing & Coverage

This document accompanies the **free-response (type-in answer)** MCAT practice
bank for the **Biological & Biochemical Foundations (B/B)** section. It records
the open sources each item is grounded in, the licensing position, and the
coverage/counts.

## Deliverables (all under `readymcat/content/`, `free_response_` prefix)

| File | Purpose |
| --- | --- |
| `free_response_bio_biochem.json` | The bank: a JSON array of 151 original free-response items (the consumable artifact). |
| `free_response_bio_biochem_build.py` | Authoring source of truth; hand-authored items as Python dicts, one function per AAMC category, serialized to the JSON above. |
| `free_response_validate.py` | Self-contained stdlib validator (JSON validity, item schema, auto-gradability, teach-on-miss ladder, category IDs vs `taxonomy.json`). |
| `free_response_bio_biochem_SOURCES.md` | This file. |

This bank complements the existing multiple-choice banks; every item here is
**free-response** (a short typed answer), authored on branch
`readymcat-fr-bio-biochem`.

---

## Authoring integrity & anti-leakage

- **All items are ORIGINAL**, written for ReadyMCAT and grounded in the
  free / openly-licensed sources listed below (cited per item in the JSON's
  `source` field, including the specific chapter/topic).
- **No item is copied, scraped, or closely paraphrased** from any copyrighted
  or paid question bank (UWorld, Kaplan, Blueprint, AAMC paid/official prep).
  No AAMC questions, passages, or confidential content are reproduced. The
  public AAMC *"What's on the MCAT Exam?"* outline was used **only** for the
  topic structure — i.e., the content-category IDs/names already encoded in
  `taxonomy.json`.
- **Facts and concepts are not copyrightable**, and no source's *expression*
  is reproduced. Items were written from an understanding of the underlying
  science, then attributed to the open source that teaches that concept.
- **Facts/answers are correct** to the level tested on the MCAT.

## Licensing

The **original items** in this bank are © ReadyMCAT contributors and released
under **CC BY-SA 4.0** (consistent with the ReadyMCAT diagnostic bank). Each
item additionally cites the open source whose *concept* it is grounded in.

| Source | Publisher | License | Items grounded | Usage |
| --- | --- | --- | ---: | --- |
| OpenStax Biology 2e | OpenStax, Rice University | CC BY 4.0 | 77 | Biochemistry, molecular biology, genetics, evolution, cell biology. |
| OpenStax Anatomy and Physiology 2e | OpenStax, Rice University | CC BY 4.0 | 45 | Nervous & endocrine systems and the organ systems (FC3). |
| LibreTexts Biochemistry (Fundamentals of Biochemistry) | LibreTexts | CC BY-NC-SA 4.0 | 14 | Enzyme kinetics/inhibition, amino-acid detail, metabolic pathway detail. |
| OpenStax Microbiology | OpenStax, Rice University | CC BY 4.0 | 13 | Prokaryote structure/genetics and viruses (2B). |
| OpenStax Chemistry 2e | OpenStax, Rice University | CC BY 4.0 | 2 | Acid-base behavior of amino-acid functional groups. |
| Khan Academy MCAT Collection | Khan Academy (with AAMC & RWJF) | CC BY-NC-SA | 0 (reference only) | Secondary concept reference / student review link only; no content reproduced. |
| AAMC "What's on the MCAT Exam?" outline | AAMC | Free public outline (not openly licensed) | 0 | Public topic list only (the 31 category IDs/names already in `taxonomy.json`). |

**LibreTexts note:** LibreTexts pages carry per-page licenses; the Biochemistry
material used here is CC BY-NC-SA 4.0. Because only uncopyrightable facts/
concepts were used (no expression reproduced) and ReadyMCAT is a
non-commercial educational project, this grounding is compatible; the
NonCommercial/ShareAlike obligations are noted here for transparency.

Source URLs (also in each item's `source.url`):

- OpenStax Biology 2e — https://openstax.org/details/books/biology-2e
- OpenStax Anatomy and Physiology 2e — https://openstax.org/details/books/anatomy-and-physiology-2e
- OpenStax Microbiology — https://openstax.org/details/books/microbiology
- OpenStax Chemistry 2e — https://openstax.org/details/books/chemistry-2e
- LibreTexts Biochemistry — https://bio.libretexts.org/Bookshelves/Biochemistry
- Khan Academy MCAT — https://www.khanacademy.org/test-prep/mcat

*Download OpenStax books for free at openstax.org; OpenStax content is licensed
under CC BY 4.0. All Khan Academy content is available for free at
khanacademy.org.*

---

## Auto-grading design (no AI at the grading layer)

Every item and every teach-on-miss sub-question is written for **normalized
string / key-term matching**, per the PRD:

- `accepted_answers` — a list of accepted phrasings/synonyms/abbreviations for
  the short answer (a term, a number, or a short phrase). No open-ended essay
  prompts.
- `key_terms` — term(s) that should appear for credit, usable as a fallback
  key-term match. Chosen so a lowercase, whitespace-normalized substring test
  is robust (e.g., `denatur` matches "denature"/"denaturation").
- `model_answer` — the single ideal concise answer.

A suggested grader: lowercase + trim + collapse whitespace on the student's
answer; mark correct if it matches any `accepted_answers` entry **or** contains
all `key_terms`.

## Teach-on-miss ladders (LEARN MODE / TEACH-ON-MISS)

Per the PRD's core feature, **every item includes a 2–3 rung `subquestions`
ladder** of guiding short-answer steps that walk the student to the answer
through their own retrieval instead of revealing the answer. Each rung is
itself an auto-gradable free-response step (`stem`, `accepted_answers`,
`explanation`). Total ladder rungs: **303**.

---

## Coverage summary

**Scope:** the B/B section = AAMC Foundational Concepts 1, 2, and 3, i.e.
content categories **1A–1D, 2A–2C, 3A–3B (9 categories)**. Category IDs are the
exact IDs from `taxonomy.json` and are cross-checked by the validator.

**All 9 B/B categories are covered (9/9).**

| Category | AAMC content category | Items |
| --- | --- | ---: |
| 1A | Structure/function of proteins & amino acids | 18 |
| 1B | Transmission of genetic information gene→protein | 18 |
| 1C | Heritable information across generations; genetic diversity | 15 |
| 1D | Bioenergetics & fuel-molecule metabolism | 20 |
| 2A | Assemblies of molecules, cells, groups of cells | 13 |
| 2B | Structure/growth/physiology/genetics of prokaryotes & viruses | 13 |
| 2C | Cell division, differentiation, specialization | 11 |
| 3A | Nervous & endocrine systems and coordination | 19 |
| 3B | Integrative functions of the main organ systems | 24 |
| **Total** | | **151** |

**Counts:** 151 items · 303 teach-on-miss ladder rungs ·
difficulty mix easy 41 / medium 100 / hard 10 ·
cognitive mix recall 106 / application 45.

### Subtopics per category

- **1A (18):** amino-acid stereochemistry, peptide bond, side chains, proline,
  acid-base behavior, isoelectric point, secondary structure, enzyme kinetics
  (Km), competitive & noncompetitive inhibition, enzyme classification,
  enzymes vs thermodynamics, hemoglobin, collagen, denaturation, feedback
  inhibition, aromatic residues, induced fit.
- **1B (18):** DNA bases/purines/pyrimidines, RNA vs DNA, base pairing,
  semiconservative replication, polymerase direction, primer/primase, Okazaki
  fragments, helicase/SSB/topoisomerase, start & stop codons, tRNA/anticodon,
  RNA processing, transcription, the genetic code, PCR, reverse transcription,
  lac operon, frameshift/point/nonsense mutations.
- **1C (15):** meiosis products & crossing over, Mendel's laws, genotype/
  phenotype, test cross, nondisjunction/aneuploidy, Hardy-Weinberg (equation &
  calculation), linkage/recombination, sex-linked inheritance, genetic drift/
  founder/bottleneck, fitness & selection, human chromosome number,
  incomplete dominance/codominance, speciation.
- **1D (20):** glycolysis (location, ATP/NADH yield, product, PFK-1),
  fermentation, link reaction (PDH), citric acid cycle (location, yields),
  ETC (final acceptor, location), ATP synthase/chemiosmosis, respiration ATP
  accounting, free energy/exergonic, ATP, β-oxidation, insulin/glucagon,
  glycogen, gluconeogenesis, uncoupling.
- **2A (13):** fluid mosaic model, phospholipid bilayer, osmosis, tonicity,
  Na⁺/K⁺ pump, mitochondria, ER, Golgi, lysosome, ribosome, tight/gap/
  desmosome junctions, cytoskeleton, secondary active transport.
- **2B (13):** peptidoglycan wall, Gram stain, binary fission, conjugation/
  transformation/transduction, plasmids, capsid/envelope, bacteriophages,
  lytic vs lysogenic, retroviruses, obligate intracellular parasites, growth
  curve/endospores.
- **2C (11):** S phase, mitosis phases, metaphase, anaphase, cytokinesis,
  cyclins/CDKs, p53/tumor suppressors, apoptosis, stem-cell potency,
  differentiation, cancer.
- **3A (19):** resting potential, Na⁺/K⁺ gradients, depolarization/
  repolarization, myelin/glia, nodes of Ranvier/saltatory conduction,
  neurotransmitters/synapse, neuromuscular junction, sympathetic/
  parasympathetic (vagus), hypothalamic-pituitary axis, steroid vs peptide
  hormones, calcium regulation (PTH/calcitonin), ADH, negative feedback,
  adrenal gland, reflex arc, CNS/PNS organization, synaptic summation.
- **3B (24):** cardiac blood flow/chambers/valves, SA node & conduction,
  hemoglobin/O₂ transport, alveoli/gas exchange, diaphragm/ventilation, CO₂
  transport, nephron/glomerulus, PCT reabsorption, stomach/pepsin, small-
  intestine absorption, liver/bile, pancreatic enzymes, B cells/humoral
  immunity, T cells/cell-mediated, innate vs adaptive, sarcomere, actin/
  myosin sliding filament, Ca²⁺ in contraction, osteoblasts/osteoclasts,
  menstrual cycle (LH surge), homeostasis, acid-base balance.

---

## Regenerating & validating

```bash
cd readymcat/content
python3 free_response_bio_biochem_build.py     # writes free_response_bio_biochem.json
python3 free_response_validate.py              # exits 0 on success
```

The validator finds `taxonomy.json` by walking up from `readymcat/content/` to
the repo root and cross-checks every item's `aamc_category` against the real
AAMC category IDs (and restricts them to the nine B/B categories).

## Known gaps / notes

- **Scope is intentionally B/B only** (FC1–FC3). Chem/Phys (FC4–FC5) and
  Psych/Soc (FC6–FC10) categories in `taxonomy.json` are out of scope for this
  workstream and are covered by sibling banks.
- The bank favors **discrete, unambiguously short answers** so it can be
  auto-graded without AI; multi-step quantitative reasoning is expressed
  through the ladder rungs rather than long free-form prompts.
- Difficulty skews easy/medium (as MCAT discrete type-in recall/application
  items tend to); ~7% are tagged `hard`.
- Depth is roughly proportional to exam weight and topic breadth (e.g., 3B
  spans the most organ systems and has the most items); it is not an exact
  proportional sample.
