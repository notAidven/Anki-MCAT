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

    /// The first category whose mapping matches any of the card's tags or its
    /// subdeck. `None` when the card maps to no topic.
    pub fn category_for(&self, tags: &[&str], deck_name: &str) -> Option<&str> {
        for mapping in &self.mappings {
            let pattern = &mapping.deck_tag_or_subdeck;
            let matches = tags.iter().any(|tag| pattern_matches(pattern, tag))
                || pattern_matches(pattern, deck_name);
            if matches {
                return Some(&mapping.category);
            }
        }
        None
    }

    fn total_weight(&self) -> f64 {
        self.aamc_categories.values().map(|c| c.weight).sum()
    }
}

/// True if `pattern` (a glob with `*`/`?`, or a plain tag/subdeck prefix)
/// matches `value`. Matching is case-insensitive. A plain pattern matches the
/// value exactly or as a `::` hierarchy prefix (so `Biochem` matches
/// `Biochem::Enzymes`).
fn pattern_matches(pattern: &str, value: &str) -> bool {
    let pattern = pattern.to_lowercase();
    let value = value.to_lowercase();
    if pattern.contains('*') || pattern.contains('?') {
        glob_match(&pattern, &value)
    } else {
        value == pattern || value.starts_with(&format!("{pattern}::"))
    }
}

/// Classic linear-time wildcard matcher supporting `*` and `?`.
fn glob_match(pattern: &str, text: &str) -> bool {
    let p: Vec<char> = pattern.chars().collect();
    let t: Vec<char> = text.chars().collect();
    let (mut pi, mut ti) = (0usize, 0usize);
    let mut star: Option<usize> = None;
    let mut mark = 0usize;
    while ti < t.len() {
        if pi < p.len() && (p[pi] == '?' || p[pi] == t[ti]) {
            pi += 1;
            ti += 1;
        } else if pi < p.len() && p[pi] == '*' {
            star = Some(pi);
            mark = ti;
            pi += 1;
        } else if let Some(s) = star {
            pi = s + 1;
            mark += 1;
            ti = mark;
        } else {
            return false;
        }
    }
    while pi < p.len() && p[pi] == '*' {
        pi += 1;
    }
    pi == p.len()
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
    pub student_weakness: f64,
    pub points_at_stake: f64,
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
            let (weight, weakness) = agg.weight_and_weakness(category);
            ranked.push(RankedCard {
                card_id,
                category: category.map(str::to_string),
                topic_weight: weight,
                student_weakness: weakness,
                points_at_stake: weight * weakness,
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

    const TAXONOMY: &str = r#"{
        "version": 1,
        "aamc_categories": {
            "1A": {"name": "Biomolecules", "weight": 5.0},
            "1B": {"name": "Cellular", "weight": 10.0},
            "3A": {"name": "Behavior", "weight": 1.0}
        },
        "mappings": [
            {"deck_tag_or_subdeck": "Biochem", "category": "1A"},
            {"deck_tag_or_subdeck": "Cell*", "category": "1B"},
            {"deck_tag_or_subdeck": "Psych::Behavior", "category": "3A"}
        ]
    }"#;

    fn taxonomy() -> Taxonomy {
        Taxonomy::from_json_str(TAXONOMY).unwrap()
    }

    /// Add a review card with the given tag, FSRS stability and days since the
    /// last review (which determines its recall probability). Returns its id.
    fn add_review_card(
        col: &mut Collection,
        tag: &str,
        stability: f32,
        days_since_review: i64,
    ) -> CardId {
        let nt = col.get_notetype_by_name("Basic").unwrap().unwrap();
        let mut note = nt.new_note();
        note.set_field(0, "q").unwrap();
        if !tag.is_empty() {
            note.tags = vec![tag.to_string()];
        }
        col.add_note(&mut note, DeckId(1)).unwrap();
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
    fn pattern_matching_glob_and_prefix() {
        // exact + hierarchy prefix
        assert!(pattern_matches("Biochem", "Biochem"));
        assert!(pattern_matches("Biochem", "Biochem::Enzymes"));
        assert!(!pattern_matches("Biochem", "Biochemistry"));
        // glob
        assert!(pattern_matches("Cell*", "CellBio"));
        assert!(pattern_matches("Cell*", "Cellular::Respiration"));
        assert!(!pattern_matches("Cell*", "Biochem"));
        // case-insensitive
        assert!(pattern_matches("biochem", "Biochem::X"));
    }

    #[test]
    fn category_resolution_and_untagged() {
        let tax = taxonomy();
        assert_eq!(tax.category_for(&["Biochem::Enzymes"], ""), Some("1A"));
        assert_eq!(tax.category_for(&["Cellular"], ""), Some("1B"));
        assert_eq!(tax.category_for(&["Psych::Behavior::Op"], ""), Some("3A"));
        // untagged / no matching mapping
        assert_eq!(tax.category_for(&["Anatomy"], ""), None);
        assert_eq!(tax.category_for(&[], ""), None);
    }

    #[test]
    fn per_topic_weakness_aggregation() {
        let mut col = Collection::new();
        let tax = taxonomy();
        // 1A (Biochem): well-remembered -> low weakness
        add_review_card(&mut col, "Biochem", 1000.0, 1);
        add_review_card(&mut col, "Biochem", 1000.0, 1);
        // 1B (Cellular): poorly remembered -> high weakness
        add_review_card(&mut col, "Cellular", 0.5, 60);

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

        // coverage: 2 of 3 outline categories have cards
        let coverage = agg.coverage_report();
        assert_eq!(coverage.categories_total, 3);
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
        let strong = add_review_card(&mut col, "Biochem", 1000.0, 1);
        // 1B weight 10, badly forgotten -> highest points
        let weak = add_review_card(&mut col, "Cellular", 0.4, 90);
        // untagged -> zero points, ranks last
        let untagged = add_review_card(&mut col, "", 0.4, 90);

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
}
