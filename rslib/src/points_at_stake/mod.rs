// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! ReadyMCAT points-at-stake queue and honest-memory aggregation.
//!
//! This is a fork-specific extension to Anki's scheduler. Anki reasons about
//! one card at a time and has no concept of a *topic*, of *exam value*, or of
//! aggregating memory across the cards that make up a concept. This module adds
//! exactly that:
//!
//! * [`Taxonomy`] maps a card's tags/subdeck onto an AAMC content category and
//!   gives each category a `topic_weight` (its share of the real MCAT).
//! * [`Aggregation`] aggregates each card's FSRS recall probability per topic
//!   to produce `student_weakness = 1 - mean_recall`, an honest (ranged)
//!   overall memory score, and an outline-coverage map.
//! * The points-at-stake order ranks due cards by `points_at_stake =
//!   topic_weight * student_weakness`, surfacing the highest-yield,
//!   weakest-topic cards first.
//!
//! The same computation backs both the live study queue (via the
//! [`ReviewCardOrder::PointsAtStake`](crate::deckconfig::ReviewCardOrder)
//! variant) and the `PointsAtStakeService` protobuf API consumed by the desktop
//! dashboard and, later, iOS.

pub mod bench;
pub mod service;

use std::collections::BTreeMap;
use std::collections::HashSet;
use std::path::Path;
use std::path::PathBuf;

use serde::Deserialize;

use crate::prelude::*;

/// Minimum number of graded reviews before the dashboard may show a score.
pub const GIVE_UP_MIN_REVIEWS: u32 = 200;
/// Minimum fraction of AAMC categories that must be covered before the
/// dashboard may show a score.
pub const GIVE_UP_MIN_COVERAGE: f64 = 0.5;

/// Tag the desktop reviewer adds to a note whose teach-on-miss correction was
/// missed again (see `qt/aqt/reviewer.py`). The points-at-stake queue raises
/// such a card's priority so the corrected concept resurfaces soon and again
/// later — the spaced re-retrieval teach-on-miss relies on. See
/// `readymcat/README.md` (§ "Teach-on-miss ↔ points-at-stake handshake").
pub const STRUGGLING_TAG: &str = "ReadyMCAT::struggling";
/// Multiplier applied to the points at stake of a `STRUGGLING_TAG` card. Kept
/// deliberately simple: a struggling card outranks its non-struggling peers in
/// the same topic (and topics up to this factor more valuable). The honest
/// memory/weakness aggregation is left untouched, so the dashboard's scores
/// stay honest; only the live queue/ranking priority is boosted.
pub const STRUGGLING_PRIORITY_BOOST: f64 = 2.0;

/// A single AAMC content category, e.g. "1A".
#[derive(Debug, Clone, Deserialize)]
pub struct AamcCategory {
    pub name: String,
    /// Percentage of the exam this category represents, per AAMC's published
    /// content distribution.
    pub weight: f64,
}

/// Resolves a deck tag or subdeck (glob or prefix) onto an AAMC category.
#[derive(Debug, Clone, Deserialize)]
pub struct TaxonomyMapping {
    pub deck_tag_or_subdeck: String,
    pub category: String,
}

/// The shared `taxonomy.json` artifact: deck tags/subdecks -> AAMC categories +
/// weights. Authored by the deck workstream; a stub lives at the repo root.
#[derive(Debug, Clone, Deserialize)]
pub struct Taxonomy {
    #[serde(default)]
    pub version: u32,
    pub aamc_categories: BTreeMap<String, AamcCategory>,
    #[serde(default)]
    pub mappings: Vec<TaxonomyMapping>,
}

impl Taxonomy {
    pub fn from_json_str(s: &str) -> Result<Self> {
        let tax: Taxonomy = serde_json::from_str(s)?;
        require!(
            !tax.aamc_categories.is_empty(),
            "taxonomy.json must define at least one AAMC category"
        );
        Ok(tax)
    }

    pub fn from_path(path: &Path) -> Result<Self> {
        let contents = std::fs::read_to_string(path)
            .or_invalid(format!("could not read taxonomy at {}", path.display()))?;
        Self::from_json_str(&contents)
    }

