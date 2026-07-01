# ReadyMCAT - P/S Free-Response Item Bank: Sources, Licensing & Coverage

This document accompanies **`free_response_psych_soc.json`**, an original bank of
**free-response (type-in answer)** MCAT practice items for the **Psychological,
Social & Biological Foundations of Behavior (P/S)** section. It complements the
existing multiple-choice banks (the diagnostic quiz and any MC item banks); this
is the **free-response** format, designed for automatic grading with **no AI at
the grading layer**.

| Artifact | Path |
| --- | --- |
| Item bank (deliverable) | `readymcat/content/free_response_psych_soc.json` |
| Human-authored generator | `readymcat/content/free_response_psych_soc_build.py` |
| Stdlib validator | `readymcat/content/free_response_psych_soc_validate.py` |
| This document | `readymcat/content/free_response_psych_soc_SOURCES.md` |

The committed **JSON is the source of truth**. It is (re)generated from the
builder and independently checked by the validator (both stdlib-only, no
third-party dependencies).

---

## 1. Authoring integrity & legal

- **All items are ORIGINAL**, authored for ReadyMCAT and grounded in
  **free / openly-licensed** sources cited per item.
- **No copying / scraping / close paraphrasing** from any copyrighted or paid
  question bank (UWorld, Kaplan, Blueprint, AAMC paid/official prep). No AAMC
  questions, passages, or confidential exam content are reproduced.
- The **public AAMC "What's on the MCAT Exam?" content outline** is used **only**
  for the content-category IDs/labels (6A-10A) already encoded in
  `taxonomy.json`, and only for structure/terminology - never for item content.
- Facts and concepts are **not copyrightable**; no source's *expression* is
  reproduced. Theorist/term attributions were checked for correctness (e.g.,
  Weber's law, Young-Helmholtz vs. opponent-process, James-Lange vs.
  Cannon-Bard vs. Schachter-Singer, Piaget/Erikson/Kohlberg/Vygotsky,
  Cooley vs. Mead, Durkheim/Marx/Weber, Bourdieu, Wallerstein).
- **Deck independence:** items are authored independently of the study deck
  (Aidan/community decks), so studying one cannot leak answers to the other.

### Bank license

Original items (c) ReadyMCAT contributors, released under **CC BY-SA 4.0**. Each
item cites the open source whose *concept* it is grounded in.

---

## 2. Sources & licensing

| Source | Publisher | License | Used for |
| --- | --- | --- | --- |
| **OpenStax Psychology 2e** | OpenStax, Rice University | **CC BY 4.0** | Psychology items (sensation/perception, cognition, memory, consciousness, emotion, motivation, learning, personality, development, disorders, social psychology, stress) |
| **OpenStax Introduction to Sociology 3e** | OpenStax, Rice University | **CC BY 4.0** | Sociology items (culture, socialization, social interaction, groups/organizations, theory, institutions, demography, stratification, inequality, health) |
| **OpenStax Biology 2e** | OpenStax, Rice University | **CC BY 4.0** | Behavioral-biology items (neuron/action potential, synaptic transmission, endocrine influence on behavior) |
| **Khan Academy MCAT Collection** | Khan Academy (with AAMC & RWJF) | **CC BY-NC-SA** | Secondary concept reference (nervous-system organization); concept-only, no content reproduced |
| **AAMC "What's on the MCAT Exam?" outline** | AAMC | Free public outline; **AAMC-copyrighted, NOT openly licensed** | Content-category IDs/labels only (already in `taxonomy.json`); structure/terminology only |

Attribution for OpenStax: *"Download for free at openstax.org. Licensed under CC BY 4.0."*

URLs:
- Psychology 2e - https://openstax.org/details/books/psychology-2e
- Introduction to Sociology 3e - https://openstax.org/details/books/introduction-sociology-3e
- Biology 2e - https://openstax.org/details/books/biology-2e
- Khan Academy MCAT - https://www.khanacademy.org/test-prep/mcat
- AAMC outline - https://students-residents.aamc.org/prepare-mcat-exam/whats-mcat-exam

Every item carries a `source` object with `name` (book + chapter), `url`, and `license`.

### Source distribution (per item)

| Source | Items |
| --- | ---: |
| OpenStax Psychology 2e | 95 |
| OpenStax Introduction to Sociology 3e | 45 |
| OpenStax Biology 2e | 3 |
| Khan Academy MCAT | 1 |
| **Total** | **144** |

---

