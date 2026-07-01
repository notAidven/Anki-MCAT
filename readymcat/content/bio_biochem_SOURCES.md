# ReadyMCAT B/B Question Bank - Sources, Licensing & Coverage

This document accompanies `bio_biochem.json`, the pre-loaded, original multiple-choice
question bank for the MCAT **Biological & Biochemical Foundations of Living Systems (B/B)**
section. It records provenance, licensing, and a coverage summary so the content is
traceable and legally clean.

- **Bank file:** `readymcat/content/bio_biochem.json`
- **Validator:** `readymcat/content/validate_bio_biochem.py` (run: `python3 validate_bio_biochem.py`)
- **Total items:** 152 main MCQs, each with a 2-step teach-on-miss sub-question ladder (304 guiding MCQs).
- **AAMC categories covered:** 1A, 1B, 1C, 1D, 2A, 2B, 2C, 3A, 3B (all nine B/B content categories in `taxonomy.json`).

---

## 1. Authoring integrity (legal / sourcing)

- **All items are ORIGINAL**, written for ReadyMCAT and grounded in free / openly-licensed
  educational sources cited per item (see the `source` field on every item).
- **No copyrighted or paid question bank content** was copied, scraped, or closely
  paraphrased. Specifically, **nothing** here is derived from UWorld, Kaplan, Blueprint,
  Princeton Review, ExamKrackers, or any AAMC paid / official practice material.
- **No confidential AAMC exam content** is reproduced. The public
  ["What's on the MCAT Exam?"](https://students-residents.aamc.org/prepare-mcat-exam/whats-mcat-exam)
  content outline was used **only** for the topic list / content-category structure
  (the category IDs and names already encoded in `taxonomy.json`). No AAMC questions,
  passages, or answer choices were used.
- **Facts, concepts, and mechanisms are not copyrightable**; only a source's specific
  *expression* is. Every stem, option set, and explanation here is independently worded.
- **Deck independence:** these items are authored independently of the study deck
  (Aidan / community decks). The bank and the deck share no items, so studying one cannot
  leak answers to the other.

## 2. Content license

Original ReadyMCAT B/B items (c) ReadyMCAT contributors, released under
**CC BY-SA 4.0**. Each item additionally cites the open source whose concept it is grounded
in. Where a source carries a NonCommercial / ShareAlike obligation (LibreTexts, below),
only *facts/concepts* were used — no protected expression was reproduced — but the source is
credited in full for transparency.

## 3. Sources used (all free / openly licensed)

| Source | Publisher | License | URL | Items |
|---|---|---|---|---:|
| OpenStax **Biology 2e** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/biology-2e | 90 |
| OpenStax **Anatomy and Physiology 2e** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/anatomy-and-physiology-2e | 41 |
| OpenStax **Microbiology** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/microbiology | 11 |
| **LibreTexts** - Fundamentals of Biochemistry (Jakubowski & Flatt) | LibreTexts / UW-Stevens Point | CC BY-NC-SA 4.0 | https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt) | 9 |
| OpenStax **Chemistry 2e** | OpenStax, Rice University | CC BY 4.0 | https://openstax.org/details/books/chemistry-2e | 1 |

Reference-only (no content reproduced; used as concept cross-checks / student review links):

- **Khan Academy MCAT Collection** — https://www.khanacademy.org/test-prep/mcat (CC BY-NC-SA; content available free at khanacademy.org).
- **AAMC content outline** — https://students-residents.aamc.org/prepare-mcat-exam/whats-mcat-exam (public outline used for topic structure only; AAMC-copyrighted, not openly licensed).

**Attribution note (OpenStax):** "Download for free at openstax.org." Content licensed CC BY 4.0.
Each item's `source.name` includes the specific chapter (e.g., "OpenStax Biology 2e ch.7
(Cellular Respiration)") so a reader can locate the grounding concept; the stable book URL is
used because deep-link section slugs are not guaranteed stable.