    /// Resolve a card to an AAMC category. This mirrors the reference resolver
    /// in `readymcat/tools/build_taxonomy.py::resolve_category`:
    ///
    /// * A mapping whose `deck_tag_or_subdeck` starts with `#` is a **tag**
    ///   mapping, matched against the card's tags; any other mapping is a
    ///   **subdeck** mapping, matched against the card's deck name.
    /// * Tag mappings win over subdeck mappings.
    /// * Within each kind the longest (most specific) `::`-path-prefix wins.
    ///
    /// `None` when the card maps to no topic.
    pub fn category_for(&self, tags: &[&str], deck_name: &str) -> Option<&str> {
        let mut best_tag: Option<&TaxonomyMapping> = None;
        let mut best_deck: Option<&TaxonomyMapping> = None;
        for mapping in &self.mappings {
            let prefix = mapping.deck_tag_or_subdeck.as_str();
            if prefix.starts_with('#') {
                if tags.iter().any(|tag| is_path_prefix(prefix, tag)) && longer(prefix, best_tag) {
                    best_tag = Some(mapping);
                }
            } else if is_path_prefix(prefix, deck_name) && longer(prefix, best_deck) {
                best_deck = Some(mapping);
            }
        }
        best_tag.or(best_deck).map(|m| m.category.as_str())
    }

    fn total_weight(&self) -> f64 {
        self.aamc_categories.values().map(|c| c.weight).sum()
    }
}

/// True if `prefix` matches `value` on `::` path boundaries: either `value`
/// equals `prefix`, or `value` begins with `prefix` followed by `::` (so
/// `Biochem` matches `Biochem::Enzymes` but not `Biochemistry`). Case-sensitive
/// and allocation-free; mirrors `build_taxonomy.py::is_path_prefix`.
fn is_path_prefix(prefix: &str, value: &str) -> bool {
    value == prefix
        || value
            .strip_prefix(prefix)
            .is_some_and(|rest| rest.starts_with("::"))
}

/// Whether `prefix` should replace the current `best` mapping: true when there
/// is no best yet, or `prefix` is strictly longer (more specific). Strict `>`
/// keeps the first match on ties, mirroring `resolve_category`.
fn longer(prefix: &str, best: Option<&TaxonomyMapping>) -> bool {
    match best {
        Some(b) => prefix.chars().count() > b.deck_tag_or_subdeck.chars().count(),
        None => true,
    }
}

/// Per-topic accumulator.
#[derive(Debug, Clone)]
pub struct TopicAcc {
    pub name: String,
    pub weight: f64,
    /// Whether this category is part of the AAMC outline (vs. an orphan
    /// mapping).
    pub in_outline: bool,
    pub total_cards: u32,
    pub graded_cards: u32,
    pub sum_recall: f64,
}

impl TopicAcc {
    pub fn mean_recall(&self) -> f64 {
        if self.graded_cards > 0 {
            self.sum_recall / self.graded_cards as f64
        } else {
            0.0
        }
    }

    /// 1 - mean recall. An unstudied topic (no graded cards) is treated as
    /// fully weak, so high-weight unstudied topics rank first.
    pub fn weakness(&self) -> f64 {
        if self.graded_cards > 0 {
            1.0 - self.mean_recall()
        } else {
            1.0
        }
    }
}

/// The result of one pass over the collection: per-topic aggregation plus the
/// inputs for the honest memory score, coverage map and give-up rule.
#[derive(Debug, Clone)]
pub struct Aggregation {
    pub topics: BTreeMap<String, TopicAcc>,
    mem_n: u32,
    mem_sum: f64,
    mem_sum_sq: f64,
    pub graded_reviews: u32,
    total_outline_weight: f64,
}

impl Aggregation {
    fn new(tax: &Taxonomy) -> Self {
        let topics = tax
            .aamc_categories
            .iter()
            .map(|(id, cat)| {
                (
                    id.clone(),
                    TopicAcc {
                        name: cat.name.clone(),
                        weight: cat.weight,
                        in_outline: true,
                        total_cards: 0,
                        graded_cards: 0,
                        sum_recall: 0.0,
                    },
                )
            })
            .collect();
        Aggregation {
            topics,
            mem_n: 0,
            mem_sum: 0.0,
            mem_sum_sq: 0.0,
            graded_reviews: 0,
            total_outline_weight: tax.total_weight(),
        }
    }

    /// Record a card belonging to `category` (None = unmapped) with an optional
    /// recall probability (None = no FSRS memory state yet).
    fn record(&mut self, category: Option<&str>, recall: Option<f64>) {
        let Some(category) = category else {
            return;
        };
        let acc = self
            .topics
            .entry(category.to_string())
            .or_insert_with(|| TopicAcc {
                name: category.to_string(),
                weight: 0.0,
                in_outline: false,
                total_cards: 0,
                graded_cards: 0,
                sum_recall: 0.0,
            });
        acc.total_cards += 1;
        if let Some(recall) = recall {
            acc.graded_cards += 1;
            acc.sum_recall += recall;
            if acc.in_outline {
                self.mem_n += 1;
                self.mem_sum += recall;
                self.mem_sum_sq += recall * recall;
            }
        }
    }

