# ReadyMCAT Introductory Diagnostic — Content & Prior-Mapping Spec

This folder holds the **content and design spec** for ReadyMCAT's first-launch
diagnostic quiz (the question bank, schema, sources, and prior-mapping method).

> **Status update:** the quiz UI, the scoring code, and the prior-seeding engine change
> described here as "follow-on" are now **built and shipping on `main`**: the Rust scorer
> and prior lives in `rslib/src/diagnostic/` (exposed via `proto/anki/diagnostic.proto`
> → `DiagnosticService`), the Svelte quiz UI is `ts/routes/readymcat-diagnostic/`, and it
> auto-opens on first launch (wired in `qt/aqt/main.py`, retake via **Tools → ReadyMCAT
> Diagnostic**). The prior is blended into the points-at-stake order as a decaying weakness
> seed, with a guardrail test proving it never writes the dashboard's memory/performance/readiness
> scores. This folder remains the content + design spec of record; the "follow-on feature build"
> section below is retained as historical design notes.

| File                     | What it is                                                                                                             |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `diagnostic_quiz.json`   | The diagnostic question bank (37 original MCQ items across all 31 AAMC content categories) + a self-describing schema. |
| `validate_diagnostic.py` | Self-contained, dependency-free validator (structure + category coverage).                                             |
| `README.md`              | This document: research findings, sources/licensing, schema, and the prior-mapping spec.                               |

## What this is (and what it is NOT)

The diagnostic is taken **once, on first launch**. Per the
[PRD](../../../ReadyMCAT-PRD.md) ("ALL-IN-ONE QUESTION BANK: EVERY FORMAT, ONE ENGINE"):

> The output is **not a score shown to the student**; it is a **per-topic
> proficiency prior** the engine uses to personalize everything after it. It
> seeds each topic's weakness estimate so the points-at-stake order is useful
> from the very first session ... and it places the student in the prerequisite
> graph.

**The honesty rule (non-negotiable).** A short quiz is a _prior_, not a
readiness verdict. The diagnostic's results feed only two things:

1. the **points-at-stake ordering** seed (`student_weakness` per category), and
2. **prerequisite-graph placement** (which foundations are already held).

They **never** feed the dashboard's memory / performance / readiness scores,
which obey their own give-up rule (>= 200 graded reviews **and** >= 50% topic
coverage). The diagnostic is never surfaced to the student as a number,
percentile, or "you are X% ready."

---

## Part 1 — Research findings

### How existing tools gauge skill / run diagnostics

| Tool                                                    | Diagnostic format                                                                                                        | Length               | How it estimates per-area ability                                                                                                                                                                                    |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Blueprint** (free)                                    | Half-length, full 4-section simulation; scaled 472-528                                                                   | ~4 hours             | Score report breaks results down by science topic, question type, AAMC reasoning skill, and **"demonstrated mastery of the AAMC content categories."** Positioned as a _directional baseline_, not a predictor.      |
| **AAMC Official Prep**                                  | Free Practice Exam One (230 Q, scored) + free Unscored Sample Test (230 Q); free Sample Question Guide (12 Q, 3/section) | Full length (~7.5 h) | Same look/feel/scaled-score as the real exam; gives section scores (118-132) and percentile. The only _free, public, openly-usable_ artifact is the **"What's on the MCAT Exam?" content outline** (the topic list). |
| **Khan Academy MCAT**                                   | ~1,100 videos + ~3,000 review questions across all four sections                                                         | Self-paced           | Practice questions per topic/unit; no single adaptive ability estimate — progress is per-exercise.                                                                                                                   |
| **JackWestin (free CARS)**                              | One daily CARS passage (365 total) + free QBank (~6,700 Q)                                                               | ~1 passage/day       | CARS is a **skills** section (no content categories). Used as an ongoing diagnostic of reasoning patterns via an error log, not a content prior.                                                                     |
| **Third-party QBanks** (UWorld, Kaplan, paid Blueprint) | Large MCQ banks w/ analytics                                                                                             | Many hours           | Per-topic and per-question-type accuracy dashboards. **Paid / copyrighted — not usable as a source (see integrity).**                                                                                                |