All five source URLs were checked and returned HTTP 200 at authoring time.

## 4. Coverage summary

### 4.1 Items per AAMC content category

| Category | AAMC content category (name) | Weight* | Items | Subtopics |
|---|---|---:|---:|---:|
| 1A | Structure and function of proteins and their constituent amino acids | 3.53 | 17 | 17 |
| 1B | Transmission of genetic information from the gene to the protein | 3.53 | 18 | 18 |
| 1C | Transmission of heritable information + processes increasing genetic diversity | 3.53 | 16 | 16 |
| 1D | Principles of bioenergetics and fuel molecule metabolism | 3.53 | 18 | 18 |
| 2A | Assemblies of molecules, cells, and groups of cells | 1.71 | 16 | 16 |
| 2B | Structure, growth, physiology, and genetics of prokaryotes and viruses | 1.71 | 14 | 14 |
| 2C | Processes of cell division, differentiation, and specialization | 1.71 | 13 | 13 |
| 3A | Structure and functions of the nervous and endocrine systems | 3.21 | 18 | 18 |
| 3B | Structure and integrative functions of the main organ systems | 3.21 | 22 | 22 |
| **Total** | | | **152** | **152** |

\* Weights are the per-category `topic_weight` values from `taxonomy.json`. Higher-weight
categories (1A-1D, 3A, 3B) received proportionally more items.

### 4.2 Distributions