    /// `(topic_weight, student_weakness)` for the given category.
    pub fn weight_and_weakness(&self, category: Option<&str>) -> (f64, f64) {
        match category.and_then(|c| self.topics.get(c)) {
            Some(topic) => (topic.weight, topic.weakness()),
            None => (0.0, 0.0),
        }
    }

    /// Number of cards in the category with an FSRS memory state. This is the
    /// per-category evidence count behind the FSRS weakness estimate, used as
    /// the precision weight `w_fsrs` in the diagnostic-prior decay (README
    /// Step 5): more reviewed cards => the FSRS estimate dominates the prior.
    pub fn graded_cards(&self, category: Option<&str>) -> u32 {
        category
            .and_then(|c| self.topics.get(c))
            .map(|t| t.graded_cards)
            .unwrap_or(0)
    }

    /// `points_at_stake = topic_weight * student_weakness`.
    pub fn points(&self, category: Option<&str>) -> f64 {
        let (weight, weakness) = self.weight_and_weakness(category);
        weight * weakness
    }

    /// Honest overall memory: the mean recall across graded outline cards, with
    /// a 95% interval. Never a bare number.
    pub fn memory_report(&self) -> MemoryReport {
        let n = self.mem_n;
        let mean = if n > 0 { self.mem_sum / n as f64 } else { 0.0 };
        let (low, high) = if n >= 2 {
            let variance = ((self.mem_sum_sq - self.mem_sum * self.mem_sum / n as f64)
                / (n as f64 - 1.0))
                .max(0.0);
            let std_err = (variance / n as f64).sqrt();
            let half = 1.96 * std_err;
            ((mean - half).clamp(0.0, 1.0), (mean + half).clamp(0.0, 1.0))
        } else {
            (mean, mean)
        };
        MemoryReport {
            mean,
            range_low: low,
            range_high: high,
            graded_reviews: self.graded_reviews,
            graded_cards: n,
        }
    }

    /// How much of the AAMC outline the deck covers.
    pub fn coverage_report(&self) -> CoverageReport {
        let outline = || self.topics.values().filter(|t| t.in_outline);
        let total = outline().count() as u32;
        let covered = outline().filter(|t| t.total_cards > 0).count() as u32;
        let weight_covered: f64 = outline()
            .filter(|t| t.total_cards > 0)
            .map(|t| t.weight)
            .sum();
        CoverageReport {
            categories_total: total,
            categories_covered: covered,
            fraction: if total > 0 {
                covered as f64 / total as f64
            } else {
                0.0
            },
            weighted_fraction: if self.total_outline_weight > 0.0 {
                weight_covered / self.total_outline_weight
            } else {
                0.0
            },
        }
    }

    /// The give-up rule: enough evidence to show a score?
    pub fn meets_data_threshold(&self) -> bool {
        self.graded_reviews >= GIVE_UP_MIN_REVIEWS
            && self.coverage_report().fraction >= GIVE_UP_MIN_COVERAGE
    }
}

#[derive(Debug, Clone, Copy)]
pub struct MemoryReport {
    pub mean: f64,
    pub range_low: f64,
    pub range_high: f64,
    pub graded_reviews: u32,
    pub graded_cards: u32,
}

#[derive(Debug, Clone, Copy)]
pub struct CoverageReport {
    pub categories_total: u32,
    pub categories_covered: u32,
    pub fraction: f64,
    pub weighted_fraction: f64,
}

/// A due review card with its computed points at stake.
#[derive(Debug, Clone)]
pub struct RankedCard {
    pub card_id: CardId,
    pub category: Option<String>,
    pub topic_weight: f64,
    /// The weakness actually used for ranking: the precision-weighted blend of
    /// the diagnostic prior and the FSRS weakness (see
    /// [`crate::diagnostic::decayed_weakness`]). Equal to
    /// [`Self::fsrs_weakness`] when no diagnostic prior covers the
    /// category, so `points_at_stake == topic_weight * student_weakness`
    /// for non-struggling cards in every case.
    pub student_weakness: f64,
    /// The honest, FSRS-only weakness (`1 - mean recall`). This is what the
    /// dashboard shows; the diagnostic prior never changes it.
    pub fsrs_weakness: f64,
    /// The diagnostic prior's weakness seed for this category (equals
    /// [`Self::fsrs_weakness`] when no prior applies). Exposed so ordering is
    /// explainable.
    pub prior_weakness: f64,
    /// Whether a diagnostic prior contributed to [`Self::student_weakness`].
    pub seeded_by_prior: bool,
    /// `topic_weight * student_weakness`, multiplied by
    /// [`STRUGGLING_PRIORITY_BOOST`] when `struggling` is set.
    pub points_at_stake: f64,
    /// The card carries [`STRUGGLING_TAG`] (a teach-on-miss correction that was
    /// missed again), so its priority was boosted.
    pub struggling: bool,
    pub due: i32,
}

