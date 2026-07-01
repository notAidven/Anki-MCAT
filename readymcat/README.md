# ReadyMCAT — content + teach-on-miss workstream

This folder documents the **study-content + teach-on-miss** workstream of ReadyMCAT
(an MCAT study app forked from Anki). It produces two committed content artifacts and
one desktop reviewer feature:

| Artifact                     | Path                                                                        | Consumed by                                                |
| ---------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------- |
| AAMC taxonomy + deck mapping | [`/taxonomy.json`](../taxonomy.json)                                        | engine (points-at-stake queue, coverage, per-topic memory) |
| Teach-on-miss ladders        | [`/subquestions.json`](../subquestions.json)                                | desktop reviewer                                           |
| Teach-on-miss reviewer flow  | `ts/reviewer/teach_on_miss.ts`, `qt/aqt/reviewer.py`, `qt/aqt/readymcat.py` | desktop app                                                |

Base deck: the community **"Aidan" deck** (`Aidan_.apkg`, 8,891 notes / 15,175 cards,
84 subdecks across all four MCAT sections), credited to its author and used for
educational purposes.

---

## 0. Pre-loaded MCQ deck + per-question teach-on-miss (v2)

The v2 rework ships ReadyMCAT as a **pre-loaded multiple-choice deck**: a brand-new
user gets the full MCAT MCQ bank with **zero import**.

| Artifact                         | Path                                                              | Consumed by                     |
| -------------------------------- | ----------------------------------------------------------------- | ------------------------------- |
| Canonical MCQ bank               | [`content/question_bank.json`](content/question_bank.json)        | the collection builder          |
| Section banks (merged)           | `content/{bio_biochem,chem_phys,psych_soc}.json`                  | `tools/build_question_bank.py`  |
| Collection builder / provisioner | [`tools/build_question_bank.py`](tools/build_question_bank.py)    | `qt/aqt/readymcat_provision.py` |
| MCQ reviewer + ladder UI         | `ts/reviewer/mcq.ts`, `qt/aqt/reviewer.py`, `qt/aqt/readymcat.py` | desktop app                     |

**Bank.** 414 MCQs / 948 sub-questions across all 31 AAMC categories; each item is
`{id, section, aamc_category, subtopic, stem, options[4], correct_index, explanation,
difficulty, cognitive_level, source, subquestions[]}`. `build_question_bank.py`
validates + merges the three section banks into `question_bank.json`.

**Note type + pre-loading (zero import).** The builder creates a `ReadyMCAT MCQ` note
type (fields: Question, OptionA–D, CorrectIndex, Explanation, Subtopic, Source,
Subquestions[JSON]) with **one card per MCQ**, in a single `ReadyMCAT` deck, and tags
every note `#ReadyMCAT::AAMC::<category>`. On first launch
`qt/aqt/readymcat_provision.py` builds the deck straight into the new user's
collection (no `.apkg` import) and drops `taxonomy.json`, `subquestions.json` and
`diagnostic_quiz.json` next to it. `taxonomy.json` maps `#ReadyMCAT::AAMC::<cat>` →
`<cat>`, so the pre-loaded deck feeds points-at-stake, the coverage map and the
honest-memory dashboard unchanged (see §1 / §5).

**MCQ reviewer + FSRS grading.** The reviewer renders each card as an interactive
four-option MCQ; on submit it grades into FSRS:

| Result                                                 | FSRS grade                               |
| ------------------------------------------------------ | ---------------------------------------- |
| Correct on the **first** attempt                       | **Good** (ease 3)                        |
| Needed the ladder (correct only after, or still wrong) | **Again** (ease 1) — relearning / spaced |

Immediate success right after the scaffold is never treated as mastery (PRD), so a
missed card always relearns; a card missed **again** after the ladder is additionally
tagged `ReadyMCAT::struggling` for the points-at-stake boost (§5).

**Per-question teach-on-miss.** This generalizes the curated-subset ladder (§2–3) to
**every** card: on a wrong answer the reviewer runs the guiding sub-questions stored in
that card's own `Subquestions` field — one sub-MCQ at a time (attempt → reveal) →
re-show the main question → correct = spaced re-retrieval, wrong again = reveal the
earned explanation + surface the source link. The curated `subquestions.json` ladders
still apply to non-MCQ (Aidan-deck) cards.

---

## 1. `taxonomy.json` — deck → AAMC outline

Maps the deck's subdecks/tags onto the **31 AAMC content categories** and assigns each a
`topic_weight` (percent-of-exam). Schema (exactly as the engine expects):

```json
{
    "version": 1,
    "aamc_categories": { "1A": { "name": "...", "weight": 3.53 }, "...": {} },
    "mappings": [
        { "deck_tag_or_subdeck": "<glob or prefix>", "category": "1A" }
    ]
}
```

### Weight methodology (traceable)

