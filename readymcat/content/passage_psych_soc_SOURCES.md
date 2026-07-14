# ReadyMCAT P/S passage question bank — sources, licensing & coverage

Original, passage-based, exam-simulating multiple-choice question sets for the
**Psychological, Social & Biological Foundations of Behavior (P/S)** section of
the MCAT, built for ReadyMCAT (an MCAT study app forked from Anki).

| File                            | What it is                                                                                            |
| ------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `passage_psych_soc.json`        | The question bank: a JSON array of passage objects (the app-consumed artifact).                       |
| `passage_psych_soc_build.py`    | Single source of truth. Holds the authored content as Python data and emits the JSON via `json.dump`. |
| `passage_psych_soc_validate.py` | Self-contained, dependency-free validator (schema + coverage).                                        |
| `passage_psych_soc_SOURCES.md`  | This document.                                                                                        |

> The JSON is **generated** — edit `passage_psych_soc_build.py` and re-run it,
> then re-run the validator. This mirrors the repo's existing
> `tools/build_taxonomy.py -> taxonomy.json` pattern.

---

## Sourcing & legal integrity (read first)

- **All passages and questions are ORIGINAL**, authored for ReadyMCAT. Every P/S
  passage describes an **invented** research study (methods/results/data in
  words), in the style of the real exam, which is heavily study- and data-based.
- **No copyrighted / paid material was copied, scraped, or paraphrased.** Nothing
  is taken from UWorld, Kaplan, Blueprint, or **any AAMC paid/practice/official
  content**. AAMC's terms bar copying or making derivative works (including
  AI/LLM modeling) from its prep products.
- The **public AAMC _"What's on the MCAT Exam?"_ content outline** is used **only
  as a format/coverage blueprint** — i.e., the list of content-category IDs
  (6A–10A) already encoded in `taxonomy.json`. No AAMC questions, passages,
  answer choices, or confidential content are used.
- Content is **grounded in free / openly-licensed sources** (below). Facts and
  concepts are not copyrightable; **no source's expression is reproduced**. We
  cite the grounding source per passage (`passage_source`) for traceability and
  so a student can review the concept for free.
- **Attribution accuracy.** Theorist/term attributions in the answer
  explanations were checked (see "Attribution check" below).

---

## Grounding sources

| Source                                              | Publisher                 | License                                                        | Use here                                                                                                                                               |
| --------------------------------------------------- | ------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **OpenStax Psychology 2e**                          | OpenStax, Rice University | **CC BY 4.0**                                                  | Primary grounding for FC 6–8 psychology passages (sensation, memory, emotion/stress, motivation, personality, social psychology, self/attribution).    |
| **OpenStax Introduction to Sociology 3e**           | OpenStax, Rice University | **CC BY 4.0**                                                  | Primary grounding for FC 8–10 passages (impression management, sociological paradigms, institutions/medicine, stratification, demography, inequality). |
| **AAMC "What's on the MCAT Exam?"** content outline | AAMC                      | Free public outline; **AAMC-copyrighted, not openly licensed** | Coverage/format blueprint **only** — the 12 P/S content-category IDs already in `taxonomy.json`. No AAMC content reproduced.                           |

`passage_source` on each passage records `{name, url, license}` pointing at the
OpenStax book (with chapter) the concept is grounded in. OpenStax attribution:
"Download for free at openstax.org," licensed CC BY 4.0.

**Khan Academy** (CC BY-NC-SA) was **not** used or reproduced here; it is only a
student review link elsewhere in ReadyMCAT.

### Licensing of this deliverable

- **Authored content** (passages, questions, explanations, sub-question ladders):
  © ReadyMCAT, released under **CC BY-SA 4.0** (compatible with grounding in
  CC BY 4.0 OpenStax material).
- **Code** (`passage_psych_soc_build.py`, `passage_psych_soc_validate.py`):
  **GNU AGPL v3 or later**, matching the ReadyMCAT/Anki fork.
- "MCAT" is a registered trademark of the AAMC. ReadyMCAT is unaffiliated with
  and unendorsed by the AAMC or OpenStax.

---

## Format (schema)

The exam is simulated: each narrative passage is ~200–350 words describing a
study's methods/results/data, followed by 4–6 questions that mix
passage/data-interpretation with content application; two **discrete**
(standalone, non-passage) sets mirror the discrete questions interspersed on the
real P/S section. Each element of the JSON array is:

```json
{
    "id": "psg-ps-<n>",
    "section": "P/S",
    "passage": "<original ~200-350 word study description>",
    "passage_source": {
        "name": "OpenStax Psychology 2e (Ch. ...)",
        "url": "https://...",
        "license": "CC BY 4.0"
    },
    "questions": [
        {
            "id": "psg-ps-<n>-q<k>",
            "aamc_category": "<6A..10A from taxonomy.json>",
            "subtopic": "<label>",
            "stem": "<question>",
            "options": ["A", "B", "C", "D"],
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

**Teach-on-miss ladders.** Per the [PRD](../../../ReadyMCAT-PRD.md) TEACH-ON-MISS
and LEARN MODE sections, every question carries a **2–3 rung `subquestions`
ladder**: pre-authored guiding MCQ steps that walk a student who misses the main
question to the answer through their own retrieval (active retrieval, not passive
reading), before the full answer is revealed. Discrete (non-passage) sets are
flagged by a `passage` field beginning with "Discrete questions"; the validator
exempts them from the narrative word-count/question-count rules.

---

## Coverage & counts

- **Passages: 12** (10 narrative studies + 2 discrete standalone sets).
- **Questions: 59** (a full-length P/S section is 59 questions).
- **Sub-questions (teach-on-miss rungs): 129.**
- **AAMC P/S content categories covered: 12 / 12** (Foundational Concepts 6–10).

| FC | Category | Name (per `taxonomy.json`)                     | Questions |
| -- | -------- | ---------------------------------------------- | --------: |
| 6  | 6A       | Sensing the environment                        |         4 |
| 6  | 6B       | Making sense of the environment                |         8 |
| 6  | 6C       | Responding to the world                        |         5 |
| 7  | 7A       | Individual influences on behavior              |         5 |
| 7  | 7B       | Social processes that influence human behavior |         5 |
| 7  | 7C       | Attitude and behavior change                   |         5 |
| 8  | 8A       | Self-identity                                  |         3 |
| 8  | 8B       | Social thinking                                |         5 |
| 8  | 8C       | Social interactions                            |         4 |
| 9  | 9A       | Understanding social structure                 |         6 |
| 9  | 9B       | Demographic characteristics and processes      |         3 |
| 10 | 10A      | Social inequality                              |         6 |

**Difficulty mix:** easy = 14, medium = 41, hard = 4.
**Cognitive mix:** comprehension = 17, application = 28, data-analysis = 14.

(`difficulty` and `cognitive_level` are authored labels; per the PRD they should
be **recalibrated empirically** once real response data exists.)

### Passage map (topic → categories)

| id        | Topic (original study)                                                       | Categories                  |
| --------- | ---------------------------------------------------------------------------- | --------------------------- |
| psg-ps-1  | Detecting faint tones: thresholds, signal detection, Weber's law, adaptation | 6A, 6B                      |
| psg-ps-2  | Depth of processing, serial position, misinformation effect                  | 6B                          |
| psg-ps-3  | Arousal + appraisal and the labeling of emotion; cortisol/stress             | 6C                          |
| psg-ps-4  | Rewards & persistence: overjustification, intrinsic/extrinsic, traits        | 7A                          |
| psg-ps-5  | Group behavior: conformity, social facilitation, bystander effect            | 7B, 8C                      |
| psg-ps-6  | Two routes to persuasion (ELM) + cognitive dissonance                        | 7C                          |
| psg-ps-7  | Self-efficacy & locus of control; attribution biases                         | 8A, 8B                      |
| psg-ps-8  | Stereotype threat & impression management (dramaturgy)                       | 8B, 8C, 10A                 |
| psg-ps-9  | Sociological paradigms & the institution of medicine                         | 9A, 9B                      |
| psg-ps-10 | Socioeconomic gradient in health; segregation, mobility, demography          | 10A, 9B, 9A                 |
| psg-ps-11 | **Discrete set A** (FC 6–7)                                                  | 6A, 6B, 6C, 7A              |
| psg-ps-12 | **Discrete set B** (FC 7–10)                                                 | 7B, 7C, 8B, 8C, 9A, 9B, 10A |

---

## Build & validate

```bash
# Regenerate the JSON from the source-of-truth builder:
python3 readymcat/content/passage_psych_soc_build.py