impl Collection {
    /// Load the taxonomy from an explicit path, or by searching next to the
    /// collection. Returns `None` when no taxonomy can be found.
    pub fn load_taxonomy(&self, explicit_path: Option<&str>) -> Result<Option<Taxonomy>> {
        if let Some(path) = explicit_path.filter(|p| !p.is_empty()) {
            let path = Path::new(path);
            require!(path.exists(), "taxonomy.json not found at {path:?}");
            return Ok(Some(Taxonomy::from_path(path)?));
        }
        for candidate in self.default_taxonomy_paths() {
            if candidate.exists() {
                return Ok(Some(Taxonomy::from_path(&candidate)?));
            }
        }
        Ok(None)
    }

    fn default_taxonomy_paths(&self) -> Vec<PathBuf> {
        let mut paths = Vec::new();
        if let Some(dir) = self.col_path.parent() {
            paths.push(dir.join("taxonomy.json"));
        }
        if !self.media_folder.as_os_str().is_empty() {
            paths.push(self.media_folder.join("taxonomy.json"));
        }
        paths
    }

    /// One pass over the whole collection, aggregating FSRS recall per topic.
    pub fn compute_topic_aggregation(&mut self, tax: &Taxonomy) -> Result<Aggregation> {
        let timing = self.timing_today()?;
        let deck_names = self.deck_name_map()?;
        let mut agg = Aggregation::new(tax);

        let mut stmt = self.storage.db.prepare_cached(
            "SELECT c.did, n.tags,
               extract_fsrs_retrievability(
                 c.data,
                 CASE WHEN c.odue != 0 THEN c.odue ELSE c.due END,
                 c.ivl, ?1, ?2, ?3)
             FROM cards c JOIN notes n ON c.nid = n.id",
        )?;
        let mut rows = stmt.query(rusqlite::params![
            timing.days_elapsed,
            timing.next_day_at.0,
            timing.now.0
        ])?;
        while let Some(row) = rows.next()? {
            let did: DeckId = DeckId(row.get(0)?);
            let tags: String = row.get(1)?;
            let recall: Option<f64> = row.get(2)?;
            let tag_refs: Vec<&str> = tags.split_whitespace().collect();
            let deck_name = deck_names.get(&did).map(String::as_str).unwrap_or("");
            let category = tax.category_for(&tag_refs, deck_name);
            agg.record(category, recall);
        }
        drop(rows);
        drop(stmt);

        agg.graded_reviews = self.graded_review_count()?;
        Ok(agg)
    }