## 3. Auto-grading contract (no AI)

Each item has a **short, closed answer** (a term, name, or short phrase) - never
an open-ended essay - so it can be graded by normalized string / key-term
matching. The intended grader logic:

> Normalize the typed answer (lowercase; trim; collapse internal whitespace;
> strip surrounding punctuation; drop a single leading article `a`/`an`/`the`).
> Mark **correct** if it equals any entry in **`accepted_answers`** (each
> normalized the same way), **or** if it contains every string in
> **`key_terms`** as a normalized substring.

- **`accepted_answers`** enumerate the primary short answer plus common synonyms,
  abbreviations, and spelling variants (e.g., `["difference threshold", "just
  noticeable difference", "jnd"]`; `["fundamental attribution error", "fae",
  "correspondence bias"]`). Average **2.6** accepted answers per item.
- **`key_terms`** are the must-appear token(s) - a lenient fallback path.
- **`model_answer`** is the ideal concise answer; **`explanation`** gives the why
  plus brief elaboration.

The **same contract applies to each teach-on-miss sub-question's**
`accepted_answers`.

---

## 4. Schema

Each element of the JSON array conforms exactly to:

```json
{
  "id": "fr-ps-<category>-<n>",
  "section": "P/S",
  "aamc_category": "<id>",
  "subtopic": "<label>",
  "answer_type": "free_response",
  "prompt": "<question requiring a short typed answer>",
  "accepted_answers": ["<primary>", "<variant/synonym>", "..."],
  "key_terms": ["<must-appear term>", "..."],
  "model_answer": "<ideal concise answer>",
  "explanation": "<why + brief elaboration>",
  "difficulty": "easy|medium|hard",
  "cognitive_level": "recall|application",
  "source": { "name": "...", "url": "...", "license": "..." },
  "subquestions": [
    { "stem": "<guiding step>", "answer_type": "free_response",
      "accepted_answers": ["..."], "explanation": "<...>" }
  ]
}
```

### Teach-on-miss ladder