AAMC's _"What's on the MCAT Exam?"_ publishes, per **section**, the approximate percentage
of questions for each **foundational concept** (FC); it does **not** publish per-content-
category (1A/1B) sub-weights. We therefore derive each category's percent-of-exam as:

```
weight(cat) = (section_questions / 230)        # section share of the exam
            * (fc_percent_within_section / 100) # AAMC published
            / categories_in_fc                  # even split within the FC (documented assumption)
            * 100
```

- Scored questions per section (AAMC): Chem/Phys 59, CARS 53, Bio/Biochem 59, Psych/Soc 59 → **230**.
- FC percentages used (AAMC): Bio/Biochem FC1 55 / FC2 20 / FC3 25; Chem/Phys FC4 40 / FC5 60;
  Psych/Soc FC6 25 / FC7 35 / FC8 20 / FC9 15 / FC10 5.
- The only non-AAMC assumption is the **even split within each FC**.
- CARS (≈23% of the exam) is a skills section with no content categories, so the 31 weights
  sum to ≈76.96 (the science/behavioral share of the exam). Points-at-stake uses _relative_
  weights, so the absolute scale does not affect ordering.

The derivation is reproducible — see [`tools/build_taxonomy.py`](tools/build_taxonomy.py).

### Resolution order (the engine should mirror this)

A mapping value starting with `#` is a **tag** prefix; otherwise it is a **subdeck** prefix.
Matching is **path-prefix on `::` boundaries** (`P` matches `V` iff `V == P` or `V` starts
with `P::`). To resolve a card → category:

1. Among **tag** mappings whose value prefixes any of the card's tags, take the **longest**.
2. Otherwise, among **subdeck** mappings whose value prefixes the card's deck, take the **longest**.
3. Otherwise the card is **uncategorized**.

Tag mappings deliberately win over subdeck mappings, because the deck's tag tree is finer than
its subdeck layout (e.g. prokaryotes/viruses, social-thinking, and inequality live as tags
inside broader subdecks). The identical algorithm is implemented in both
`tools/build_taxonomy.py` (`resolve_category`) and the reviewer's concept matcher.

### Coverage report

Generated by `python readymcat/tools/build_taxonomy.py --collection <collection.anki21>`:

- Cards examined: **15,175**; categorized: **14,982 (98.7%)**; uncategorized: **193 (1.3%)**.
  The uncategorized cards are the `MCAT::Experimental` deck (research methods / statistics =
  AAMC _Scientific Inquiry & Reasoning Skills_, not a content category) plus 3 stray umbrella
  cards — intentionally left unmapped.
- **AAMC content categories covered: 31 / 31 (100%).** Every category resolves to ≥1 card
  (thinnest: 10A social inequality = 29, 7C attitude change = 33, 8B social thinking = 116).
- **Exam-weight covered: 76.96% of the exam** (= 100% of the content-category weight; the
  remaining 23.04% is CARS, which has no content categories and is not flashcard material).
- Comfortably clears the PRD give-up rule's ≥50% topic-coverage threshold.

---

## 2. `subquestions.json` — teach-on-miss ladders

24 curated high-value concepts drawn from the highest-weight categories (1A–1D, 3A/3B,
4B–4E, 5A/5D/5E, 6B/6C, 7A/7B), each with a 2–3 rung guiding ladder (72 rungs total). Every
concept's `match_tags` were validated against the deck — each matches real cards (5–136
notes), so teach-on-miss is demonstrable across hundreds of cards.

```json
{
    "version": 1,
    "concepts": [
        {
            "id": "biochem_glycolysis_net_yield",
            "title": "Glycolysis: net ATP / NADH yield",
            "category": "1D",
            "match_tags": [
                "#Biochemistry::Metabolism::Carbohydrates::Glycolysis"
            ],
            "resource": {
                "label": "Khan Academy - Biomolecules (Glycolysis)",
                "url": "https://..."
            },
            "ladder": [{ "q": "guiding sub-question", "a": "sub-answer" }]
        }
    ]
}
```

A card is matched to a concept using the **same path-prefix / longest-match** rule as the
taxonomy (over `match_tags`). `resource` is the "needs content review" nudge surfaced when the
main question is missed again (the reviewer prefers the card's own embedded link when present,
else this curated Khan Academy link).

---

## 3. Teach-on-miss (desktop reviewer)

Implements the PRD's core feature. When a card belonging to a curated concept is graded
**Again**, the reviewer does **not** just flip to the back — it runs the guiding ladder, then
re-shows the main question. Files:

- `qt/aqt/readymcat.py` — loads/caches `subquestions.json`, resolves a card → concept,
  extracts a resource link, and appends instrumentation events to a JSONL log.
- `qt/aqt/reviewer.py` — `_answerCard` intercepts an `Again` (ease 1) on a matched card and
  starts the ladder (`_maybe_start_teach_on_miss`); `tom:*` bridge commands are handled in
  `_linkHandler`; `_finish_teach_on_miss` reschedules the card as Again (relearning) and
  advances. `_answerCard` was split into interception + `_do_answer_card` (scheduler body).
