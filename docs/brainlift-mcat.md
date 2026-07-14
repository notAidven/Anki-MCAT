# BrainLift — MCAT Study Redesign (ReadyMCAT)

This brainlift is the research and point-of-view behind **ReadyMCAT**, and is kept in lock-step with the PRD (`ReadyMCAT-PRD.md`). It preserves the original research and adds the spiky points of view and learning-science sources that the product is built on. Throughout, spiky points of view are treated as **claims to test**, not proven facts.

## Owners

- Evan Cabrera

## Purpose

The purpose of this BrainLift is to redesign how MCAT students study by identifying the core failures of existing prep tools and building **ReadyMCAT** — a desktop and mobile study app built _inside the Anki codebase_ (a real change to Anki's Rust engine, not a plugin or add-on) — that measures **memory, performance, and readiness as three separate, honest scores** backed by real learning science. The desktop app and an iOS companion share **one engine**. The shipped core includes: the teach-on-miss feature (authored guiding sub-question ladders on every bundled question + spaced re-retrieval, now with a **desktop AI fallback that generates the ladder at runtime** — source-grounded and eval-gated — for any missed card that has no authored one), an honest memory model with a give-up rule, a new value-weighted review order (points-at-stake), a **pre-loaded, zero-import all-format question bank** spanning every MCAT format (fill-in-the-blank/type-in → discrete MCQ → passage-based, including CARS), a **first-launch diagnostic** that seeds ordering without ever showing a score, a simplified honest dashboard, a **home/study hub** as the app's entry screen (four one-tap format tiles with honest due counts, a study-next shortcut, a diagnostic call-to-action, and lightweight progress; finalized on the `readymcat-home-hub` branch and merging in), and the iOS companion running a real review loop on the shared engine (in the engine's default order — points-at-stake is a desktop-side ordering). This already replaces the fragmented AAMC + Anki + UWorld stack for practice; what remains ahead is extending runtime AI generation to iOS, two-way sync, and calibrating the performance and readiness models. The primary audience is college sophomores and juniors on the pre-med track.

## In Scope

- MCAT test-takers (pre-med undergraduates, primarily sophomores and juniors).
- Existing MCAT prep tools and their learning-science foundations.
- Spaced repetition and retrieval practice as retention mechanisms.
- Practice across every question format (fill-in-the-blank → MCQ → passage-based, including CARS), not just single-format recall.
- Score modeling: memory → performance → readiness, with honest uncertainty.
- Value-weighted study prioritization (topic weight × student weakness).
- Desktop and mobile study behavior across one shared engine.
- Anki's FSRS (Free Spaced Repetition Scheduler) algorithm and Rust engine.
- Runtime AI generation of teach-on-miss guiding sub-questions, with source-grounding, guardrails, and an eval harness (the AI feature).

## Out of Scope

- Other graduate exams (LSAT, GMAT, USMLE).
- General flashcard-app design outside the MCAT context.
- Medical-school admissions strategy beyond the MCAT.

## DOK 4: Spiky Points of View (SPOVs)

**SPOV 1 — Reading a wrong-answer explanation feels like learning, but it isn't.**
Instead of displaying a static wrong-answer explanation, the question should be broken into smaller guiding sub-questions, and the corrected concept should be forced back through _re-retrieval on a spaced schedule_. Every QBank delivers explanations as static text after a wrong answer; students read them passively and believe they understand. But passive re-reading is the weakest form of learning. A student who reads an explanation and never retrieves the corrected concept within a scheduled window fails the same question two weeks later. The fix is not better explanations — it is forced re-retrieval, which no current MCAT tool does. _(ReadyMCAT: this is the core feature — authored sub-question ladders on every bundled question + spaced re-retrieval, shipped on desktop, and now extended with a runtime AI fallback that **generates** the ladder for any missed card lacking an authored one, grounded in the card's own material and gated by an eval harness. Extending that generation to iOS is the remaining step.)_

**SPOV 2 — An MCAT tool should be one question bank spanning every format — short fill-in-the-blank recall up to full AAMC-style passage sets — not a single-format silo you supplement with other apps.**
Students stitch tools together because each does only one kind of question (Anki = flashcard recall, QBanks = discrete MCQs, AAMC = passages), and nothing lets you practice the same concept from short recall up to passage-level reasoning in one place. ReadyMCAT's edge is running every format on one engine — fill-in-the-blank/type-in, discrete MCQ, and full passage-based sets including CARS — with one scheduler and one honest score. Letting students try every question type the exam throws at them, in one bank, is the point — rather than teaching content. _(ReadyMCAT: one shared Rust engine across desktop + iOS, and the all-format question bank — fill-in-the-blank/type-in → discrete MCQ → full passage sets including CARS on one scheduler and one honest score — is built and pre-loaded, alongside a first-launch diagnostic that personalizes ordering.)_

## DOK 3: Insights

- **Insight 1 — The illusion of understanding pervades MCAT prep.** QBanks teach platform patterns, not concepts; students confuse memory with readiness; reading explanations feels like learning but isn't. Students constantly mistake a _feeling_ of understanding for the real thing.
- **Insight 2 — There is a gap between memory and performance.** Anki builds recall, but the MCAT tests application of recalled knowledge to passages under time pressure. Strong recall does not predict passage-based reasoning, and no tool measures the gap.
- **Insight 3 — The format-fragmentation gap.** Every tool silos by a single question format — Anki does flashcard recall, QBanks do discrete MCQs, AAMC does passages — so no one bank lets a student practice the same concept from short recall up to passage-level reasoning. This is the root reason students bolt a separate resource onto each question type.
- **Insight 4 — Fragmentation across formats and devices.** Because no shared engine spans every question format (or even desktop ↔ phone), weakness signals never combine across how a concept is tested, and a student cannot answer "what is the single most valuable thing to study right now?" One engine running every format resolves this.

## DOK 2: Knowledge Tree

**Category 1 — Question banks build pattern recognition, not understanding.**

- Sources: Larsen et al. (2009, _Medical Education_); Schmidmaier et al. (2011, _Advances in Health Sciences Education_).
- Summary: Third-party QBanks (UWorld, Blueprint, Kaplan) train students to recognize question archetypes specific to that platform, not the underlying concept, forcing a de-adaptation phase when students switch to official AAMC materials.

**Category 2 — Memory, performance, and readiness are three different things.**

- Sources: Roediger & Karpicke (2006, _Psychological Science_); Kornell & Bjork (2008, _Psychological Science_); Kruger & Dunning (1999, _JPSP_).
- Summary: Recalling a flashcard, answering a novel exam-style question, and predicting a test score are distinct cognitive tasks, but every current tool collapses them into one progress metric that produces confident-looking numbers disconnected from real readiness. FSRS estimates probability of recall, not probability of getting a novel exam question right.

**Category 3 — Students study in two contexts, but tools don't share one engine.**

- Sources: Kornell (2009, _Applied Cognitive Psychology_ — spacing/distributed practice); Kornell & Bjork (2008, _Psychological Science_).
- Summary: Deep work happens at a desk; retrieval practice happens on a phone between classes. No current MCAT tool shares a single scheduling engine across both, so reviews in one context don't inform the other, silently degrading retention. _(Honesty note: the desk↔phone / single-shared-engine point is primarily a product observation. The learning science it leans on is distributed practice — studying the same material across separate sessions beats massing it — not a specific two-context field study; it is a claim to test, not a settled empirical finding.)_

**Category 4 — Tools silo by question format, and the stack is fragmented (the format-fragmentation / one-size-fits-all gap).**

- Sources: Slamecka & Graf (1978, _JEP_ — generation effect); Kornell, Hays & Bjork (2009, _JEP:LMC_) and Richland, Kornell & Kao (2009, _JEP: Applied_) — pretesting / errorful generation; Kapur (2008, _Cognition and Instruction_ — productive failure); Bloom (1984, _Educational Researcher_ — mastery learning / the 2-sigma problem).
- Summary: Each tool covers only one question format — Anki does flashcard recall, QBanks do discrete MCQs, AAMC does passages — so students bolt several apps together to practice one concept across the formats the exam actually uses. The learning science supports spanning those formats in one bank: producing an answer beats recognizing one (generation effect), which is why fill-in-the-blank/type-in matters; attempting before you are sure and correcting the error builds mastery (pretesting, errorful generation, productive failure); and progression works best gated on demonstrated mastery (mastery learning), letting a concept escalate from short recall up to passage-level reasoning. A single engine running every format, on one scheduler, can replace the fragmented stack.

## DOK 1: Facts

**Study tools.**

- **UWorld** — question bank with explanations, analytics, timed/tutor modes. Paid: $300–$1,200. Learning science: retrieval/practice-based learning ("taking memory tests improves long-term retention").
- **Blueprint** — adaptive planner, full-length practice tests, 1,600+ page online textbook, live/self-paced courses. Paid: $99–$3,000 (up to 1-on-1 tutoring). Learning science: spaced repetition.
- **Kaplan MCAT** — 7 full-length exams, lectures, large QBank; live/self-paced/tutoring. Paid: $1,500–$3,600. No strong learning-science basis; structured curriculum + live instruction (online ≈ or slightly better than face-to-face in meta-analysis).
- **AAMC materials** — official practice exams, section banks, question packs, made by the test-makers. Real test simulation; the canonical source of question style and the content outline.
- **Anki (+ premed decks)** — spaced-repetition flashcards, free, massive community decks. Learning science: spaced repetition + active recall. Explicitly "for remembering content, not learning new content."

**MCAT general facts.**

- N = 305,494 total MCAT exams administered across the 2023, 2024, and 2025 testing years combined (~101,800 sittings per year).
- The dominant prep stack is AAMC + Anki + UWorld used together; no single platform captures a majority of students.

**Learning-science facts (added).**

- Retrieval practice beat restudy for one-week retention (61% vs 40%), but recall of isolated facts does not predict passage-based reasoning.
- Pre-testing: attempting (and failing) to answer before instruction improves later learning versus studying alone.
- Generation effect: producing an answer yields better retention than reading it.
- Productive failure: struggling before instruction can improve conceptual transfer.
- Mastery learning: gating progression on demonstrated mastery substantially improves outcomes.

## How the SPOVs map to ReadyMCAT (and how they'll be tested)

- SPOV 1 → **teach-on-miss** (the core feature): authored ladders on every bundled question + spaced re-retrieval, plus a desktop **runtime AI generator** (source-grounded, guardrailed, and measured by the `just eval` harness — schema/answer-leak/grounding gates, an LLM-judge, and a beats-a-baseline win-rate) that produces the ladder for any missed card without an authored one, so teach-on-miss covers imported decks too. Instrumented by the corrected-concept re-retrieval rate (generated vs authored logged distinctly); the full ablation is the fair test still ahead. Extending generation to iOS is the remaining step.
- SPOV 2 → **an all-format question bank** on one shared engine, built and pre-loaded (desktop + iOS on the same Rust backend): fill-in-the-blank/type-in + discrete MCQ + full passage sets including CARS, run on one scheduler with one honest score, plus a first-launch diagnostic that seeds ordering. Still ahead: runtime AI generation, two-way sync, and a strict mastery-gated escalation across formats.
- Each learning-science claim is validated with an honest ablation (feature on / feature off / plain Anki) at equal study time; a null result ("no difference here") is reported, not hidden.

## Sources

- Larsen et al. (2009), _Medical Education_.
- Schmidmaier et al. (2011), _Advances in Health Sciences Education_.
- Roediger & Karpicke (2006), _Psychological Science_.
- Kornell & Bjork (2008), _Psychological Science_.
- Kruger & Dunning (1999), _Journal of Personality and Social Psychology_ ("Unskilled and unaware of it"; Kruger is first author).
- Kornell (2009), _Applied Cognitive Psychology_ (flashcard spacing beats cramming — distributed practice).
- Slamecka & Graf (1978), _Journal of Experimental Psychology_ (generation effect).
- Kornell, Hays & Bjork (2009), _JEP: Learning, Memory, and Cognition_ (errorful generation).
- Richland, Kornell & Kao (2009), _JEP: Applied_ (pretesting effect).
- Kapur (2008), _Cognition and Instruction_ (productive failure).
- Bloom (1984), _Educational Researcher_ (mastery learning / 2-sigma).
- AAMC MCAT content outline and score-scale documentation (topic weights, 472–528 scale).
- Anki / FSRS documentation (Free Spaced Repetition Scheduler).
