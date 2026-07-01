# ReadyMCAT P/S Question Bank — Sources, Licensing & Coverage

**File:** `readymcat/content/psych_soc.json`
**Section:** Psychological, Social, and Biological Foundations of Behavior (P/S)
**AAMC Foundational Concepts covered:** 6, 7, 8, 9, 10 (content categories 6A–10A)

## What this is

An **original**, pre-authored multiple-choice question bank for the MCAT P/S section, written for ReadyMCAT's teach-on-miss / learn-mode flow. Every item is a main exam-style MCQ plus a **ladder of 2–3 guiding sub-questions** (each itself an MCQ) that scaffold a student toward the answer on a miss, per the PRD's TEACH-ON-MISS and LEARN MODE sections.

- **147 main items** across all 12 P/S content categories
- **299 guiding sub-questions** (2–3 per main item)
- **446 total MCQs** (main + sub), each with a written explanation

## Sourcing & legal statement

All questions are **original**, authored from general subject-matter knowledge of psychology, sociology, and behavioral biology and grounded in **free / openly-licensed** references. **No item was copied, scraped, or closely paraphrased from any copyrighted or paid question bank** (e.g., UWorld, Kaplan, Blueprint, AAMC paid materials). The exam's public MCQ *style* is emulated, but all stems, options, explanations, and sub-questions are written from scratch, and the underlying facts used are non-copyrightable (theorists, definitions, mechanisms) verified for correct attribution.

Each item cites the free source where a student can learn the concept, in its `source` field (`name`, `url`, `license`).

### Reference sources (all citations resolve to live pages)

| Source | Use | License |
| --- | --- | --- |
| **OpenStax, _Psychology 2e_** (Spielman, Jenkins, Lovett; 2020) — https://openstax.org/details/books/psychology-2e | Primary reference for FC6, FC7 (7A/7C), and psychology topics in 7B/8A/8B/8C | CC BY-NC-SA 4.0 |
| **OpenStax, _Introduction to Sociology 3e_** (2021) — https://openstax.org/details/books/introduction-sociology-3e | Primary reference for sociology topics in 7B, 8A, 8C, 9A, 9B, 10A | CC BY-NC-SA 4.0 |
| **OpenStax, _Biology 2e_**, §45.7 Behavioral Biology — https://openstax.org/books/biology-2e/pages/45-7-behavioral-biology-proximate-and-ultimate-causes-of-behavior | Biological explanations of social behavior (inclusive fitness, mate choice, foraging, game theory) in 8C | CC BY-NC-SA 4.0 |
| **AAMC "What's on the MCAT Exam?" P/S content outline** (public) — https://students-residents.aamc.org/mcat-exam/whats-mcat-exam | Topic/subtopic structure and official P/S terminology only | Public AAMC outline (structure only; not copied) |
| **Khan Academy MCAT collection (Psych/Soc)** — https://www.khanacademy.org/test-prep/mcat | Concept reference only (no text reused) | Referenced for concepts only |

**Attribution note:** OpenStax content is licensed CC BY-NC-SA 4.0 and must be attributed to OpenStax. This bank uses OpenStax only as a factual reference for authoring original items and cites each relevant section; it does not reproduce OpenStax prose. Category `topic_weight` values referenced in coverage below come from the repository's `taxonomy.json` (derived from AAMC's published content distribution).

## Verification performed

- **Valid JSON:** `json.load` succeeds on `psych_soc.json`.
- **Schema conformance:** every item has all required fields (`id`, `section`, `aamc_category`, `subtopic`, `stem`, `options`, `correct_index`, `explanation`, `difficulty`, `cognitive_level`, `source{name,url,license}`, `subquestions`); every item has exactly 4 options; every `correct_index` is in range; every item has 2–3 sub-questions, each a valid MCQ with an in-range `correct_index`.
- **Taxonomy check:** every `aamc_category` exists in `taxonomy.json` (`6A,6B,6C,7A,7B,7C,8A,8B,8C,9A,9B,10A`).
- **Unique IDs:** all 147 `id` values are unique (`ps-<category>-<n>`).
- **Source URLs:** all OpenStax section slugs were checked and return HTTP 200.
- **Factual spot-checks:** theorist/term attributions verified (e.g., Weber's law, signal detection theory, James–Lange vs. Cannon–Bard vs. Schachter–Singer, Selye's GAS order, Piaget/Erikson/Kohlberg/Vygotsky stages, Weber's authority types, Bourdieu's cultural capital, demographic transition).

## Item metadata distribution

- **Difficulty:** easy 27, medium 111, hard 9
- **Cognitive level:** recall 72, application 75

## Coverage summary (categories → subtopics → counts)

### 6A — Sensing the environment (weight 2.14) — 14 items
Sensation vs. perception & transduction; absolute threshold; Weber's law / difference threshold; signal detection theory; sensory adaptation; vision (rods, cones, dark adaptation); visual processing (feature detection, parallel processing); auditory transduction; theories of pitch perception (place vs. frequency); gustation; olfaction; vestibular & kinesthetic senses; Gestalt principles; depth perception (binocular vs. monocular cues).

### 6B — Making sense of the environment (weight 2.14) — 17 items
Attention (selective/divided); cognitive development (Piaget); availability heuristic; barriers to problem solving (mental set, functional fixedness); intelligence theories (Spearman g, Gardner, fluid/crystallized); sleep stages; circadian rhythms; theories of dreaming; sleep disorders; psychoactive drug classes; reward pathway & addiction; memory encoding (levels of processing); memory stores & capacity (chunking); retrieval & cues; forgetting (interference); memory dysfunction & neural basis (amnesia, hippocampus, LTP); language & the brain (Broca/Wernicke, linguistic relativity).