**Every item includes a 2-3 step `subquestions` teach-on-miss ladder** (guiding
short-answer steps that walk the student to the answer through their own
retrieval, per the PRD's TEACH-ON-MISS / LEARN MODE sections). This bank ships
**2 rungs per item = 288 ladder steps** across 144 items. Each rung is itself an
auto-gradable free-response step.

---

## 5. Coverage

Comprehensive coverage of P/S: **Foundational Concepts 6, 7, 8, 9, 10**, all
**12** content categories (6A-6C, 7A-7C, 8A-8C, 9A-9B, 10A), confirmed against
`taxonomy.json` (`aamc_categories`). Weights are `topic_weight` (percent-of-exam)
from `taxonomy.json`.

| Category | Name | AAMC weight | Items |
| --- | --- | ---: | ---: |
| 6A | Sensing the environment | 2.14 | 14 |
| 6B | Making sense of the environment | 2.14 | 17 |
| 6C | Responding to the world | 2.14 | 11 |
| 7A | Individual influences on behavior | 2.99 | 21 |
| 7B | Social processes that influence human behavior | 2.99 | 12 |
| 7C | Attitude and behavior change | 2.99 | 8 |
| 8A | Self-identity | 1.71 | 11 |
| 8B | Social thinking | 1.71 | 10 |
| 8C | Social interactions | 1.71 | 11 |
| 9A | Understanding social structure | 1.92 | 11 |
| 9B | Demographic characteristics and processes | 1.92 | 9 |
| 10A | Social inequality | 1.28 | 9 |
| **Total** | | | **144** |

By Foundational Concept: **FC6 = 42, FC7 = 41, FC8 = 32, FC9 = 20, FC10 = 9.**
Higher-weight concepts (FC7 at 2.99, FC6 at 2.14) carry more items.

### Subtopics covered (representative)

- **6A** absolute/difference thresholds, Weber's law, signal detection,
  sensory adaptation, transduction, bottom-up/top-down, rods/cones/fovea,
  trichromatic & opponent-process theories, place theory, gate control theory,
  taste (umami), vestibular sense.
- **6B** selective/divided attention, Piaget, heuristics (availability/
  representativeness), functional fixedness, intelligence (g, Gardner,
  Sternberg, fluid/crystallized), sleep stages/REM, dream theories, drug reward
  pathway, Atkinson-Shiffrin, memory types, serial position, interference, LTP,
  Broca/Wernicke, linguistic relativity.
- **6C** components & theories of emotion (James-Lange, Cannon-Bard,
  Schachter-Singer, appraisal), Ekman/universality, amygdala, Yerkes-Dodson,
  general adaptation syndrome, HPA/cortisol, coping.
- **7A** classical & operant conditioning, reinforcement schedules, shaping,
  observational learning, neurotransmitters, autonomic NS, heritability, Freud,
  defense mechanisms, Rogers, Big Five, locus of control, drive-reduction/
  Maslow, schizophrenia, diathesis-stress, and behavioral biology (action
  potential, synaptic transmission, hormones, CNS/PNS).
- **7B** social facilitation/loafing, bystander effect, deindividuation,
  groupthink, Asch, Milgram, compliance techniques, norms (mores/folkways/
  taboos), agents of socialization, culture (assimilation/subculture),
  sanctions.
- **7C** cognitive dissonance, ELM, habituation/sensitization, social cognitive
  theory, ABC attitudes, mere exposure, observational-learning processes,
  self-perception theory.
- **8A** Erikson, Freud psychosexual, Kohlberg, looking-glass self (Cooley),
  Mead (I/me, generalized other, stages), social identity theory, self-esteem/
  self-efficacy, Vygotsky/ZPD, self-schema, gender identity.
- **8B** fundamental attribution error, self-serving & actor-observer bias,
  just-world hypothesis, stereotype/prejudice/discrimination, stereotype threat,
  self-fulfilling prophecy, ethnocentrism/cultural relativism, halo effect,
  institutional vs. individual discrimination, out-group homogeneity.
- **8C** status (ascribed/achieved/master), roles (conflict/strain/exit),
  dramaturgy (Goffman), attachment (Ainsworth), attraction, altruism (kin/
  reciprocal), primary/secondary groups, bureaucracy (Weber), nonverbal
  communication, aggression, social support.
- **9A** functionalism/conflict/symbolic interactionism/constructionism/
  exchange/feminist theory, micro vs. macro, material/nonmaterial culture,
  sick role & medicalization, hidden curriculum, secularization, Durkheim/
  anomie.
- **9B** demographic transition, Malthus, fertility/birth rate/replacement,
  migration push-pull, social movements (relative deprivation / resource
  mobilization), globalization, urbanization/gentrification, population
  pyramids/aging, race/ethnicity/minority group.
- **10A** caste vs. class, social mobility, cultural/social capital (Bourdieu),
  absolute/relative poverty, SES (Weber's class/status/power), social
  reproduction/meritocracy, health disparities & social determinants,
  residential segregation/environmental justice, world-systems (core/periphery).

### Item distribution

- **Difficulty:** easy 25, medium 92, hard 27.
- **Cognitive level:** recall 87, application 57.

---

## 6. Reproduce & validate

```bash
cd readymcat/content

# (Re)generate the JSON from the human-authored builder:
python3 free_response_psych_soc_build.py            # writes free_response_psych_soc.json
python3 free_response_psych_soc_build.py --stdout   # or print to stdout

# Validate (JSON validity; schema; category IDs vs. taxonomy.json;
# accepted_answers present; 2-3 step ladder present):
python3 free_response_psych_soc_validate.py
```

The validator locates the repo-root `taxonomy.json` automatically (walking up
from this folder) and cross-checks every category ID against it; pass
`--taxonomy PATH` to override, and `--bank PATH` to validate a different file. It
exits `0` on success and `1` on any failure.

---

## 7. Gaps & notes

- **Grader not included:** this workstream ships the *content* and its
  auto-grading *contract* (accepted_answers + key_terms). The normalization/
  matching routine described in section 3 is the intended reviewer-layer
  implementation and is not part of this content deliverable.
- **Ladders are 2 rungs each** (within the PRD's 2-3 range). Some hard items
  could support a 3rd rung; this is a natural future enhancement.
- **CARS** has no content categories and is out of scope, as are the science
  sections (Bio/Biochem, Chem/Phys); this bank is P/S-only.
- **Overlapping subtopics** (e.g., observational learning appears under both 7A
  and 7C; self-efficacy under 7A/7C/8A) are intentionally represented from the
  angle each AAMC category emphasizes, without duplicate prompts (0 duplicate
  prompts, 0 duplicate IDs).
- Source grounding leans on OpenStax Psychology 2e and Sociology 3e (the
  cleanest CC BY 4.0 fit for P/S); Biology 2e and Khan Academy are used for the
  biological-bases-of-behavior subtopic.
