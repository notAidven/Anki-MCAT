# ReadyMCAT — content, provisioning & teach-on-miss

This folder houses ReadyMCAT's **study content** (the pre-loaded, source-cited
question bank and the first-launch diagnostic), the **tools** that build and
provision it, and the **teach-on-miss** reviewer feature. ReadyMCAT is an MCAT
study app forked from Anki; the product rationale is in
[`../ReadyMCAT-PRD.md`](../ReadyMCAT-PRD.md).

> **Proof docs:** [`PROOF-FRIDAY.md`](PROOF-FRIDAY.md) maps every Friday
> requirement (desktop AI + held-out eval, two-way sync, the three honest scores)
> to concrete in-repo evidence with real numbers; [`PROOF.md`](PROOF.md) is the
> broader Wednesday-MVP capture checklist.

| Artifact                | Path                                                                                                              | Consumed by                                                              |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Canonical question bank | [`content/question_bank.json`](content/question_bank.json)                                                        | the collection builder                                                   |
| MCQ section banks       | `content/{bio_biochem,chem_phys,psych_soc}.json`                                                                  | `tools/build_question_bank.py`                                           |
| Free-response banks     | `content/free_response_{bio_biochem,chem_phys,psych_soc}.json`                                                    | `tools/build_question_bank.py`                                           |
| Passage banks (+ CARS)  | `content/passage_{bio_biochem,chem_phys,psych_soc}.json`, `content/passage_cars.json`                             | `tools/build_question_bank.py`                                           |
| Diagnostic bank         | [`diagnostic/diagnostic_quiz.json`](diagnostic/diagnostic_quiz.json)                                              | first-launch diagnostic ([`diagnostic/README.md`](diagnostic/README.md)) |
| AAMC taxonomy + weights | [`../taxonomy.json`](../taxonomy.json)                                                                            | engine (points-at-stake, coverage, per-topic memory)                     |
| Teach-on-miss ladders   | each note's `Subquestions` field; legacy [`../subquestions.json`](../subquestions.json)                           | desktop reviewer                                                         |
| Builder → provisioner   | [`tools/build_question_bank.py`](tools/build_question_bank.py) → `qt/aqt/readymcat_provision.py`                  | first launch (zero import)                                               |
| Demo dashboard seeder   | [`tools/seed_demo_dashboard.py`](tools/seed_demo_dashboard.py)                                                    | Tools → Load ReadyMCAT demo data (SYNTHETIC)                             |
| Teach-on-miss reviewer  | `ts/reviewer/` (`mcq.ts`, `fr.ts`, `passage.ts`, `teach_on_miss.ts`), `qt/aqt/reviewer.py`, `qt/aqt/readymcat.py` | desktop app                                                              |

**Zero import.** A brand-new user gets the full bank pre-loaded on first launch —
there is no `.apkg` import step. The community **"Aidan" deck** (`Aidan_.apkg`,
8,891 notes / 15,175 cards, 84 subdecks across all four MCAT sections) is now an
**optional** import the taxonomy still supports — its tags map onto the same 31
AAMC categories — rather than the base deck; it is credited to its author and
used for educational purposes.

---

## 0. The pre-loaded question bank (zero import)

On first launch `qt/aqt/readymcat_provision.py` builds **four decks — 1,075
cards — directly into the new user's collection**, no import required:

| Deck                        | Format                                    |     Cards |
| --------------------------- | ----------------------------------------- | --------: |
| `ReadyMCAT`                 | Discrete multiple-choice                  |       414 |
| `ReadyMCAT::Free Response`  | Type-in / fill-in-the-blank (auto-graded) |       410 |
| `ReadyMCAT::Passages`       | AAMC-style passage sets (36 passages)     |       174 |
| `ReadyMCAT::Passages::CARS` | CARS passage sets (15 passages)           |        77 |
| **Total**                   |                                           | **1,075** |

Every item is 100% original and per-item source-cited (OpenStax CC BY,
LibreTexts, and public-domain/original CARS); see the per-section
`content/*_SOURCES.md` files and the stdlib validators in `content/`. Nothing is
taken from UWorld, Kaplan, Blueprint, or AAMC-paid materials, and the app makes
**no runtime model calls** — the bank is statically authored content shipped with
the app. Authored items are CC BY-SA 4.0.

