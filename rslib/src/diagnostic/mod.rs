// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! ReadyMCAT introductory-diagnostic scorer and prior seeding.
//!
//! The first time a student opens ReadyMCAT they take a short, breadth-first
//! diagnostic that samples every AAMC content category (see
//! `readymcat/diagnostic/`). This module turns those responses into a
//! **per-topic proficiency prior** that personalises study *ordering* and
//! prerequisite *placement* — and nothing else.
//!
//! ## The honesty rule (enforced, not just documented)
//!
//! A short quiz is a *prior*, not a readiness verdict. Its results feed exactly
//! two things:
//!
//! 1. the points-at-stake **ordering** seed (`student_weakness` per category),
//!    with a precision-weighted decay so the seed self-erases as real FSRS
//!    reviews accrue ([`decayed_weakness`]); and
//! 2. coarse prerequisite-graph **placement bands** ([`Band`]).
//!
//! It **never** writes the dashboard's memory / performance / readiness scores,
//! which obey their own give-up rule. Concretely, the per-topic aggregation in
//! [`crate::points_at_stake::Aggregation`] (mean recall, coverage, the ranged
//! memory score) is computed purely from FSRS state and is *never* touched by
//! this module. The seed is applied only when ranking due cards. A guardrail
//! test enforces this (see `crate::points_at_stake` tests + `pylib/tests`).
//!
//! ## The prior-mapping method (README Part 3)
//!
//! * **Step 1 — difficulty-aware evidence.** Each response becomes an effective
//!   success in `[0, 1]`. A correct *hard* item is stronger evidence of
//!   proficiency than a correct *easy* one; a missed *easy* item is stronger
//!   evidence of a gap ([`item_score`]).
//! * **Step 2 — beta-binomial shrinkage.** `p_hat = (k + kappa*mu0) /
//!   (n + kappa)` with a small `kappa`, so 1–2 items only *nudge* the estimate.
//! * **Step 3 — hierarchical pooling.** `mu0` is blended from the
//!   category → foundational-concept → section → global means, so a student who
//!   bombs most of a foundational concept has every category in it pulled down.
//! * **Step 4 — seed.** `weakness_prior = 1 - p_hat`.
//! * **Step 5 — decay.** [`decayed_weakness`] blends the prior with FSRS
//!   weakness by precision (`w_fsrs` = reviewed cards in the category).
//! * **Step 6 — placement bands.** held / partial / gap ([`Band`]).

pub mod service;

use std::collections::BTreeMap;

use serde::Deserialize;
use serde::Serialize;

use crate::prelude::*;

/// Collection-config key under which the diagnostic prior + bands are
/// persisted. Stored as JSON config (travels with the collection, sync- and
/// undo-aware) and kept entirely separate from any score the dashboard shows.
pub const DIAGNOSTIC_PRIOR_CONFIG_KEY: &str = "readymcatDiagnosticPrior";
/// Schema version of the persisted [`DiagnosticPrior`] blob.
pub const DIAGNOSTIC_PRIOR_SCHEMA: u32 = 1;

/// Default baseline proficiency `mu0` (README Step 2: "start ~0.5").
pub const DEFAULT_MU0: f64 = 0.5;
/// Default beta-binomial prior strength in pseudo-items (README: `kappa = 4-8`,
/// worked example uses 6). Small on purpose: the quiz nudges, never dominates.
pub const DEFAULT_KAPPA: f64 = 6.0;
/// Default Step-5 decay pseudo-count `c0` (README: "~5-10 reviews"). The prior
/// is worth this many FSRS reviews; once a category passes it, FSRS dominates.
pub const DEFAULT_DECAY_PSEUDOCOUNT: f64 = 8.0;

/// `p_hat >= 0.75` => the foundation is already **held**.
pub const BAND_HELD_MIN: f64 = 0.75;
/// `0.40 <= p_hat < 0.75` => **partial**; below `0.40` => **gap**.
pub const BAND_PARTIAL_MIN: f64 = 0.40;