**Psychometrics takeaway (why "prior, not score").** The computerized-adaptive-
testing (CAT) / IRT literature is explicit that with only a **handful of items
per domain (1-4)** you cannot get a reliable per-domain ability estimate; short
tests must **regularize toward a Bayesian/empirical prior** and **borrow strength
across correlated domains** (estimate each ability using information from the
others), using estimators like EAP/MAP. This is the formal justification for
treating our 1-2-item-per-category results as a _shrunk prior_ and for the
hierarchical pooling in the spec below.

### Design implication for ReadyMCAT

A full 4-7 hour simulation is the wrong tool for a _first-launch intake_: it is
high-fatigue and produces a _score_ we have promised not to show. ReadyMCAT
instead ships a **~20-40 minute, breadth-first** quiz whose only job is to make
session one's ordering and the prerequisite placement non-random. The depth a
real ability estimate needs comes later, from actual reviews.

---

## Sources & licensing

All diagnostic items are **original**, authored for ReadyMCAT and **grounded in
free / openly-licensed sources**. We cite the grounding source per item for
traceability and so the student can review the concept for free.

| Source                                                                                                                                                             | License                                                                                                                                                  | Use here                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OpenStax** (Biology 2e, Chemistry 2e, College Physics 2e, Organic Chemistry, Anatomy & Physiology 2e, Microbiology, Psychology 2e, Introduction to Sociology 3e) | **CC BY 4.0**                                                                                                                                            | **Primary** concept grounding. CC BY is the most permissive (allows commercial use + derivatives with attribution), so it is the safest base for authored questions. Attribution: "Download for free at openstax.org."                   |
| **Khan Academy MCAT Collection** (created with AAMC + Robert Wood Johnson Foundation)                                                                              | **CC BY-NC-SA**                                                                                                                                          | **Secondary** concept reference and student review link only. _No content reproduced._ Note the NonCommercial + ShareAlike obligations and the required notice: "All Khan Academy content is available for free at www.khanacademy.org." |
| **AAMC "What's on the MCAT Exam?" content outline**                                                                                                                | Free public outline, **AAMC-copyrighted (not openly licensed)**                                                                                          | Used **only** for the canonical topic list (the 31 content-category IDs/names already encoded in `taxonomy.json`). No AAMC questions, passages, answer choices, or confidential content used.                                            |
| **Aidan deck** (`Aidan_.apkg`, in repo) + community decks (MileDown, MrPankow, Abdullah, Coffin via AnKing; JackSparrow)                                           | Free community downloads; educational use (license generally unspecified). AnkiHub auto-update is an optional paid layer; the decks themselves are free. | The **study collection** the prior seeds and the basis for the deck-tag taxonomy. **Not used to author diagnostic items** (see deck-independence).                                                                                       |

### Integrity: traceable source + no leakage

- **No copying from paid/copyrighted QBanks.** Nothing is taken from UWorld,
  Kaplan, paid Blueprint, or AAMC paid/Official Prep. AAMC's terms explicitly
  bar copying or creating derivative works (including AI/LLM modeling) from its
  prep products; we use only the public content outline.
- **Facts vs. expression.** Items are grounded in the _facts/concepts_ of open
  sources (facts are not copyrightable); no source's _expression_ is reproduced.
- **Deck-independence (no leakage into study).** Diagnostic items are authored
  independently of the Aidan/community study deck. The diagnostic and the deck
  share no items, so studying the deck cannot leak diagnostic answers, and the
  diagnostic cannot be "studied" by reviewing the deck.
- **Per-item traceability.** Every item carries `source.ref` (resolving to the
  `sources` registry, with license + URL) plus a `source.location` and a
  one-line `rationale`.

---

## Part 2 — The question bank

### Schema (`diagnostic_quiz.json`)

Top-level keys:

| Key                                                            | Meaning                                                                                                                                                         |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema_version`, `quiz_id`, `title`, `description`, `purpose` | Identity + intent.                                                                                                                                              |
| `taxonomy`                                                     | Pointer to the source of truth (`taxonomy.json` on `readymcat-content-teach-on-miss`) and the category-ID scheme.                                               |
| `administration`                                               | `item_format`, `default_mode`, the `short`/`extended` modes (items-per-category, item count, est. minutes), and the documented `coverage_vs_fatigue` trade-off. |
| `honesty_rule`                                                 | Restates that results are a prior, never a dashboard score.                                                                                                     |
| `authoring_integrity`                                          | The no-leakage / deck-independence policy.                                                                                                                      |
| `content_license`                                              | License of the authored items (CC BY-SA 4.0).                                                                                                                   |
| `sources`                                                      | Registry of every grounding source: `name`, `publisher`, `license`, `url`, `attribution`, `usage`. Items reference these by key.                                |
| `categories_covered`                                           | The 31 AAMC content-category IDs.                                                                                                                               |
| `coverage`                                                     | Totals + the "2 items if weight >= 3.2, else 1" rule.                                                                                                           |
| `items[]`                                                      | The questions (below).                                                                                                                                          |

Each **item**:

```json
{
  "id": "DQ-1A-01",                       // stable unique id: DQ-<category>-<nn>
  "category": "1A",                        // AAMC content-category id (joins to taxonomy.json)
  "category_name": "Structure and function of proteins ...",
  "section": "Bio/Biochem",               // Bio/Biochem | Chem/Phys | Psych/Soc
  "discipline": "Biochemistry",           // academic subject
  "format": "mcq_single_best",            // single-best-answer MCQ
  "cognitive_level": "recall",            // recall | application
  "difficulty": "easy",                   // easy | medium | hard
  "stem": "....?",
  "options": [{"key":"A","text":"..."}, ... 4 total],
  "answer": "A",                           // must equal one option key
  "source": {"ref":"openstax_chemistry_2e","location":"...","url":"..."},
  "rationale": "One line: why the key is correct / what the item probes.",
  "tags": ["amino acids", "pKa"]
}
```

Notes:

- **Format choice.** Items are **discrete (non-passage) single-best-answer
  MCQs**. This is deliberate: discrete MCQs auto-grade unambiguously (ideal for a
  prior) and keep the intake short. Real MCAT items are passage-based; passage
  sets are deferred to the _performance_ model (Friday), not this content prior.
- **Recall vs. application.** Default is application-style; ~10 items are tagged
  `cognitive_level: "recall"` where a crisp factual probe is the cleaner signal.
  `cognitive_level` lets the scorer down-weight pure recall when forming a
  _performance_-flavored prior later, without re-authoring.
- **Difficulty** is an authored label consumed by the difficulty-adjustment step
  of the prior (below). It should be **recalibrated empirically** once real
  response data exists (see follow-on notes).

### Coverage & the coverage-vs-fatigue trade-off

- **31 / 31** AAMC content categories covered. **37** items total.
- **Allocation rule:** 2 items for content categories with AAMC `weight >= 3.2`
  (`1A,1B,1C,1D` at 3.53 and `3A,3B` at 3.21); 1 item for the other 25.
- **Why this allocation:** points-at-stake = `topic_weight x weakness`, so a
  noisy weakness estimate distorts ordering _most_ where weight is high. Spending
  the second item on the highest-weight categories halves the prior's variance
  exactly where it most changes the queue.
- **The trade-off, stated:** first-launch **fatigue** is the binding constraint.
  - `short` mode (**default**): 1 item/category = **31 items**, ~20-30 min —
    full breadth, minimum length. The scorer administers the `-01` item per
    category.
  - `extended` mode: all **37 items**, ~28-40 min — same breadth, modestly
    better resolution on high-yield categories.
  - Even two items per category is far too few for a _reliable_ per-category
    ability estimate — which is precisely why results are consumed as a
    **heavily-shrunk prior**, never a score.
- **CARS is intentionally excluded.** CARS is a skills section with no content
  categories in the AAMC outline (and none in `taxonomy.json`), so it has no
  content prior. CARS skill practice (JackWestin-style) is handled separately and
  is out of scope here.

### Validation

`validate_diagnostic.py` is self-contained (stdlib only) and checks: required
fields; exactly 4 unique option keys; `answer` is a real option key; every
`source.ref` resolves to the registry; valid `difficulty`; **every item category
is a real AAMC category and all 31 are covered**. It also cross-checks its
embedded category set against a `taxonomy.json` when one is found.

```bash
# From the repo root (uses the embedded AAMC category set on this branch):
python3 readymcat/diagnostic/validate_diagnostic.py