# Validate structure + coverage (exits non-zero on any failure):
python3 readymcat/content/passage_psych_soc_validate.py

# Cross-check categories against a specific taxonomy.json:
python3 readymcat/content/passage_psych_soc_validate.py --taxonomy /path/to/taxonomy.json
```

The validator checks: top-level array shape; per-passage required fields, id
pattern/uniqueness, `section == "P/S"`, `passage_source` completeness, and
(narrative only) 200–350 words with 4–6 questions; per-question required fields,
`psg-ps-<n>-q<k>` id, exactly 4 unique options, valid `correct_index`,
substantive explanation, allowed `difficulty`/`cognitive_level`, and a 2–3 rung
`subquestions` ladder; per-sub-question stem/options/index/explanation; and that
all 12 P/S categories are covered. It also cross-checks used categories against
`taxonomy.json` when one is found.

---

## Attribution check (theorist / term traceability)

Concepts and their correct attributions used in explanations:

- **Weber's law** (Ernst Weber); **signal detection** — sensitivity `d'` vs.
  response criterion; **sensory adaptation**; **top-down processing**.
- **Levels of processing** (Craik & Lockhart); **serial position** — primacy
  (long-term store) vs. recency (short-term store); **misinformation effect /
  reconstructive memory** (Elizabeth Loftus).
- **Two-factor theory** (Schachter & Singer) vs. **James-Lange** vs.
  **Cannon-Bard**; **cognitive appraisal of stress** (Lazarus); **general
  adaptation syndrome** (Hans Selye); **HPA axis / cortisol**.
- **Overjustification effect**; **intrinsic vs. extrinsic / self-determination**
  (Deci & Ryan); **Big Five (OCEAN)** trait approach.
- **Conformity / normative vs. informational influence** (Asch); **social
  facilitation** (Zajonc); **bystander effect / diffusion of responsibility**
  (Latané & Darley); power of the situation.
- **Elaboration likelihood model** — central vs. peripheral route (Petty &
  Cacioppo); **cognitive dissonance / insufficient justification** (Festinger &
  Carlsmith).
- **Self-efficacy** (Bandura); **locus of control** (Rotter); **fundamental
  attribution error**; **actor-observer bias**; **generalized other** and the
  "I"/"me" (George Herbert Mead).
- **Stereotype threat** (Steele & Aronson); **impression management** &
  **dramaturgy / front- and back-stage** (Erving Goffman); stereotype
  (cognitive) vs. prejudice (affective) vs. discrimination (behavioral).
- **Structural functionalism** & the **sick role** (Talcott Parsons); **conflict
  theory** (Marx); **symbolic interactionism** (Mead/Blumer/Goffman);
  **medicalization**; macro vs. micro levels; **anomie** (Durkheim) vs.
  **alienation** (Marx); **structure vs. agency**.
- **Socioeconomic gradient in health**; multidimensional **SES** (Weber);
  **spatial inequality / environmental injustice**; **social mobility** and
  **social reproduction**; **meritocracy**; **demographic transition** and the
  **dependency ratio**; population aging.
- Discrete items: retinal **transduction** (rods/cones); Piagetian
  **conservation**; **representativeness vs. availability** heuristics (Tversky &
  Kahneman); **REM vs. NREM** sleep; operant **reinforcement schedules**
  (Skinner); **obedience** (Milgram); **foot-in-the-door vs. door-in-the-face**;
  **self-serving bias**; **attachment / Strange Situation** (Ainsworth).

---

## Gaps & limitations / future work

- **Discipline scope.** Passages are the described-study format the P/S section
  favors; a few purely biological P/S sub-topics (e.g., detailed neuroanatomy of
  emotion, biological bases of behavior) are touched only lightly and could get
  dedicated passages.
- **Category balance.** 8A, 9B are at the coverage floor (3 questions each,
  matching their lower AAMC weight); high-yield 6B is deepest (8). Balance is
  intentional but can be re-tuned.
- **Difficulty distribution** skews medium; more `hard` data-interpretation items
  would improve exam fidelity, and all difficulty labels should be recalibrated
  from real response data.
- **No figures.** Real P/S passages sometimes include a table/graph; here all
  data are described in words (rendering-agnostic and copyright-safe).
- **Not yet wired into the reviewer.** This is the content artifact; consuming it
  in the desktop/iOS reviewers (and logging teach-on-miss outcomes) is follow-on
  feature work, consistent with the PRD.