### 6C — Responding to the world (weight 2.14) — 9 items
James–Lange theory; two-factor theory & misattribution of arousal; components of emotion; universal emotions & expression (Ekman, display rules); neural basis of emotion (amygdala/limbic system); stress appraisal (Lazarus); general adaptation syndrome (Selye); stress physiology (HPA axis, cortisol); types of stressors & coping.

### 7A — Individual influences on behavior (weight 2.99) — 19 items
Neurons & the action potential; neurotransmitters & behavior; nervous system organization (sympathetic/parasympathetic/somatic); hindbrain structures; cortical lobes; methods of studying the brain (EEG/fMRI); behavioral genetics (twin/adoption studies); psychoanalytic, humanistic, trait (Big Five), and social-cognitive personality theories; classifying disorders (DSM, biopsychosocial, diathesis-stress); anxiety disorders; OCD; mood disorders (bipolar/MDD); schizophrenia; theories of motivation (drive-reduction, Yerkes-Dodson, Maslow); biological basis of hunger (hypothalamus, leptin); physiological (prenatal) development.

### 7B — Social processes that influence human behavior (weight 2.99) — 13 items
Social facilitation; social loafing; deindividuation; bystander effect (diffusion of responsibility); conformity (Asch); obedience (Milgram); group polarization; groupthink; social norms & sanctions; folkways/mores/taboos; deviance & anomie (Durkheim, Merton, labeling); collective behavior (fads, mass hysteria); socialization & its agents.

### 7C — Attitude and behavior change (weight 2.99) — 13 items
Habituation & dishabituation; classical conditioning components (NS/US/UR/CS/CR); acquisition/extinction/spontaneous recovery; generalization & discrimination; operant reinforcement vs. punishment; reinforcement schedules; shaping; latent learning & cognitive maps; biological constraints (taste aversion, preparedness); observational learning (Bandura, mirror neurons); elaboration likelihood model; cognitive dissonance; compliance techniques (foot-in-the-door / door-in-the-face).

### 8A — Self-identity (weight 1.71) — 9 items
Self-concept & self-esteem; locus of control & self-efficacy; Erikson's psychosocial stages; Freud's psychosexual stages; Kohlberg's moral development; Vygotsky (ZPD, scaffolding); the looking-glass self (Cooley); Mead's theory of the self (I/me, generalized other); social identity theory.

### 8B — Social thinking (weight 1.71) — 9 items
Attribution (dispositional vs. situational); fundamental attribution error; actor-observer bias; self-serving & just-world biases; stereotype/prejudice/discrimination; stereotype threat & the contact hypothesis; self-fulfilling prophecy (Pygmalion); ethnocentrism vs. cultural relativism; in-group/out-group perception (out-group homogeneity).

### 8C — Social interactions (weight 1.71) — 11 items
Status (ascribed/achieved/master); role conflict & role strain (and role exit); primary vs. secondary groups (reference groups, dyad/triad); bureaucracy & formal organizations (Weber, iron law of oligarchy, McDonaldization); dramaturgy & self-presentation (Goffman, front/back stage); nonverbal communication; interpersonal attraction (mere exposure, matching); attachment (Ainsworth, Harlow); altruism & inclusive fitness; aggression (frustration-aggression); biological explanations of social behavior (parental investment, foraging, game theory).

### 9A — Understanding social structure (weight 1.92) — 12 items
Theoretical approaches: functionalism, conflict theory, symbolic interactionism (micro vs. macro), social constructionism; education (hidden curriculum, tracking); religion (church/sect/ecclesia, secularization); government (Weber's authority types); health & medicine (medicalization, sick role); culture (material vs. nonmaterial, culture lag/shock/diffusion); subculture vs. counterculture; elements of culture (values, norms, symbols, language); family & kinship (nuclear/extended, endogamy).

### 9B — Demographic characteristics and processes (weight 1.92) — 11 items
Sex vs. gender (and gender identity); race/ethnicity as social constructs (minority group); demographic transition theory; Malthusian theory; migration (push/pull, net migration); aging ("graying," dependency ratio); social movements (relative deprivation, resource mobilization); globalization; urbanization & gentrification (suburbanization); fertility & mortality measures (crude birth/death rate, infant mortality); sexual orientation as a demographic characteristic.

### 10A — Social inequality (weight 1.28) — 10 items
Social stratification & SES (caste vs. class); cultural capital & social capital (Bourdieu); social reproduction & meritocracy; intersectionality (privilege); social mobility (inter/intragenerational, vertical/horizontal); absolute vs. relative poverty (social exclusion); spatial inequality & residential segregation; environmental justice; health disparities & the SES gradient; global inequality (dependency vs. modernization theory).

## Known gaps / future additions

- **Physics/biology-heavy behavioral-neuroscience detail** (e.g., detailed second-messenger cascades) is intentionally light; P/S emphasizes concepts, not deep biochemistry.
- A few AAMC micro-subtopics are represented at the category level rather than with a dedicated item (e.g., hypnosis/meditation within 6B consciousness; specific personality-disorder clusters within 7A; specific religious-organization subtypes beyond church/sect/ecclesia in 9A). These are natural targets for a second authoring pass.
- All items are standalone (discrete) questions; **passage-based question sets** are out of scope for this pre-loaded bank and could be added later.
- Difficulty skews "medium"; a future pass could add more "hard" application/experiment-interpretation items to better mirror the live exam's research-reasoning emphasis.
