// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

use std::collections::HashSet;

use anki_proto::points_at_stake as pb;

use crate::prelude::*;

impl crate::services::PointsAtStakeService for Collection {
    fn points_at_stake_queue(
        &mut self,
        input: pb::PointsAtStakeRequest,
    ) -> Result<pb::PointsAtStakeResponse> {
        let taxonomy = self
            .load_taxonomy(Some(input.taxonomy_path.as_str()))?
            .or_invalid(
                "taxonomy.json not found; pass taxonomy_path or place it next to the collection",
            )?;
        let agg = self.compute_topic_aggregation(&taxonomy)?;

        let deck_filter: Option<HashSet<DeckId>> = if input.deck_id != 0 {
            Some(self.deck_subtree_ids(DeckId(input.deck_id))?)
        } else {
            None
        };
        let mut ranked = self.rank_due_cards(&taxonomy, &agg, deck_filter.as_ref())?;
        if input.limit > 0 && ranked.len() > input.limit as usize {
            ranked.truncate(input.limit as usize);
        }

        let ranked_cards = ranked
            .into_iter()
            .map(|r| pb::RankedCard {
                card_id: r.card_id.0,
                category: r.category.unwrap_or_default(),
                topic_weight: r.topic_weight,
                student_weakness: r.student_weakness,
                points_at_stake: r.points_at_stake,
            })
            .collect();

        let topics = agg
            .topics
            .iter()
            .map(|(id, topic)| pb::TopicMastery {
                category: id.clone(),
                name: topic.name.clone(),
                topic_weight: topic.weight,
                graded_cards: topic.graded_cards,
                total_cards: topic.total_cards,
                mean_retrievability: topic.mean_recall(),
                student_weakness: topic.weakness(),
            })
            .collect();

        let mem = agg.memory_report();
        let cov = agg.coverage_report();

        Ok(pb::PointsAtStakeResponse {
            ranked_cards,
            topics,
            memory: Some(pb::MemoryReport {
                mean: mem.mean,
                range_low: mem.range_low,
                range_high: mem.range_high,
                graded_reviews: mem.graded_reviews,
                graded_cards: mem.graded_cards,
            }),
            coverage: Some(pb::CoverageReport {
                categories_total: cov.categories_total,
                categories_covered: cov.categories_covered,
                fraction: cov.fraction,
                weighted_fraction: cov.weighted_fraction,
            }),
            meets_data_threshold: agg.meets_data_threshold(),
        })
    }
}