/// Authored difficulty label. Consumed by the Step-1 difficulty adjustment;
/// should be recalibrated empirically once real response data exists.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Difficulty {
    Easy,
    Medium,
    Hard,
}

impl Difficulty {
    /// Parse the authored label; anything unrecognised falls back to `Medium`
    /// (the neutral middle), so a typo never crashes the scorer.
    pub fn from_label(label: &str) -> Self {
        match label.trim().to_ascii_lowercase().as_str() {
            "easy" => Difficulty::Easy,
            "hard" => Difficulty::Hard,
            _ => Difficulty::Medium,
        }
    }

    /// Target accuracy `t` of a "borderline" test-taker (README Step 1 MVP).
    fn target(self) -> f64 {
        match self {
            Difficulty::Easy => 0.80,
            Difficulty::Medium => 0.55,
            Difficulty::Hard => 0.35,
        }
    }
}

/// A coarse prerequisite-placement band (README Step 6). Deliberately coarse
/// and revisable: pooling + re-evaluation as reviews arrive mean a single
/// lucky/unlucky item can neither unlock nor lock a concept on its own.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Band {
    /// Foundation already held; learn-mode should not re-teach it.
    Held,
    /// Partially known.
    Partial,
    /// A genuine gap.
    Gap,
}

impl Band {
    pub fn from_proficiency(p_hat: f64) -> Self {
        if p_hat >= BAND_HELD_MIN {
            Band::Held
        } else if p_hat >= BAND_PARTIAL_MIN {
            Band::Partial
        } else {
            Band::Gap
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Band::Held => "held",
            Band::Partial => "partial",
            Band::Gap => "gap",
        }
    }
}

/// One administered item's outcome. A skipped item (`answered = false`) counts
/// as **no evidence** — never as wrong.
#[derive(Debug, Clone)]
pub struct ItemResponse {
    pub item_id: String,
    /// AAMC content-category id, e.g. "1A" (joins to `taxonomy.json`).
    pub category: String,
    pub difficulty: Difficulty,
    pub answered: bool,
    pub correct: bool,
}

/// Step-3 pooling blend weights. More specific groups get more weight, so a
/// category is informed most by its own foundational concept, then its section,
/// then the global mean. Tunable; the defaults are deliberately gentle.
#[derive(Debug, Clone, Copy)]
pub struct PoolWeights {
    pub global: f64,
    pub section: f64,
    pub fc: f64,
}

impl Default for PoolWeights {
    fn default() -> Self {
        PoolWeights {
            global: 1.0,
            section: 2.0,
            fc: 3.0,
        }
    }
}

/// Knobs for [`score_diagnostic`].
#[derive(Debug, Clone)]
pub struct ScorerConfig {
    pub mu0: f64,
    pub kappa: f64,
    /// Step-1 difficulty weighting. When `false`, evidence is raw correctness.
    pub difficulty_aware: bool,
    /// Step-3 hierarchical pooling. When `false`, `mu0` is the fixed baseline.
    pub pool: bool,
    pub pool_weights: PoolWeights,
}

impl Default for ScorerConfig {
    fn default() -> Self {
        ScorerConfig {
            mu0: DEFAULT_MU0,
            kappa: DEFAULT_KAPPA,
            difficulty_aware: true,
            pool: true,
            pool_weights: PoolWeights::default(),
        }
    }
}

impl ScorerConfig {
    /// The "simple beta-binomial" path the README's worked example uses: raw
    /// correctness, a fixed baseline `mu0`, and no pooling. Useful as a sanity
    /// fixture and when only one category is administered.
    pub fn simple_beta_binomial(mu0: f64, kappa: f64) -> Self {
        ScorerConfig {
            mu0,
            kappa,
            difficulty_aware: false,
            pool: false,
            pool_weights: PoolWeights::default(),
        }
    }
}