# Cross-check against the real taxonomy.json (which lives on another branch):
git show readymcat-content-teach-on-miss:taxonomy.json > /tmp/taxonomy.json
python3 readymcat/diagnostic/validate_diagnostic.py --taxonomy /tmp/taxonomy.json
```

Current status: **OK — all checks pass, 31/31 categories, 37 items**, category
IDs verified identical to `taxonomy.json`.

---

## Part 3 — Prior-mapping spec (design)

This is the **method** for turning quiz results into a per-topic proficiency
prior. The implementation is the follow-on feature build; this section is the
contract it should satisfy.

### Inputs

For each AAMC content category `c`: the number of items administered `n_c`
(1 or 2) and the number correct `k_c`, plus each item's `difficulty` and
`cognitive_level`. Skipped items count as **no evidence** (not as wrong).

### Step 1 — Per-item evidence (difficulty-aware)

Raw per-category accuracy `k_c / n_c` is in `{0, 0.5, 1}` — far too coarse and
noisy to use directly. First convert each _response_ to a difficulty-aware
proficiency signal. Two acceptable implementations:

- **MVP (difficulty-weighted Bernoulli):** map difficulty to a target accuracy
  `t(easy)=0.80, t(medium)=0.55, t(hard)=0.35` (the accuracy a "borderline" test-
  taker would have). A correct hard item is stronger evidence of proficiency than
  a correct easy item; a missed easy item is stronger evidence of a gap. Use the
  residual `(correct - t)` as the signed evidence.
- **Preferred (1PL/Rasch with a prior):** treat difficulty as item difficulty
  `b_i` and estimate category ability `theta_c` by MAP/EAP with a standard-normal
  prior — the short-test, informative-prior approach recommended in the CAT
  literature. Convert `theta_c` to `p_hat_c` via the logistic link.

### Step 2 — Shrink toward a prior (Bayesian, beta-binomial)

Regularize each category's proficiency `p_hat_c` toward a baseline `mu0` with a
**beta-binomial posterior mean**:

```
p_hat_c = (k_c + kappa * mu0) / (n_c + kappa)
```

- `mu0` = expected baseline proficiency (start ~0.5; or the difficulty-implied
  baseline from Step 1; or, better, the section/group mean from Step 3).
- `kappa` = prior strength in pseudo-items (recommend `kappa = 4-8`). With
  `n_c` only 1-2, `p_hat_c` stays close to `mu0`: the quiz **nudges**, it does
  not dominate. This is the math behind "a prior, not a score."

### Step 3 — Borrow strength across correlated categories (hierarchical pooling)

With 1-2 items/category, single-category estimates are unreliable, so partially
pool each category toward its parents using the natural hierarchy
**category -> foundational concept -> section -> global**:

```
mu0(c) = blend(global_mean, section_mean(c), foundational_concept_mean(c))
```

then apply Step 2 with that group-informed `mu0`. Effect: a student who misses
most of Foundational Concept 1 has _every_ FC1 category pulled down, even one
with a lucky correct answer — and one strong category is not over-trusted on a
single item. This is the "empirical prior from a battery of correlated abilities"
result from the CAT research, applied to the AAMC content tree.

### Step 4 — Seed `student_weakness` for points-at-stake

Convert proficiency to the weakness the engine's queue expects:

```
weakness_prior[c] = 1 - p_hat_c          # in [0, 1], higher = weaker
```

This is the **initial** value for `student_weakness[c]` used by the points-at-
stake queue _before_ FSRS has data:

```
points_at_stake(card) = topic_weight[c] * student_weakness[c]
```

(`topic_weight[c]` comes from `taxonomy.json`.) Result: session one already
surfaces high-yield, weak-topic cards instead of a random/forgetting-only order.

### Step 5 — Decay the prior as real reviews arrive (precision-weighted blend)

The prior must **self-erase** as FSRS evidence accumulates so it only ever
affects _early_ ordering:

```
w_prior            = c0                                  # fixed pseudo-count, ~ "5-10 reviews"
w_fsrs(c)          = n_reviews_in_category(c)
weakness_eff[c]    = (w_prior*weakness_prior[c] + w_fsrs(c)*weakness_fsrs[c])
                     / (w_prior + w_fsrs(c))
```

Early on, `w_fsrs ~ 0`, so the prior drives ordering. By the time the dashboard's
give-up rule (>= 200 reviews) is met, `w_fsrs >> w_prior` and the prior's
contribution is negligible. The prior touches **ordering only** and vanishes on
its own — consistent with the honesty rule.

### Step 6 — Prerequisite-graph placement

The prereq graph (a Friday+ engine change) is a DAG over AAMC
categories/concepts with mastery gates. The diagnostic places the student by
**coarse bands**, not scores:

```
band(c) = held    if p_hat_c >= 0.75
          partial if 0.40 <= p_hat_c < 0.75
          gap     if p_hat_c < 0.40
