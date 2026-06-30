// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Benchmark support for the ReadyMCAT points-at-stake queue.
//!
//! These helpers back the `just bench` entry point (`tools/mcat_bench`). They
//! live in the engine crate because building a large synthetic deck and forcing
//! a full study-queue build both need crate-private access (`storage`,
//! `build_queues`). Nothing here is used by the shipping desktop/iOS apps.

use std::time::Instant;

use crate::card::CardQueue;
use crate::card::CardType;
use crate::card::FsrsMemoryState;
use crate::deckconfig::DeckConfigId;
use crate::deckconfig::ReviewCardOrder;
use crate::prelude::*;
use crate::scheduler::answering::CardAnswer;
use crate::scheduler::answering::Rating;

/// Deck names mirroring `taxonomy.json` subdeck prefixes, so generated cards
/// resolve to a spread of AAMC categories. All live under `MCAT::`, so a single
/// `build_queues(MCAT)` covers them; `MCAT::Research Methods` maps to no
/// category (the untagged/uncovered edge case).
const BENCH_DECKS: &[&str] = &[
    "MCAT::Biochemistry::Enzymes",
    "MCAT::Biochemistry::Metabolism",
    "MCAT::Biology::Cells",
    "MCAT::Biology::Nervous System",
    "MCAT::Biology::Cardiovascular System",
    "MCAT::General Chemistry::Acids & Bases",
    "MCAT::General Chemistry::Equilibrium",
    "MCAT::Organic Chemistry::Alcohols",
    "MCAT::Physics::Kinematics",
    "MCAT::Physics::Electricity & Circuits",
    "MCAT::Psychology::Memory",
    "MCAT::Psychology::Sensation",
    "MCAT::Research Methods",
];

/// Tag sets exercised by the templates: a subdeck-only card, three `#`-tag
/// cards (whose tag overrides the subdeck), and a `ReadyMCAT::struggling` card
/// (whose priority is boosted).
const BENCH_TAG_SETS: &[&[&str]] = &[
    &[],
    &["#Physiology::Cells::Viruses"],
    &["#OrganicChemistry::Spectroscopy"],
    &["#Psychology::SocialPsychology"],
    &["#Physiology::Cells", super::STRUGGLING_TAG],
];

/// FSRS stabilities (in days), paired with the tag sets so per-topic weakness
/// varies across the deck.
const BENCH_STABILITIES: &[f32] = &[2.0, 20.0, 80.0, 300.0, 1000.0];