/// Per-category result of the scorer.
#[derive(Debug, Clone)]
pub struct CategoryScore {
    pub category: String,
    /// Items answered (0, 1 or 2 in the bundled bank).
    pub n: u32,
    /// Raw number correct (for reporting/traceability).
    pub k: u32,
    /// Shrunk, pooled proficiency in `[0, 1]`.
    pub p_hat: f64,
    /// `1 - p_hat`; the points-at-stake weakness seed.
    pub weakness: f64,
    pub band: Band,
}

/// Foundational concept of an AAMC category id: the leading digits
/// (`"1A" -> "1"`, `"10A" -> "10"`). Empty when the id has no leading digit.
pub fn foundational_concept_of(category: &str) -> &str {
    let end = category
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(category.len());
    &category[..end]
}

/// AAMC section of a category, derived from its foundational concept:
/// FC 1–3 → Bio/Biochem, FC 4–5 → Chem/Phys, FC 6–10 → Psych/Soc. Empty for an
/// unparseable id (so it simply does not contribute a section group).
pub fn section_of_category(category: &str) -> &'static str {
    match foundational_concept_of(category).parse::<u32>() {
        Ok(1..=3) => "Bio/Biochem",
        Ok(4..=5) => "Chem/Phys",
        Ok(6..=10) => "Psych/Soc",
        _ => "",
    }
}

/// Step 1: convert one response into an effective success in `[0, 1]`.
///
/// * difficulty **off** → raw correctness (`1.0` / `0.0`), which reproduces the
///   README worked example exactly.
/// * difficulty **on** → `0.5 + (correct - t(difficulty)) / 2`, a monotone map
///   in which a correct hard item scores highest and a missed easy item lowest.
pub fn item_score(correct: bool, difficulty: Difficulty, difficulty_aware: bool) -> f64 {
    let correct = if correct { 1.0 } else { 0.0 };
    if !difficulty_aware {
        return correct;
    }
    (0.5 + (correct - difficulty.target()) / 2.0).clamp(0.0, 1.0)
}

#[derive(Default, Clone, Copy)]
struct GroupAcc {
    sum: f64,
    n: u32,
}

impl GroupAcc {
    fn add(&mut self, score: f64) {
        self.sum += score;
        self.n += 1;
    }

    fn mean(&self) -> Option<f64> {
        (self.n > 0).then(|| self.sum / self.n as f64)
    }
}

#[derive(Default)]
struct CatAcc {
    n: u32,
    k: u32,
    k_eff: f64,
}

/// Score a set of responses into per-category proficiency (Steps 1–4).
///
/// Pure and deterministic: the same responses + config always yield the same
/// scores. Output is sorted by category id.
pub fn score_diagnostic(responses: &[ItemResponse], cfg: &ScorerConfig) -> Vec<CategoryScore> {
    let mut by_cat: BTreeMap<String, CatAcc> = BTreeMap::new();
    let mut global = GroupAcc::default();
    let mut by_section: BTreeMap<String, GroupAcc> = BTreeMap::new();
    let mut by_fc: BTreeMap<String, GroupAcc> = BTreeMap::new();

    for r in responses {
        // Ensure the category appears in the output even if every item for it
        // was skipped — it then falls back to the group prior (README edge case).
        let acc = by_cat.entry(r.category.clone()).or_default();
        if !r.answered {
            continue;
        }
        let score = item_score(r.correct, r.difficulty, cfg.difficulty_aware);
        acc.n += 1;
        acc.k += u32::from(r.correct);
        acc.k_eff += score;

        global.add(score);
        by_section
            .entry(section_of_category(&r.category).to_string())
            .or_default()
            .add(score);
        by_fc
            .entry(foundational_concept_of(&r.category).to_string())
            .or_default()
            .add(score);
    }

    let global_mean = global.mean().unwrap_or(cfg.mu0);

    by_cat
        .into_iter()
        .map(|(category, acc)| {
            let mu0_c = if cfg.pool {
                pooled_mu0(
                    cfg,
                    global_mean,
                    by_section.get(section_of_category(&category)),
                    by_fc.get(foundational_concept_of(&category)),
                )
            } else {
                cfg.mu0
            };
            // Beta-binomial posterior mean. With n = 0 this is exactly `mu0_c`
            // (the group prior), which is the documented skipped-item fallback.
            let p_hat = (acc.k_eff + cfg.kappa * mu0_c) / (acc.n as f64 + cfg.kappa);
            let p_hat = p_hat.clamp(0.0, 1.0);
            CategoryScore {
                category,
                n: acc.n,
                k: acc.k,
                p_hat,
                weakness: 1.0 - p_hat,
                band: Band::from_proficiency(p_hat),
            }
        })
        .collect()
}

