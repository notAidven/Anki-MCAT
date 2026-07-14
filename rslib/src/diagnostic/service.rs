// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

use anki_proto::diagnostic as pb;

use crate::diagnostic::DiagnosticPrior;
use crate::diagnostic::Difficulty;
use crate::diagnostic::ItemResponse;
use crate::diagnostic::PoolWeights;
use crate::diagnostic::ScorerConfig;
use crate::diagnostic::DEFAULT_DECAY_PSEUDOCOUNT;
use crate::diagnostic::DEFAULT_KAPPA;
use crate::diagnostic::DEFAULT_MU0;
use crate::prelude::*;

impl crate::services::DiagnosticService for Collection {
    fn get_diagnostic_quiz(
        &mut self,
        input: pb::DiagnosticQuizRequest,
    ) -> Result<pb::DiagnosticQuiz> {
        let mode = normalize_mode(&input.mode);
        let Some(bank) = self.load_diagnostic_quiz(Some(input.quiz_path.as_str()))? else {
            return Ok(pb::DiagnosticQuiz {
                mode,
                present: false,
                ..Default::default()
            });
        };
        let items = bank
            .items_for_mode(&mode)
            .into_iter()
            .map(|it| pb::DiagnosticItem {
                id: it.id,
                category: it.category,
                category_name: it.category_name,
                section: it.section,
                discipline: it.discipline,
                cognitive_level: it.cognitive_level,
                difficulty: it.difficulty,
                stem: it.stem,
                options: it
                    .options
                    .into_iter()
                    .map(|o| pb::DiagnosticOption {
                        key: o.key,
                        text: o.text,
                    })
                    .collect(),
                answer: it.answer,
                rationale: it.rationale,
                source_url: it.source.url,
            })
            .collect();
        Ok(pb::DiagnosticQuiz {
            quiz_id: bank.quiz_id,
            title: bank.title,
            description: bank.description,
            mode,
            items,
            present: true,
        })
    }

    fn score_and_seed_diagnostic(
        &mut self,
        input: pb::DiagnosticResponses,
    ) -> Result<pb::DiagnosticPrior> {
        let mode = normalize_mode(&input.mode);
        let cfg = ScorerConfig {
            mu0: positive_or(input.mu0, DEFAULT_MU0),
            kappa: positive_or(input.kappa, DEFAULT_KAPPA),
            difficulty_aware: !input.disable_difficulty,
            pool: !input.disable_pooling,
            pool_weights: PoolWeights::default(),
        };
        let decay = positive_or(input.decay_pseudocount, DEFAULT_DECAY_PSEUDOCOUNT);

        let responses: Vec<ItemResponse> = input
            .responses
            .iter()
            .map(|r| ItemResponse {
                item_id: r.item_id.clone(),
                category: r.category.clone(),
                difficulty: Difficulty::from_label(&r.difficulty),
                answered: r.answered,
                correct: r.correct,
            })
            .collect();

        let scores = crate::diagnostic::score_diagnostic(&responses, &cfg);
        let prior = DiagnosticPrior::from_scores(&mode, decay, &scores);
        self.save_diagnostic_prior(&prior)?;
        Ok(prior_to_proto(&prior, true))
    }

    fn get_diagnostic_prior(&mut self) -> Result<pb::DiagnosticPrior> {
        match self.load_diagnostic_prior() {
            Some(prior) => Ok(prior_to_proto(&prior, true)),
            None => Ok(pb::DiagnosticPrior {
                present: false,
                ..Default::default()
            }),
        }
    }

    fn clear_diagnostic_prior(&mut self) -> Result<()> {
        self.clear_diagnostic_prior()?;
        Ok(())
    }
}

fn normalize_mode(mode: &str) -> String {
    if mode == "extended" {
        "extended".to_string()
    } else {
        "short".to_string()
    }
}

fn positive_or(value: f64, default: f64) -> f64 {
    if value > 0.0 {
        value
    } else {
        default
    }
}

fn prior_to_proto(prior: &DiagnosticPrior, present: bool) -> pb::DiagnosticPrior {
    pb::DiagnosticPrior {
        present,
        taken_at: prior.taken_at,
        mode: prior.mode.clone(),
        decay_pseudocount: prior.decay_pseudocount(),
        categories: prior
            .categories
            .iter()
            .map(|(category, cp)| pb::CategoryPrior {
                category: category.clone(),
                n: cp.n,
                k: cp.k,
                p_hat: cp.p_hat,
                weakness: cp.weakness,
                band: cp.band.clone(),
            })
            .collect(),
    }
}