**Build + provision.** `tools/build_question_bank.py` merges and validates the
section banks (MCQ + free-response + passages + CARS) into the canonical
`content/question_bank.json`. On first launch the provisioner creates the note
types (one card per question), builds the four decks, tags every AAMC card
`#ReadyMCAT::AAMC::<category>`, and drops the sidecars (`taxonomy.json`,
`subquestions.json`, `diagnostic_quiz.json`) next to the collection. It is
**idempotent per note** (stable guids), so a profile created before CARS existed
gains exactly the new cards without duplicates.

**Input-required answering + FSRS grading.** Unlike a self-graded flashcard,
every ReadyMCAT card requires a real input — select an MCQ option, type a
free-response answer (auto-graded by normalized-string / key-term /
numeric-tolerance matching), or answer a passage-based MCQ with the passage shown
alongside — and the reviewer grades the input into FSRS:

| Result                                                               | FSRS grade                      |
| -------------------------------------------------------------------- | ------------------------------- |
| Correct on the **first** attempt                                     | **Good**                        |
| Needed the teach-on-miss ladder (correct only after, or still wrong) | **Again** — relearning / spaced |

Immediate success right after the scaffold is never treated as mastery, so a
missed card always relearns; a card missed **again** after the ladder is
additionally tagged `ReadyMCAT::struggling` for the points-at-stake boost (§5).

**Per-question teach-on-miss.** Teach-on-miss fires on **every** bundled card: on
a wrong answer the reviewer runs the guiding sub-questions stored in that card's
own `Subquestions` field — one at a time (attempt → reveal) → re-show the main
question → correct = spaced re-retrieval, wrong again = earned explanation +
resource link (§3). The legacy curated `subquestions.json` ladders (§2) still
apply to classic self-graded cards from an optional Aidan import.

**First-launch diagnostic.** A short quiz (31-item short mode drawn from a
37-item bank covering all 31 AAMC content categories) seeds each topic's weakness
prior so the points-at-stake order is useful from session one; it **never** writes
the dashboard's memory / performance / readiness scores. Content + method spec:
[`diagnostic/README.md`](diagnostic/README.md); engine scorer + prior seeding:
`rslib/src/diagnostic/`.

**Backend endpoints.** The desktop SvelteKit pages reach the backend over the
local media server (`qt/aqt/mediasrv.py`), which registers `readymcat-dashboard`
and `readymcat-diagnostic` as pages and exposes `pointsAtStakeQueue`
(dashboard + ranked queue) and `getDiagnosticQuiz` / `scoreAndSeedDiagnostic`
(the diagnostic). Endpoint registration is covered by a mediasrv test. The
home/study hub adds a `readymcat-home` page and a `readymcatHomeStatus`
aggregation endpoint (backed by `tools/home_launcher.py`); it merges in from the
`readymcat-home-hub` branch alongside these docs.

**Demo data (synthetic).** **Tools → Load ReadyMCAT demo data (SYNTHETIC)** runs
`tools/seed_demo_dashboard.py` (wired via `qt/aqt/readymcat_demo.py`) to populate
clearly-labeled synthetic reviews so the honest-memory dashboard can be previewed
without accumulating hundreds of real ones.

---

## 1. `taxonomy.json` — deck → AAMC outline

Maps each card's tags/subdecks onto the **31 AAMC content categories** and assigns
each a `topic_weight` (percent-of-exam). Schema (exactly as the engine expects):

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

The pre-loaded bank's AAMC cards are natively tagged `#ReadyMCAT::AAMC::<category>`, so it
covers all **31 / 31** content categories by construction. The report below is an illustrative
run over the **optional Aidan deck**
(`python readymcat/tools/build_taxonomy.py --collection <collection.anki21>`):

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

## 2. `subquestions.json` — legacy teach-on-miss ladders

These curated ladders are the **legacy** path for classic self-graded cards (e.g. from an
optional Aidan import); every bundled question in the pre-loaded bank now carries its own
ladder in its `Subquestions` field (§0), so teach-on-miss is no longer limited to this
curated subset.

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

Implements the PRD's core feature. The reviewer does **not** just flip to the back on a miss —
it runs that card's guiding ladder (its own `Subquestions` for bundled cards, or the curated
concept ladder / a runtime-generated one for classic cards), then re-shows the main question.
The interactive bundled reviewers (MCQ/FR/passage) are retrieve-first by construction; plain
**basic front/back flashcards** get a **retrieve-before-reveal** path so the ladder runs while
the back is still hidden (see "Retrieve-before-reveal for basic front/back flashcards" in the
PRD). Files:

- `qt/aqt/readymcat.py` — loads/caches `subquestions.json`, resolves a card → concept,
  extracts a resource link, and appends instrumentation events to a JSONL log.
- `qt/aqt/reviewer.py` — for basic front/back cards, `_retrieve_first_available` decides
  eligibility and `_showAnswerButton` renders a question-side "Stuck? work it out" button;
  `_on_retrieve_first` (routed from `_linkHandler`'s `rmcatStuck`) starts the ladder with the
  back still hidden (`_maybe_start_teach_on_miss(trigger="stuck")`). `tom:*` bridge commands are
  handled in `_linkHandler`; `_finish_teach_on_miss` reschedules the card as Again (relearning)
  and advances. `_answerCard` (split into interception + `_do_answer_card`) no longer launches
  teach-on-miss post-reveal — that would reveal the back before the ladder.
- `ts/reviewer/teach_on_miss.ts` — the in-card UI (exposed globally as `_teachOnMissStart`
  via `index.ts`/`index_wrapper.ts`); drives reveal → self-mark → main re-show → outcome and
  reports over `bridgeCommand`.

### Flow (matches the PRD mermaid exactly)

```
Miss (Again) on a card
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

1. Build & run the desktop app on a fresh dev profile:
   ```
   just run
   ```
   The bank pre-loads automatically on first launch — **no import step** — and the sidecars
   (`taxonomy.json`, `subquestions.json`, `diagnostic_quiz.json`) are dropped next to the
   collection. (Optional: import `Aidan_.apkg` via File → Import to exercise the classic
   self-graded teach-on-miss path in §2.)
2. Study any of the four decks (`ReadyMCAT`, `ReadyMCAT::Free Response`,
   `ReadyMCAT::Passages`, `ReadyMCAT::Passages::CARS`). Answer a question wrong (an MCQ pick,
   a type-in, or a passage MCQ) — the reviewer grades it **Again**.
3. Instead of advancing, the teach-on-miss ladder appears. Work through the rungs
   (Reveal → Got it / Missed), then the main question is re-shown.
4. Try both endings: answer **"I recalled it correctly"** (note the _not-mastered → spaced
   re-retrieval_ message and that the card relearns) and, on another card, **"I missed it
   again"** (note the earned full answer, the resource nudge, and the `ReadyMCAT::struggling`
   tag).
5. Confirm the flow always ends at **Continue → next card** (no loops), and inspect
   `readymcat_teach_on_miss_log.jsonl` next to your collection.
6. Open **Tools → ReadyMCAT Dashboard** for the honest-memory view (and **Tools → Load
   ReadyMCAT demo data (SYNTHETIC)** first if you want to preview it before 200 real reviews).

---

## 5. Integration notes for the engine workstream

- **`taxonomy.json` is the contract.** It uses the exact agreed schema. Resolve a card to a
  category with the algorithm in §1 (tag-over-subdeck, longest path-prefix on `::`). Reference
  implementation: `resolve_category` in `tools/build_taxonomy.py`.
- **`topic_weight`** is percent-of-exam (sums to ≈76.96; CARS excluded). For points-at-stake
  (`topic_weight × weakness`) only relative weights matter; normalize if you prefer.
- **Per-topic weakness:** aggregate FSRS recall probability over the cards in each category
  using the same resolver. The uncategorized cards (research methods) should be treated as
  the "empty/untagged topic" edge case the engine test covers.
- **Teach-on-miss ↔ points-at-stake handshake:** the reviewer tags missed concepts
  `ReadyMCAT::struggling` (and `ReadyMCAT::corrected`). The points-at-stake queue raises the
  priority of cards/notes carrying `ReadyMCAT::struggling` (a `STRUGGLING_PRIORITY_BOOST`×
  multiplier in `rank_due_cards`), so corrected concepts resurface soon and again later (the
  spaced re-retrieval teach-on-miss relies on) — on top of plain Anki relearning. See
  `docs/readymcat-points-at-stake.md` (§ "Seam reconciliations").
- **Coverage map + give-up rule:** the pre-loaded bank covers all 31 categories by construction
  (native `#ReadyMCAT::AAMC` tags), clearing the ≥50% threshold.

---

## 6. Reproducing the taxonomy / coverage

```
python readymcat/tools/build_taxonomy.py --out taxonomy.json \
    --collection /path/to/collection.anki21
```

Writes `taxonomy.json` and prints the coverage report. The script is the single, traceable
source of the weights (AAMC FC percentages + documented even-within-FC split) and the
deck→category mappings.