/// Step 3: blend the baseline `mu0` from the global / section / foundational-
/// concept means over the groups that actually have data.
fn pooled_mu0(
    cfg: &ScorerConfig,
    global_mean: f64,
    section: Option<&GroupAcc>,
    fc: Option<&GroupAcc>,
) -> f64 {
    let mut num = cfg.pool_weights.global * global_mean;
    let mut den = cfg.pool_weights.global;
    if let Some(mean) = section.and_then(GroupAcc::mean) {
        num += cfg.pool_weights.section * mean;
        den += cfg.pool_weights.section;
    }
    if let Some(mean) = fc.and_then(GroupAcc::mean) {
        num += cfg.pool_weights.fc * mean;
        den += cfg.pool_weights.fc;
    }
    if den > 0.0 {
        num / den
    } else {
        cfg.mu0
    }
}

/// Step 5: precision-weighted blend of the diagnostic weakness prior with the
/// FSRS weakness.
///
/// `w_fsrs` is the per-category FSRS evidence count (reviewed cards in the
/// category); `c0` is the prior's fixed pseudo-count. Early on `w_fsrs ≈ 0`, so
/// the prior drives ordering; once a category accrues many reviews
/// `w_fsrs >> c0` and the prior's contribution vanishes. The prior thus touches
/// *ordering only* and self-erases.
pub fn decayed_weakness(prior_weakness: f64, fsrs_weakness: f64, w_fsrs: f64, c0: f64) -> f64 {
    let c0 = c0.max(0.0);
    let w = w_fsrs.max(0.0);
    let denom = c0 + w;
    if denom <= 0.0 {
        return fsrs_weakness;
    }
    (c0 * prior_weakness + w * fsrs_weakness) / denom
}

// --- Persistence ------------------------------------------------------------

/// The persisted per-category prior + band.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
pub struct CategoryPrior {
    #[serde(default)]
    pub n: u32,
    #[serde(default)]
    pub k: u32,
    pub p_hat: f64,
    pub weakness: f64,
    #[serde(default)]
    pub band: String,
}

/// The persisted diagnostic prior blob (collection config). Holds the
/// ordering seed (`weakness` per category) and the placement `band`s, plus the
/// decay pseudo-count so Step 5 is reproducible.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosticPrior {
    #[serde(default)]
    pub schema_version: u32,
    #[serde(default)]
    pub mode: String,
    #[serde(default)]
    pub taken_at: i64,
    #[serde(default = "default_decay_pseudocount")]
    pub decay_pseudocount: f64,
    #[serde(default)]
    pub categories: BTreeMap<String, CategoryPrior>,
}

fn default_decay_pseudocount() -> f64 {
    DEFAULT_DECAY_PSEUDOCOUNT
}