    /// Rank due review cards by points at stake (highest first). `deck_filter`,
    /// when set, restricts to cards whose deck is in the set.
    pub fn rank_due_cards(
        &mut self,
        tax: &Taxonomy,
        agg: &Aggregation,
        deck_filter: Option<&HashSet<DeckId>>,
    ) -> Result<Vec<RankedCard>> {
        let timing = self.timing_today()?;
        let deck_names = self.deck_name_map()?;

        // ReadyMCAT LEARN MODE: seed weakness from the first-launch diagnostic
        // prior so session-one ordering is useful before FSRS has data. The
        // prior touches ORDERING ONLY (never the dashboard's honest aggregation)
        // and decays as reviews accrue (README Step 5). Absent => no effect.
        let prior = self.load_diagnostic_prior();
        let decay_c0 = prior
            .as_ref()
            .map(|p| p.decay_pseudocount())
            .unwrap_or(crate::diagnostic::DEFAULT_DECAY_PSEUDOCOUNT);

        let mut ranked = Vec::new();
        let mut stmt = self.storage.db.prepare_cached(
            "SELECT c.id, c.did, c.due, n.tags
             FROM cards c JOIN notes n ON c.nid = n.id
             WHERE c.queue = 2 AND c.due <= ?1",
        )?;
        let mut rows = stmt.query(rusqlite::params![timing.days_elapsed])?;
        while let Some(row) = rows.next()? {
            let card_id: CardId = CardId(row.get(0)?);
            let did: DeckId = DeckId(row.get(1)?);
            if let Some(filter) = deck_filter {
                if !filter.contains(&did) {
                    continue;
                }
            }
            let due: i32 = row.get(2)?;
            let tags: String = row.get(3)?;
            let tag_refs: Vec<&str> = tags.split_whitespace().collect();
            let deck_name = deck_names.get(&did).map(String::as_str).unwrap_or("");
            let category = tax.category_for(&tag_refs, deck_name);
            let (weight, fsrs_weakness) = agg.weight_and_weakness(category);

            // Blend the diagnostic prior in by precision, if it covers this
            // category. `w_fsrs` is the category's reviewed-card count, so the
            // prior fades as real reviews accumulate.
            let prior_seed = prior
                .as_ref()
                .zip(category)
                .and_then(|(p, c)| p.weakness_for(c));
            let (student_weakness, prior_weakness, seeded_by_prior) = match prior_seed {
                Some(pw) => {
                    let w_fsrs = agg.graded_cards(category) as f64;
                    let blended =
                        crate::diagnostic::decayed_weakness(pw, fsrs_weakness, w_fsrs, decay_c0);
                    (blended, pw, true)
                }
                None => (fsrs_weakness, fsrs_weakness, false),
            };

            // Seam: a corrected-but-still-struggling concept (tagged by the
            // teach-on-miss reviewer) gets a priority boost so it resurfaces.
            let struggling = tag_refs
                .iter()
                .any(|tag| is_path_prefix(STRUGGLING_TAG, tag));
            let base = weight * student_weakness;
            let points_at_stake = if struggling {
                base * STRUGGLING_PRIORITY_BOOST
            } else {
                base
            };
            ranked.push(RankedCard {
                card_id,
                category: category.map(str::to_string),
                topic_weight: weight,
                student_weakness,
                fsrs_weakness,
                prior_weakness,
                seeded_by_prior,
                points_at_stake,
                struggling,
                due,
            });
        }
        drop(rows);
        drop(stmt);

        sort_ranked(&mut ranked);
        Ok(ranked)
    }

    fn deck_name_map(&self) -> Result<std::collections::HashMap<DeckId, String>> {
        Ok(self
            .storage
            .get_decks_map()?
            .into_iter()
            .map(|(id, deck)| (id, deck.human_name()))
            .collect())
    }

    fn graded_review_count(&self) -> Result<u32> {
        let count: i64 =
            self.storage
                .db
                .query_row("SELECT count() FROM revlog WHERE ease >= 1", [], |r| {
                    r.get(0)
                })?;
        Ok(count as u32)
    }

    /// Resolve a deck id to the set of its own + descendant deck ids.
    pub(crate) fn deck_subtree_ids(&mut self, deck_id: DeckId) -> Result<HashSet<DeckId>> {
        let deck = self.storage.get_deck(deck_id)?.or_not_found(deck_id)?;
        let mut ids: HashSet<DeckId> = self
            .storage
            .child_decks(&deck)?
            .iter()
            .map(|d| d.id)
            .collect();
        ids.insert(deck.id);
        Ok(ids)
    }
}

/// Sort by points at stake desc, then most-overdue first, then card id.
pub(crate) fn sort_ranked(ranked: &mut [RankedCard]) {
    ranked.sort_by(|a, b| {
        b.points_at_stake
            .partial_cmp(&a.points_at_stake)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.due.cmp(&b.due))
            .then(a.card_id.cmp(&b.card_id))
    });
}

#[cfg(test)]
mod test {
    use super::*;
    use crate::card::CardType;
    use crate::collection::Collection;