```

- Mark `held` categories as **satisfied prerequisites** so learn-mode does not
  re-teach known foundations.
- Set the **learning frontier** to the first not-`held` concept whose
  prerequisites are all `held`; the quiz-first learn loop starts there.
- Bands are deliberately coarse and **revisable**: because of Step 3's pooling, a
  single lucky/unlucky item cannot by itself unlock or lock a concept, and the
  gate is re-evaluated as real mastery evidence accrues.

### Worked example (FC1)

Student answers Foundational Concept 1: `1A` 1/2, `1B` 0/2, `1C` 2/2, `1D` 0/2.
Using a simple beta-binomial with `mu0 = 0.5`, `kappa = 6` (i.e. `alpha0=beta0=3`):

| Cat | k/n | `p_hat = (k+3)/(n+6)` | `weakness = 1 - p_hat` | band    |
| --- | --- | --------------------- | ---------------------- | ------- |
| 1A  | 1/2 | 4/8 = 0.50            | 0.50                   | partial |
| 1B  | 0/2 | 3/8 = 0.375           | 0.625                  | gap     |
| 1C  | 2/2 | 5/8 = 0.625           | 0.375                  | partial |
| 1D  | 0/2 | 3/8 = 0.375           | 0.625                  | gap     |

All FC1 share `topic_weight = 3.53`, so points-at-stake ranks `1B` and `1D`
first within FC1 — the two the student bombed. Note that even `1B`/`1D` at 0/2
only reach weakness `0.625`, not `1.0`: the prior is **humble** by construction.
(Step 3 pooling would pull all four further toward the FC1 mean of ~0.375 raw,
sharpening the "weak across FC1" signal.)

### Edge cases

- **No deck cards for a category:** the prior still informs prereq placement but
  cannot affect card ordering (there are no cards); surfaced via the coverage map.
- **Blank/skipped item:** no evidence; category falls back to the group prior.
- **CARS:** no content prior (skills section, excluded above).
- **Outlier single items:** mitigated by Step 3 pooling + Step 6 coarse bands +
  re-evaluation as reviews arrive.

---

## For the follow-on feature build

This deliverable is research + content + spec. The feature build (on top of the
**integration branch**) still needs:

1. **Quiz intake UI** — first-launch flow that administers `short` mode (31
   items) by default, renders MCQs, records responses; desktop reviewer
   (`ts/` + `qt/aqt`) and, sharing the engine, iOS.
2. **Scorer** — implement Steps 1-3 (difficulty-aware evidence + beta-binomial +
   hierarchical pooling) to produce `p_hat_c` per category. Pure function, unit-
   tested against fixtures (incl. the worked example above).
3. **Prior-seeding into the engine** — write `weakness_prior[c]` as the initial
   `student_weakness` consumed by the points-at-stake queue builder
   (`rslib/.../scheduler/queue/builder/`), and implement the Step-5 precision-
   weighted decay so the prior fades as FSRS reviews accumulate. Likely a new
   protobuf message to pass diagnostic results into the Rust core.
4. **Prereq-graph placement** — once the prereq DAG (separate Friday+ engine
   change) exists, consume the Step-6 bands to set satisfied prerequisites and
   the learning frontier.
5. **Guardrails** — assert the diagnostic never writes to memory/performance/
   readiness; keep it ordering + placement only. Empirically **recalibrate item
   difficulty** from real response data and refresh the bank.
6. **Integration** — this branch only **adds** files under `readymcat/diagnostic/`.
   Merge after the points-at-stake queue and taxonomy land on the integration
   branch (the scorer/seeder depend on both).

## License & attribution

- Authored diagnostic items: **(c) ReadyMCAT, CC BY-SA 4.0**.
- Concepts grounded in **OpenStax** (CC BY 4.0) and referenced from the
  **Khan Academy MCAT Collection** (CC BY-NC-SA; "All Khan Academy content is
  available for free at www.khanacademy.org").
- AAMC content-category names/IDs are from the public **"What's on the MCAT
  Exam?"** outline; "MCAT" is a registered trademark of the AAMC. ReadyMCAT is
  unaffiliated with and unendorsed by the AAMC or Khan Academy.