- **Difficulty:** easy 30, medium 93, hard 29.
- **Cognitive level:** recall 58, application 94 (application-heavy, matching the exam's emphasis on reasoning).
- **Teach-on-miss ladders:** every item has exactly 2 guiding sub-questions (304 total), each an auto-gradable MCQ with its own explanation.

### 4.3 Subtopics covered (by category)

- **1A** - amino acid structure; classification; zwitterions & isoelectric point; side-chain charge vs pH; peptide bond formation; peptide bond properties (resonance/planarity); levels of protein structure (1o-4o); tertiary-structure stabilization (incl. disulfides); quaternary structure; denaturation; enzymes & activation energy; enzyme specificity (induced fit); Michaelis-Menten (Km); competitive inhibition; noncompetitive inhibition; allosteric regulation & feedback inhibition; cofactors & coenzymes.
- **1B** - DNA structure & base pairing; semiconservative replication; replication enzymes & directionality; leading/lagging strands & Okazaki fragments; transcription; mRNA processing (cap/tail/splicing); the genetic code (degeneracy); translation (ribozyme, A/P/E sites); types of RNA; mutations (silent/missense/nonsense/frameshift); lac operon (inducible); trp operon (repressible); eukaryotic regulation (enhancers/TFs); epigenetics (methylation); PCR; gel electrophoresis; restriction enzymes / recombinant DNA; blotting (Southern/Northern/Western).
- **1C** - law of segregation; law of independent assortment; monohybrid (3:1); dihybrid (9:3:3:1); test cross; incomplete dominance; multiple alleles & codominance (ABO); sex-linked inheritance; meiosis; crossing over; nondisjunction & aneuploidy; linkage & recombination frequency; Hardy-Weinberg calculations; Hardy-Weinberg assumptions; natural selection & fitness; genetic drift & speciation.
- **1D** - Gibbs free energy & spontaneity; ATP & energy coupling; redox & electron carriers; glycolysis products; glycolysis location & regulation (PFK-1); fermentation; pyruvate -> acetyl-CoA; citric acid cycle; electron transport chain; chemiosmosis & ATP synthase; aerobic vs anaerobic ATP yield; uncouplers; gluconeogenesis; glycogen metabolism; hormonal regulation (insulin/glucagon); pentose phosphate pathway; fatty acid oxidation; ketone bodies.
- **2A** - cell theory; prokaryotic vs eukaryotic cells; nucleus & nucleolus; mitochondria; endoplasmic reticulum (rough/smooth); Golgi apparatus; lysosomes; ribosomes; plasma membrane (fluid mosaic); membrane fluidity (cholesterol); facilitated diffusion; osmosis & tonicity; active transport (Na+/K+ pump); endocytosis & exocytosis; cytoskeleton; cell junctions & tissues.
- **2B** - bacterial cell wall (Gram stain); bacterial morphology; appendages (flagella/pili/capsule); bacterial growth curve; endospores; oxygen requirements; conjugation; transformation; transduction; plasmids & antibiotic resistance; virus structure; lytic vs lysogenic cycles; retroviruses; prions.
- **2C** - cell cycle phases; mitosis; cytokinesis; checkpoints; cyclins & CDKs; tumor suppressors (p53); cancer & loss of cell cycle control; apoptosis; stem cell potency; cell differentiation; embryogenesis (germ layers); embryonic induction; senescence & telomeres.
- **3A** - neuron structure; glial cells & myelin; resting membrane potential; action potential depolarization; action potential repolarization; all-or-none principle; refractory period; saltatory conduction; synaptic transmission; neurotransmitter removal; CNS vs PNS; autonomic nervous system; reflex arc; nervous vs endocrine signaling; peptide vs steroid hormones; hypothalamic-pituitary axis; negative feedback; specific hormones (ADH).
- **3B** - cardiovascular (blood flow path, cardiac conduction, blood vessels, blood components); respiratory (gas exchange, breathing mechanics, oxygen-hemoglobin/Bohr, CO2 transport); digestive (stomach, small-intestine absorption, accessory organs); renal (nephron & filtration, urine concentration); immune (innate vs adaptive, humoral vs cell-mediated); muscular (sliding filament, muscle types); skeletal (bone remodeling); reproductive (menstrual cycle hormones); endocrine control (calcium/PTH); integumentary system; homeostasis & thermoregulation.

## 5. Item schema

Each element of the `bio_biochem.json` array conforms to:

```json
{
  "id": "bb-<category>-<n>",
  "section": "B/B",
  "aamc_category": "<id matching taxonomy.json, e.g. 1A>",
  "subtopic": "<subtopic label>",
  "stem": "<question>",
  "options": ["<A>", "<B>", "<C>", "<D>"],
  "correct_index": 0,
  "explanation": "<why correct + why each distractor is wrong>",
  "difficulty": "easy|medium|hard",
  "cognitive_level": "recall|application",
  "source": {"name": "...", "url": "...", "license": "..."},
  "subquestions": [
    {"stem": "...", "options": ["..."], "correct_index": 0, "explanation": "..."}
  ]
}
```

The `subquestions` array is the pre-authored **teach-on-miss ladder** (see the PRD's
"TEACH-ON-MISS" section): 2 guiding MCQ steps shown one at a time when a learner misses the
main question, walking them to the answer through active retrieval rather than passive reading.

## 6. Verification

Run the validator from this directory:

```bash
python3 validate_bio_biochem.py
```

It confirms valid JSON, schema conformance for every main item and sub-question, that every
`aamc_category` exists in `taxonomy.json`, that `correct_index` values are in range, that ids
are unique, and it prints the coverage summary above. It exits non-zero on any error.

## 7. Known gaps / future work

- **Passage-based (CARS-style discrete-set) items:** all items are standalone (discrete)
  MCQs for unambiguous auto-grading; experimental/passage-linked question sets are not yet included.
- **Figure/graph-dependent items:** items are text-only (no images), so questions requiring
  reading a specific titration curve, Lineweaver-Burk plot, or pedigree diagram are described
  in words rather than shown; adding rendered figures is future work.
- **Depth vs breadth:** coverage is one high-quality item per subtopic (152 subtopics). Adding
  a second variant per high-yield subtopic (especially 1A-1D, 3A, 3B) would deepen the bank.
- **Ladder length:** every item ships a 2-step ladder; some hard items could benefit from a
  third guiding step (the schema and validator already allow 2-3).