    // Mirrors the real taxonomy.json shape: a `#`-prefixed key is a TAG mapping
    // (matched against a card's tags); any other key is a SUBDECK mapping
    // (matched against the card's deck name). Tags win over subdecks; within a
    // kind the longest `::`-path-prefix wins.
    // NB: `r##"…"##` (not `r#"…"#`) because the tag mappings contain the byte
    // sequence `"#` (e.g. `"#Physiology`), which would otherwise close a `r#`
    // raw string early.
    const TAXONOMY: &str = r##"{
        "version": 1,
        "aamc_categories": {
            "1A": {"name": "Biomolecules", "weight": 5.0},
            "1B": {"name": "Cellular", "weight": 10.0},
            "2B": {"name": "Microbes", "weight": 2.0},
            "3A": {"name": "Behavior", "weight": 1.0}
        },
        "mappings": [
            {"deck_tag_or_subdeck": "#Physiology::Cells", "category": "1B"},
            {"deck_tag_or_subdeck": "#Physiology::Cells::Viruses", "category": "2B"},
            {"deck_tag_or_subdeck": "MCAT::Biochemistry", "category": "1A"},
            {"deck_tag_or_subdeck": "MCAT::Psychology::Behavior", "category": "3A"}
        ]
    }"##;

    fn taxonomy() -> Taxonomy {
        Taxonomy::from_json_str(TAXONOMY).unwrap()
    }

    /// Add a review card in `deck_name` (created if needed) carrying `tags`,
    /// with the given FSRS stability and days since the last review (which
    /// set its recall probability). Returns its id.
    fn add_card(
        col: &mut Collection,
        deck_name: &str,
        tags: &[&str],
        stability: f32,
        days_since_review: i64,
    ) -> CardId {
        let deck_id = col.get_or_create_normal_deck(deck_name).unwrap().id;
        let nt = col.get_notetype_by_name("Basic").unwrap().unwrap();
        let mut note = nt.new_note();
        note.set_field(0, "q").unwrap();
        if !tags.is_empty() {
            note.tags = tags.iter().map(|t| t.to_string()).collect();
        }
        col.add_note(&mut note, deck_id).unwrap();
        let mut card = col
            .storage
            .get_card_by_ordinal(note.id, 0)
            .unwrap()
            .unwrap();
        let card_id = card.id;
        card.ctype = CardType::Review;
        card.queue = crate::card::CardQueue::Review;
        card.due = -1;
        card.interval = 10;
        card.memory_state = Some(crate::card::FsrsMemoryState {
            stability,
            difficulty: 5.0,
        });
        card.last_review_time = Some(TimestampSecs::now().adding_secs(-days_since_review * 86_400));
        col.update_cards_maybe_undoable(vec![card], false).unwrap();
        card_id
    }

    #[test]
    fn path_prefix_matching() {
        // exact + `::` hierarchy prefix
        assert!(is_path_prefix("Biochem", "Biochem"));
        assert!(is_path_prefix("Biochem", "Biochem::Enzymes"));
        // path boundary only: not a bare substring/sibling
        assert!(!is_path_prefix("Biochem", "Biochemistry"));
        assert!(!is_path_prefix("Physiology::Cells", "Physiology::CellsX"));
        // a longer prefix is not matched by a shorter value
        assert!(!is_path_prefix("Biochem::Enzymes", "Biochem"));
    }

    #[test]
    fn resolution_tag_over_subdeck_longest_prefix() {
        let tax = taxonomy();
        // subdeck resolves when there is no tag match
        assert_eq!(
            tax.category_for(&[], "MCAT::Biochemistry::Enzymes"),
            Some("1A")
        );
        // a tag match wins over a subdeck match
        assert_eq!(
            tax.category_for(&["#Physiology::Cells"], "MCAT::Biochemistry::Enzymes"),
            Some("1B")
        );
        // longest (most specific) tag prefix wins
        assert_eq!(
            tax.category_for(&["#Physiology::Cells::Viruses::HIV"], "MCAT::Biochemistry"),
            Some("2B")
        );
        // path-prefix, not substring: a sibling tag does not match
        assert_eq!(tax.category_for(&["#Physiology::CellsX"], "Other"), None);
        // untagged & unknown deck -> no topic
        assert_eq!(tax.category_for(&["unrelated"], "Other::Deck"), None);
        assert_eq!(tax.category_for(&[], ""), None);
    }

    #[test]
    fn per_topic_weakness_aggregation() {
        let mut col = Collection::new();
        let tax = taxonomy();
        // 1A (Biochemistry subdeck): well-remembered -> low weakness
        add_card(&mut col, "MCAT::Biochemistry::Enzymes", &[], 1000.0, 1);
        add_card(&mut col, "MCAT::Biochemistry", &[], 1000.0, 1);
        // 1B (Cells tag): poorly remembered -> high weakness
        add_card(&mut col, "Default", &["#Physiology::Cells"], 0.5, 60);

        let agg = col.compute_topic_aggregation(&tax).unwrap();
        let bio = agg.topics.get("1A").unwrap();
        let cell = agg.topics.get("1B").unwrap();
        let behavior = agg.topics.get("3A").unwrap();

        assert_eq!(bio.total_cards, 2);
        assert_eq!(bio.graded_cards, 2);
        assert_eq!(cell.total_cards, 1);
        // remembered topic is much stronger than the forgotten one
        assert!(bio.mean_recall() > 0.9, "bio recall {}", bio.mean_recall());
        assert!(
            cell.mean_recall() < 0.5,
            "cell recall {}",
            cell.mean_recall()
        );
        assert!(cell.weakness() > bio.weakness());
        // an outline topic with no cards is treated as fully weak
        assert_eq!(behavior.total_cards, 0);
        assert_eq!(behavior.weakness(), 1.0);

        // coverage: 2 of 4 outline categories have cards
        let coverage = agg.coverage_report();
        assert_eq!(coverage.categories_total, 4);
        assert_eq!(coverage.categories_covered, 2);

        // memory score is a real interval over graded cards
        let mem = agg.memory_report();
        assert_eq!(mem.graded_cards, 3);
        assert!(mem.range_low <= mem.mean && mem.mean <= mem.range_high);
    }

    #[test]
    fn ranking_orders_by_points_at_stake() {
        let mut col = Collection::new();
        let tax = taxonomy();
        // 1A weight 5, strongly remembered -> small but non-zero points
        let strong = add_card(&mut col, "MCAT::Biochemistry", &[], 1000.0, 1);
        // 1B weight 10, badly forgotten -> highest points
        let weak = add_card(&mut col, "Default", &["#Physiology::Cells"], 0.4, 90);
        // untagged, unknown deck -> zero points, ranks last
        let untagged = add_card(&mut col, "Default", &[], 0.4, 90);

        let agg = col.compute_topic_aggregation(&tax).unwrap();
        let ranked = col.rank_due_cards(&tax, &agg, None).unwrap();
        let order: Vec<CardId> = ranked.iter().map(|r| r.card_id).collect();

        assert_eq!(order, vec![weak, strong, untagged]);
        // the weakest, highest-yield topic has the most points at stake
        assert!(ranked[0].points_at_stake > ranked[1].points_at_stake);
        assert!(ranked[1].points_at_stake > ranked[2].points_at_stake);
        // untagged card carries no topic and no points
        assert_eq!(ranked[2].category, None);
        assert_eq!(ranked[2].points_at_stake, 0.0);
        assert!(!ranked.iter().any(|r| r.struggling));
    }

    #[test]
    fn struggling_tag_boosts_priority() {
        let mut col = Collection::new();
        let tax = taxonomy();
        // Two cards in the SAME topic (1B) => identical base points. The one
        // flagged ReadyMCAT::struggling must rank first with ~2x the points.
        let normal = add_card(&mut col, "Default", &["#Physiology::Cells"], 0.6, 30);
        let struggling = add_card(
            &mut col,
            "Default",
            &["#Physiology::Cells", STRUGGLING_TAG],
            0.6,
            30,
        );

        let agg = col.compute_topic_aggregation(&tax).unwrap();
        let ranked = col.rank_due_cards(&tax, &agg, None).unwrap();
        let find = |id: CardId| ranked.iter().find(|r| r.card_id == id).unwrap();
        let s = find(struggling);
        let n = find(normal);

        assert!(s.struggling);
        assert!(!n.struggling);
        // same topic => identical weight & weakness; only the priority differs
        assert_eq!(s.topic_weight, n.topic_weight);
        assert_eq!(s.student_weakness, n.student_weakness);
        assert!((s.points_at_stake - n.points_at_stake * STRUGGLING_PRIORITY_BOOST).abs() < 1e-9);
        assert!(s.points_at_stake > n.points_at_stake);
        // the struggling card resurfaces first
        assert_eq!(ranked.first().unwrap().card_id, struggling);
    }

    #[test]
    fn empty_collection_and_missing_topics() {
        let mut col = Collection::new();
        let tax = taxonomy();
        let agg = col.compute_topic_aggregation(&tax).unwrap();
        // no cards: every outline topic is fully weak, nothing covered
        assert_eq!(agg.coverage_report().categories_covered, 0);
        assert_eq!(agg.memory_report().graded_cards, 0);
        assert!(!agg.meets_data_threshold());
        let ranked = col.rank_due_cards(&tax, &agg, None).unwrap();
        assert!(ranked.is_empty());
    }

    /// GUARDRAIL (honesty rule): the first-launch diagnostic prior influences
    /// card ORDERING only. It must never move the dashboard's honest numbers
    /// (per-topic weakness/mastery, coverage, the ranged memory score), which
    /// are computed purely from FSRS state.
    #[test]
    fn diagnostic_prior_seeds_ordering_not_dashboard() {
        use std::collections::BTreeMap;

        use crate::diagnostic::CategoryPrior;
        use crate::diagnostic::DiagnosticPrior;
        use crate::diagnostic::DEFAULT_DECAY_PSEUDOCOUNT;

        let mut col = Collection::new();
        // Two equally-weighted topics, so the prior alone can decide the order.
        let tax = Taxonomy::from_json_str(
            r##"{
                "version": 1,
                "aamc_categories": {
                    "1A": {"name": "Biomolecules", "weight": 5.0},
                    "3A": {"name": "Behavior", "weight": 5.0}
                },
                "mappings": [
                    {"deck_tag_or_subdeck": "MCAT::Biochemistry", "category": "1A"},
                    {"deck_tag_or_subdeck": "MCAT::Psychology::Behavior", "category": "3A"}
                ]
            }"##,
        )
        .unwrap();
        // 1A strongly remembered (low FSRS weakness); 3A badly forgotten (high).
        let card_1a = add_card(&mut col, "MCAT::Biochemistry", &[], 1000.0, 1);
        let card_3a = add_card(&mut col, "MCAT::Psychology::Behavior", &[], 0.3, 120);

        // Baseline (no diagnostic prior): FSRS-only ordering + honest numbers.
        let agg_before = col.compute_topic_aggregation(&tax).unwrap();
        let mem_before = agg_before.memory_report();
        let cov_before = agg_before.coverage_report();
        let weak_1a = agg_before.weight_and_weakness(Some("1A")).1;
        let weak_3a = agg_before.weight_and_weakness(Some("3A")).1;
        let ranked_before = col.rank_due_cards(&tax, &agg_before, None).unwrap();
        // The forgotten topic leads when only FSRS speaks.
        assert_eq!(ranked_before.first().unwrap().card_id, card_3a);
        assert!(ranked_before.iter().all(|r| !r.seeded_by_prior));

        // Seed a prior that says the OPPOSITE: 1A weak, 3A strong.
        let mut categories = BTreeMap::new();
        categories.insert(
            "1A".to_string(),
            CategoryPrior {
                n: 2,
                k: 0,
                p_hat: 0.1,
                weakness: 0.9,
                band: "gap".to_string(),
            },
        );
        categories.insert(
            "3A".to_string(),
            CategoryPrior {
                n: 2,
                k: 2,
                p_hat: 0.9,
                weakness: 0.1,
                band: "held".to_string(),
            },
        );
        let prior = DiagnosticPrior {
            schema_version: 1,
            mode: "short".to_string(),
            taken_at: 0,
            decay_pseudocount: DEFAULT_DECAY_PSEUDOCOUNT,
            categories,
        };
        col.save_diagnostic_prior(&prior).unwrap();

        // GUARDRAIL: the honest aggregation is byte-for-byte unchanged.
        let agg_after = col.compute_topic_aggregation(&tax).unwrap();
        let mem_after = agg_after.memory_report();
        let cov_after = agg_after.coverage_report();
        assert_eq!(mem_before.mean, mem_after.mean);
        assert_eq!(mem_before.range_low, mem_after.range_low);
        assert_eq!(mem_before.range_high, mem_after.range_high);
        assert_eq!(mem_before.graded_cards, mem_after.graded_cards);
        assert_eq!(cov_before.categories_covered, cov_after.categories_covered);
        assert_eq!(weak_1a, agg_after.weight_and_weakness(Some("1A")).1);
        assert_eq!(weak_3a, agg_after.weight_and_weakness(Some("3A")).1);

        // But ORDERING is now seeded by the prior: the diagnostic-weak 1A leads.
        let ranked_after = col.rank_due_cards(&tax, &agg_after, None).unwrap();
        assert_eq!(ranked_after.first().unwrap().card_id, card_1a);

        let r1 = ranked_after
            .iter()
            .find(|r| r.card_id == card_1a)
            .unwrap()
            .clone();
        assert!(r1.seeded_by_prior);
        // The ranked card still reports the HONEST FSRS weakness (== dashboard)...
        assert_eq!(r1.fsrs_weakness, weak_1a);
        // ...while the weakness actually used for ordering was pulled up by the
        // prior, and points_at_stake tracks that effective weakness.
        assert!(r1.student_weakness > r1.fsrs_weakness);
        assert!((r1.prior_weakness - 0.9).abs() < 1e-9);
        assert!((r1.points_at_stake - r1.topic_weight * r1.student_weakness).abs() < 1e-9);
    }
}