impl DiagnosticPrior {
    /// Build a persistable prior from freshly-computed scores.
    pub fn from_scores(mode: &str, decay_pseudocount: f64, scores: &[CategoryScore]) -> Self {
        let categories = scores
            .iter()
            .map(|s| {
                (
                    s.category.clone(),
                    CategoryPrior {
                        n: s.n,
                        k: s.k,
                        p_hat: s.p_hat,
                        weakness: s.weakness,
                        band: s.band.as_str().to_string(),
                    },
                )
            })
            .collect();
        DiagnosticPrior {
            schema_version: DIAGNOSTIC_PRIOR_SCHEMA,
            mode: mode.to_string(),
            taken_at: TimestampSecs::now().0,
            decay_pseudocount,
            categories,
        }
    }

    /// The ordering-seed weakness for a category, if the diagnostic covered it.
    pub fn weakness_for(&self, category: &str) -> Option<f64> {
        self.categories.get(category).map(|c| c.weakness)
    }

    /// The effective decay pseudo-count, guarding against a corrupt/zero value.
    pub fn decay_pseudocount(&self) -> f64 {
        if self.decay_pseudocount > 0.0 {
            self.decay_pseudocount
        } else {
            DEFAULT_DECAY_PSEUDOCOUNT
        }
    }
}

impl Collection {
    /// Load the persisted diagnostic prior, if the student has taken it.
    pub fn load_diagnostic_prior(&self) -> Option<DiagnosticPrior> {
        self.get_config_optional::<DiagnosticPrior, _>(DIAGNOSTIC_PRIOR_CONFIG_KEY)
    }

    /// Persist the diagnostic prior. Not undoable: it is a one-off intake
    /// artifact, not a study action, and must never appear in the undo stack
    /// alongside real reviews.
    pub fn save_diagnostic_prior(&mut self, prior: &DiagnosticPrior) -> Result<()> {
        self.set_config_json(DIAGNOSTIC_PRIOR_CONFIG_KEY, prior, false)?;
        Ok(())
    }

    /// Forget the diagnostic prior (so it can be retaken). No-op when absent.
    pub fn clear_diagnostic_prior(&mut self) -> Result<()> {
        if self.load_diagnostic_prior().is_some() {
            self.remove_config(DIAGNOSTIC_PRIOR_CONFIG_KEY)?;
        }
        Ok(())
    }
}

// --- Quiz bank loading ------------------------------------------------------
//
// The question bank is content authored independently of the study deck (see
// `readymcat/diagnostic/`). The backend reads + filters it so every client
// (desktop, later iOS) shares one source of truth and the file-location logic
// lives in one place — mirroring how `taxonomy.json` is loaded.