impl Collection {
    /// Build a synthetic deck of roughly `total` due review cards for `just
    /// bench`, and switch the default deck config to the points-at-stake review
    /// order (with the review limit lifted so the whole deck is gathered). A
    /// handful of template cards are authored through the normal API (so their
    /// notes/FSRS state are valid), then cloned in one transaction. Returns the
    /// number of cards created.
    pub fn readymcat_generate_synthetic_deck(&mut self, total: usize) -> Result<usize> {
        let mut config = self
            .get_deck_config(DeckConfigId(1), true)?
            .or_invalid("default deck config")?;
        config.inner.review_order = ReviewCardOrder::PointsAtStake as i32;
        config.inner.reviews_per_day = 1_000_000;
        self.add_or_update_deck_config(&mut config)?;

        let deck_ids: Vec<DeckId> = BENCH_DECKS
            .iter()
            .map(|name| self.get_or_create_normal_deck(name).map(|deck| deck.id))
            .collect::<Result<_>>()?;

        let basic = self
            .get_notetype_by_name("Basic")?
            .or_invalid("Basic notetype")?;

        // Author one template review note+card per tag set, through the normal
        // API (so notes/FSRS state are valid); capture their ids for cloning.
        let mut template_notes = Vec::new();
        let mut template_cards = Vec::new();
        for (i, tags) in BENCH_TAG_SETS.iter().enumerate() {
            let mut note = basic.new_note();
            note.set_field(0, format!("Bench question {i}"))?;
            note.set_field(1, format!("Bench answer {i}"))?;
            note.tags = tags.iter().map(|tag| tag.to_string()).collect();
            self.add_note(&mut note, deck_ids[0])?;
            template_notes.push(note.id);

            let mut card = self
                .storage
                .get_card_by_ordinal(note.id, 0)?
                .or_not_found(note.id)?;
            card.ctype = CardType::Review;
            card.queue = CardQueue::Review;
            card.due = -1;
            card.interval = 10;
            card.memory_state = Some(FsrsMemoryState {
                stability: BENCH_STABILITIES[i % BENCH_STABILITIES.len()],
                difficulty: 5.0,
            });
            card.last_review_time = Some(TimestampSecs::now().adding_secs(-30 * 86_400));
            let card_id = card.id;
            self.update_cards_maybe_undoable(vec![card], false)?;
            template_cards.push(card_id);
        }

        // Clone each template into an independent note+card (unique ids/guids, so
        // no sibling burying collapses the deck), cycling deck and due for
        // variety. A single transaction keeps this fast even at 50k cards. The
        // `left` column is given a literal 0 so the SQL keyword need not be
        // selected by name.
        let template_count = template_cards.len();
        let to_add = total.saturating_sub(template_count);
        let id_base = TimestampMillis::now().0 + 1_000;
        let note_id_base = id_base;
        let card_id_base = id_base + 1_000_000_000;
        self.transact_no_undo(|col| {
            let mut note_stmt = col.storage.db.prepare(
                "INSERT INTO notes \
                 (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) \
                 SELECT ?1, ?2, mid, mod, usn, tags, flds, sfld, csum, flags, data \
                 FROM notes WHERE id = ?3",
            )?;
            let mut card_stmt = col.storage.db.prepare(
                "INSERT INTO cards \
                 (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, \
                  reps, lapses, left, odue, odid, flags, data) \
                 SELECT ?1, ?2, ?3, ord, mod, usn, type, queue, ?4, ivl, factor, \
                  reps, lapses, 0, odue, odid, flags, data \
                 FROM cards WHERE id = ?5",
            )?;
            for i in 0..to_add {
                let slot = i % template_count;
                let new_nid = note_id_base + i as i64;
                let new_cid = card_id_base + i as i64;
                let guid = format!("readymcat-bench-{i}");
                let did = deck_ids[i % deck_ids.len()].0;
                let due = -1 - (i % 200) as i64;
                note_stmt.execute(rusqlite::params![new_nid, guid, template_notes[slot].0])?;
                card_stmt.execute(rusqlite::params![
                    new_cid,
                    new_nid,
                    did,
                    due,
                    template_cards[slot].0
                ])?;
            }
            Ok(())
        })?;

        // Study from the MCAT subtree so get_next_card/grading see these cards.
        let mcat = self.get_or_create_normal_deck("MCAT")?.id;
        self.set_current_deck(mcat)?;

        Ok(template_count + to_add)
    }

    /// Build the full study queue for `deck_id` from scratch, so the benchmark
    /// measures real queue building including the points-at-stake re-rank.
    /// Returns the number of review cards in the built queue.
    pub fn readymcat_build_study_queue(&mut self, deck_id: DeckId) -> Result<usize> {
        let mut queues = self.build_queues(deck_id)?;
        Ok(queues.counts().review)
    }

    /// Answer the current top card "Good" and fetch the next one, returning the
    /// nanoseconds spent in `(answer_card, fetch-next-card)`. Returns `None`
    /// when the queue is empty. Used by `just bench` to measure the
    /// button-press acknowledgement and next-card latencies separately.
    pub fn readymcat_time_answer_and_next(&mut self) -> Result<Option<(u128, u128)>> {
        let Some(queued) = self.get_next_card()? else {
            return Ok(None);
        };
        let mut answer = CardAnswer {
            card_id: queued.card.id,
            current_state: queued.states.current,
            new_state: queued.states.good,
            rating: Rating::Good,
            answered_at: TimestampMillis::now(),
            milliseconds_taken: 0,
            custom_data: None,
            from_queue: true,
        };

        let started = Instant::now();
        self.answer_card(&mut answer)?;
        let answer_ns = started.elapsed().as_nanos();

        let started = Instant::now();
        let _ = self.get_next_card()?;
        let next_ns = started.elapsed().as_nanos();

        Ok(Some((answer_ns, next_ns)))
    }
}