- `ts/reviewer/teach_on_miss.ts` — the in-card UI (exposed globally as `_teachOnMissStart`
  via `index.ts`/`index_wrapper.ts`); drives reveal → self-mark → main re-show → outcome and
  reports over `bridgeCommand`.

### Flow (matches the PRD mermaid exactly)

```
Miss (Again) on a tagged card
  → ladder, one sub-question at a time: attempt → Reveal sub-answer → self-mark Got it / Missed
      (a missed rung reveals the sub-answer, logs the gap, and continues — never blocks, never drills deeper)
  → immediately re-show the MAIN question → attempt → Show answer
      → "I recalled it correctly"  → NOT mastered: card grades Again (relearning) → spaced re-retrieval
                                      (must be recalled in a later session to count); tag ReadyMCAT::corrected
      → "I missed it again"        → reveal full answer (earned) + surface resource link;
                                      tag ReadyMCAT::struggling (aggressive early re-retrieval); returns fresh next session
  → Continue → next card   (always ends gracefully; no loops)
```

Spaced re-retrieval leans on Anki's existing **relearning** (a missed card always grades
Again). The `ReadyMCAT::struggling` / `ReadyMCAT::corrected` tags are the hooks the
points-at-stake queue (engine workstream) reads to resurface corrected concepts — see §5.

### Instrumentation

Every teach-on-miss event (ladder start, each self-mark, the main re-attempt result with the
number of missed sub-questions) is appended to `readymcat_teach_on_miss_log.jsonl` next to the
collection. This instruments the PRD's headline metric — the **corrected-concept re-retrieval
rate** — so a later analysis can ask whether teach-on-miss concepts are recalled better when
they return.

---

## 4. How to test end-to-end

1. Build & run the desktop app on a dev profile (imports the deck once):
   ```
   just run
   ```
   On first run, import `Aidan_.apkg` (File → Import). Copy `subquestions.json` next to your
   collection, or set `READYMCAT_SUBQUESTIONS=/path/to/subquestions.json`, or run from the repo
   root (the reviewer searches all three locations; it logs how many concepts it loaded).
2. Study a deck containing a curated concept — e.g. browse to a card tagged under
   `#Biochemistry::Metabolism::Carbohydrates::Glycolysis` (95 cards) and review it.
3. Reveal the answer and press **Again**. Instead of advancing, the teach-on-miss ladder
   appears. Work through the rungs (Reveal → Got it / Missed), then the main question is
   re-shown.
4. Try both endings: answer **"I recalled it correctly"** (note the _not-mastered → spaced
   re-retrieval_ message and that the card relearns) and, on another card, **"I missed it
   again"** (note the earned full answer, the Khan Academy resource nudge, and the
   `ReadyMCAT::struggling` tag).
5. Confirm the flow always ends at **Continue → next card** (no loops), and inspect
   `readymcat_teach_on_miss_log.jsonl` next to your collection.

Non-curated cards behave exactly like stock Anki on Again, so the change is inert outside the
tagged set.

---

## 5. Integration notes for the engine workstream

- **`taxonomy.json` is the contract.** It uses the exact agreed schema. Resolve a card to a
  category with the algorithm in §1 (tag-over-subdeck, longest path-prefix on `::`). Reference
  implementation: `resolve_category` in `tools/build_taxonomy.py`.
- **`topic_weight`** is percent-of-exam (sums to ≈76.96; CARS excluded). For points-at-stake
  (`topic_weight × weakness`) only relative weights matter; normalize if you prefer.
- **Per-topic weakness:** aggregate FSRS recall probability over the cards in each category
  using the same resolver. The 193 uncategorized cards (research methods) should be treated as
  the "empty/untagged topic" edge case the engine test covers.
- **Teach-on-miss ↔ points-at-stake handshake:** the reviewer tags missed concepts
  `ReadyMCAT::struggling` (and `ReadyMCAT::corrected`). **Implemented on the
  `readymcat-integration` branch:** the points-at-stake queue raises the priority of
  cards/notes carrying `ReadyMCAT::struggling` (a `STRUGGLING_PRIORITY_BOOST`× multiplier in
  `rank_due_cards`), so corrected concepts resurface soon and again later (the spaced
  re-retrieval teach-on-miss relies on) — on top of plain Anki relearning. See
  `docs/readymcat-points-at-stake.md` (§ "Seam reconciliations").
- **Coverage map + give-up rule:** use the coverage numbers in §1 (31/31 categories; 76.96%
  exam weight) — both clear the ≥50% threshold.

---

## 6. Reproducing the taxonomy / coverage

```
python readymcat/tools/build_taxonomy.py --out taxonomy.json \
    --collection /path/to/collection.anki21
```

Writes `taxonomy.json` and prints the coverage report. The script is the single, traceable
source of the weights (AAMC FC percentages + documented even-within-FC split) and the
deck→category mappings.