/// A per-item grounding source (for traceability + a free review link). Never
/// used to compute the prior; carried through so the UI can cite it.
#[derive(Debug, Clone, Deserialize, Default)]
pub struct ItemSource {
    #[serde(default, rename = "ref")]
    pub source_ref: String,
    #[serde(default)]
    pub location: String,
    #[serde(default)]
    pub url: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct QuizOption {
    pub key: String,
    pub text: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct QuizItem {
    pub id: String,
    pub category: String,
    #[serde(default)]
    pub category_name: String,
    #[serde(default)]
    pub section: String,
    #[serde(default)]
    pub discipline: String,
    #[serde(default)]
    pub cognitive_level: String,
    #[serde(default)]
    pub difficulty: String,
    pub stem: String,
    pub options: Vec<QuizOption>,
    pub answer: String,
    #[serde(default)]
    pub rationale: String,
    #[serde(default)]
    pub source: ItemSource,
}

/// The diagnostic question bank (`diagnostic_quiz.json`). Only the fields the
/// feature consumes are modelled; the rest of the file is ignored.
#[derive(Debug, Clone, Deserialize)]
pub struct QuizBank {
    #[serde(default)]
    pub quiz_id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub items: Vec<QuizItem>,
}

impl QuizBank {
    pub fn from_json_str(s: &str) -> Result<Self> {
        let bank: QuizBank = serde_json::from_str(s)?;
        require!(!bank.items.is_empty(), "diagnostic_quiz.json has no items");
        Ok(bank)
    }

    /// Items for the requested administration mode. `short` (the default) gives
    /// the first item per category (≈31, full breadth, minimum length);
    /// `extended` gives the whole bank (≈37).
    pub fn items_for_mode(&self, mode: &str) -> Vec<QuizItem> {
        if mode == "extended" {
            return self.items.clone();
        }
        let mut seen = std::collections::HashSet::new();
        self.items
            .iter()
            .filter(|it| seen.insert(it.category.clone()))
            .cloned()
            .collect()
    }
}

impl Collection {
    /// Load the diagnostic bank from an explicit path, or by searching next to
    /// the collection (then the media folder). `None` when not found.
    pub fn load_diagnostic_quiz(&self, explicit_path: Option<&str>) -> Result<Option<QuizBank>> {
        if let Some(path) = explicit_path.filter(|p| !p.is_empty()) {
            let path = std::path::Path::new(path);
            require!(path.exists(), "diagnostic_quiz.json not found at {path:?}");
            let contents = std::fs::read_to_string(path)
                .or_invalid(format!("could not read diagnostic at {}", path.display()))?;
            return Ok(Some(QuizBank::from_json_str(&contents)?));
        }
        for candidate in self.default_quiz_paths() {
            if candidate.exists() {
                let contents = std::fs::read_to_string(&candidate).or_invalid(format!(
                    "could not read diagnostic at {}",
                    candidate.display()
                ))?;
                return Ok(Some(QuizBank::from_json_str(&contents)?));
            }
        }
        Ok(None)
    }

    fn default_quiz_paths(&self) -> Vec<std::path::PathBuf> {
        let mut paths = Vec::new();
        if let Some(dir) = self.col_path.parent() {
            paths.push(dir.join("diagnostic_quiz.json"));
        }
        if !self.media_folder.as_os_str().is_empty() {
            paths.push(self.media_folder.join("diagnostic_quiz.json"));
        }
        paths
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use crate::collection::Collection;

    fn resp(category: &str, difficulty: Difficulty, correct: bool) -> ItemResponse {
        ItemResponse {
            item_id: format!("DQ-{category}"),
            category: category.to_string(),
            difficulty,
            answered: true,
            correct,
        }
    }

    fn by_cat(scores: &[CategoryScore], category: &str) -> CategoryScore {
        scores.iter().find(|s| s.category == category).unwrap().clone()
    }

    /// The README's worked FC1 example (Part 3 → "Worked example (FC1)").
    /// Simple beta-binomial, `mu0 = 0.5`, `kappa = 6`.
    #[test]
    fn worked_example_fc1() {
        // 1A 1/2, 1B 0/2, 1C 2/2, 1D 0/2 (difficulty does not matter here).
        let responses = vec![
            resp("1A", Difficulty::Easy, true),
            resp("1A", Difficulty::Easy, false),
            resp("1B", Difficulty::Easy, false),
            resp("1B", Difficulty::Easy, false),
            resp("1C", Difficulty::Easy, true),
            resp("1C", Difficulty::Easy, true),
            resp("1D", Difficulty::Easy, false),
            resp("1D", Difficulty::Easy, false),
        ];
        let cfg = ScorerConfig::simple_beta_binomial(0.5, 6.0);
        let scores = score_diagnostic(&responses, &cfg);

        // Exact values from the README table.
        let approx = |a: f64, b: f64| (a - b).abs() < 1e-9;
        let a = by_cat(&scores, "1A");
        assert!(approx(a.p_hat, 4.0 / 8.0), "1A p_hat={}", a.p_hat);
        assert!(approx(a.weakness, 0.50));
        assert_eq!(a.band, Band::Partial);

        let b = by_cat(&scores, "1B");
        assert!(approx(b.p_hat, 3.0 / 8.0), "1B p_hat={}", b.p_hat);
        assert!(approx(b.weakness, 0.625));
        assert_eq!(b.band, Band::Gap);

        let c = by_cat(&scores, "1C");
        assert!(approx(c.p_hat, 5.0 / 8.0), "1C p_hat={}", c.p_hat);
        assert!(approx(c.weakness, 0.375));
        assert_eq!(c.band, Band::Partial);

        let d = by_cat(&scores, "1D");
        assert!(approx(d.p_hat, 3.0 / 8.0), "1D p_hat={}", d.p_hat);
        assert!(approx(d.weakness, 0.625));
        assert_eq!(d.band, Band::Gap);

        // README: "even 1B/1D at 0/2 only reach weakness 0.625, not 1.0" — humble.
        assert!(b.weakness < 0.65);
    }

    /// Step 1: a correct hard item is stronger evidence than a correct easy one;
    /// a missed easy item is a stronger gap signal than a missed hard one.
    #[test]
    fn difficulty_aware_evidence_direction() {
        let correct_hard = item_score(true, Difficulty::Hard, true);
        let correct_easy = item_score(true, Difficulty::Easy, true);
        let missed_easy = item_score(false, Difficulty::Easy, true);
        let missed_hard = item_score(false, Difficulty::Hard, true);

        assert!(correct_hard > correct_easy);
        assert!(missed_easy < missed_hard);
        // all stay in range; correct above 0.5, missed below
        assert!(correct_easy > 0.5 && correct_hard <= 1.0);
        assert!(missed_easy >= 0.0 && missed_hard < 0.5);

        // difficulty off => raw correctness
        assert_eq!(item_score(true, Difficulty::Hard, false), 1.0);
        assert_eq!(item_score(false, Difficulty::Easy, false), 0.0);
    }

    /// Step 3: pooling pulls a category with a lucky correct answer *down*
    /// toward a foundational concept the student otherwise bombed.
    #[test]
    fn pooling_pulls_lucky_category_toward_weak_concept() {
        // FC1: 1A 0/2, 1B 0/2, 1D 0/2, but 1C 2/2 (lucky).
        let responses = vec![
            resp("1A", Difficulty::Medium, false),
            resp("1A", Difficulty::Medium, false),
            resp("1B", Difficulty::Medium, false),
            resp("1B", Difficulty::Medium, false),
            resp("1C", Difficulty::Medium, true),
            resp("1C", Difficulty::Medium, true),
            resp("1D", Difficulty::Medium, false),
            resp("1D", Difficulty::Medium, false),
        ];
        let pooled = ScorerConfig {
            pool: true,
            difficulty_aware: false,
            ..ScorerConfig::default()
        };
        let unpooled = ScorerConfig {
            pool: false,
            difficulty_aware: false,
            ..ScorerConfig::default()
        };
        let c_pooled = by_cat(&score_diagnostic(&responses, &pooled), "1C");
        let c_unpooled = by_cat(&score_diagnostic(&responses, &unpooled), "1C");

        // The lucky category looks weaker (lower proficiency) once pooled.
        assert!(
            c_pooled.weakness > c_unpooled.weakness,
            "pooled weakness {} should exceed unpooled {}",
            c_pooled.weakness,
            c_unpooled.weakness
        );
    }

    /// A skipped item is no evidence: the category falls back to the prior.
    #[test]
    fn skipped_item_is_no_evidence() {
        let responses = vec![ItemResponse {
            item_id: "DQ-2A-01".to_string(),
            category: "2A".to_string(),
            difficulty: Difficulty::Medium,
            answered: false,
            correct: false,
        }];
        let cfg = ScorerConfig::simple_beta_binomial(0.5, 6.0);
        let scores = score_diagnostic(&responses, &cfg);
        let s = by_cat(&scores, "2A");
        assert_eq!(s.n, 0);
        assert_eq!(s.k, 0);
        // n = 0 => p_hat == mu0, weakness == 0.5 (a skip never reads as wrong).
        assert!((s.p_hat - 0.5).abs() < 1e-9);
    }

    /// Step 5: the prior dominates with no FSRS data and vanishes as reviews
    /// accrue.
    #[test]
    fn decay_fades_as_reviews_accrue() {
        let prior = 0.9; // diagnostic says "very weak"
        let fsrs = 0.2; // FSRS later says "actually strong"
        let c0 = 8.0;

        // No reviews => pure prior.
        assert!((decayed_weakness(prior, fsrs, 0.0, c0) - prior).abs() < 1e-9);
        // A few reviews => still prior-leaning but moving.
        let early = decayed_weakness(prior, fsrs, 4.0, c0);
        assert!(early > 0.5 && early < prior);
        // Many reviews => essentially FSRS.
        let late = decayed_weakness(prior, fsrs, 400.0, c0);
        assert!((late - fsrs).abs() < 0.02);
        // Monotone toward FSRS.
        assert!(early > late);
    }

    #[test]
    fn band_thresholds() {
        assert_eq!(Band::from_proficiency(0.80), Band::Held);
        assert_eq!(Band::from_proficiency(0.75), Band::Held);
        assert_eq!(Band::from_proficiency(0.50), Band::Partial);
        assert_eq!(Band::from_proficiency(0.40), Band::Partial);
        assert_eq!(Band::from_proficiency(0.39), Band::Gap);
    }

    #[test]
    fn fc_and_section_derivation() {
        assert_eq!(foundational_concept_of("1A"), "1");
        assert_eq!(foundational_concept_of("10A"), "10");
        assert_eq!(section_of_category("1A"), "Bio/Biochem");
        assert_eq!(section_of_category("4B"), "Chem/Phys");
        assert_eq!(section_of_category("10A"), "Psych/Soc");
        assert_eq!(section_of_category("XX"), "");
    }

    #[test]
    fn prior_persists_round_trip() {
        let mut col = Collection::new();
        assert!(col.load_diagnostic_prior().is_none());

        let responses = vec![
            resp("1A", Difficulty::Easy, true),
            resp("1B", Difficulty::Easy, false),
        ];
        let scores = score_diagnostic(&responses, &ScorerConfig::default());
        let prior = DiagnosticPrior::from_scores("short", DEFAULT_DECAY_PSEUDOCOUNT, &scores);
        col.save_diagnostic_prior(&prior).unwrap();

        let loaded = col.load_diagnostic_prior().unwrap();
        assert_eq!(loaded.mode, "short");
        assert_eq!(loaded.schema_version, DIAGNOSTIC_PRIOR_SCHEMA);
        assert!(loaded.weakness_for("1A").is_some());

        col.clear_diagnostic_prior().unwrap();
        assert!(col.load_diagnostic_prior().is_none());
        // clearing again is a safe no-op
        col.clear_diagnostic_prior().unwrap();
    }

    #[test]
    fn quiz_mode_selection() {
        let bank = QuizBank::from_json_str(
            r#"{
              "quiz_id": "t", "title": "T", "description": "d",
              "items": [
                {"id":"DQ-1A-01","category":"1A","difficulty":"easy","stem":"s",
                 "options":[{"key":"A","text":"a"}],"answer":"A"},
                {"id":"DQ-1A-02","category":"1A","difficulty":"hard","stem":"s",
                 "options":[{"key":"A","text":"a"}],"answer":"A"},
                {"id":"DQ-2A-01","category":"2A","difficulty":"medium","stem":"s",
                 "options":[{"key":"A","text":"a"}],"answer":"A"}
              ]
            }"#,
        )
        .unwrap();
        // short => one item per category (first-seen)
        let short = bank.items_for_mode("short");
        assert_eq!(short.len(), 2);
        assert_eq!(short[0].id, "DQ-1A-01");
        assert_eq!(short[1].id, "DQ-2A-01");
        // extended => all items
        assert_eq!(bank.items_for_mode("extended").len(), 3);
    }
}
