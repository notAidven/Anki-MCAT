// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! ReadyMCAT performance benchmark (`just bench`).
//!
//! Loads a synthetic 50,000-card deck (a few authored cards cloned/padded) on
//! the shared Rust engine and reports p50/p95/worst for:
//!   * queue building, including the points-at-stake review order;
//!   * grading (button-press acknowledgement) and fetching the next card;
//!   * the dashboard's per-topic mastery query.
//!
//! Numbers are compared against the PRD targets (button < 50 ms p95, next card
//! < 100 ms p95, dashboard < 1 s p95).

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;
use std::time::Instant;

use anki::collection::CollectionBuilder;
use anki::error::Result;

struct Args {
    cards: usize,
    iters: usize,
    grade_iters: usize,
    taxonomy: String,
}

fn parse_args() -> Args {
    let mut args = Args {
        cards: 50_000,
        iters: 50,
        grade_iters: 1_000,
        taxonomy: "taxonomy.json".to_string(),
    };
    let mut rest = env::args().skip(1);
    while let Some(flag) = rest.next() {
        match flag.as_str() {
            "--cards" => {
                if let Some(v) = rest.next().and_then(|v| v.parse().ok()) {
                    args.cards = v;
                }
            }
            "--iters" => {
                if let Some(v) = rest.next().and_then(|v| v.parse().ok()) {
                    args.iters = v;
                }
            }
            "--grade-iters" => {
                if let Some(v) = rest.next().and_then(|v| v.parse().ok()) {
                    args.grade_iters = v;
                }
            }
            "--taxonomy" => {
                if let Some(v) = rest.next() {
                    args.taxonomy = v;
                }
            }
            other => eprintln!("ignoring unknown argument: {other}"),
        }
    }
    args
}

fn main() {
    if let Err(err) = run() {
        eprintln!("mcat_bench failed: {err:?}");
        process::exit(1);
    }
}

fn run() -> Result<()> {
    let args = parse_args();

    // Throwaway on-disk collection in a temp folder.
    let base = env::temp_dir().join(format!("readymcat_bench_{}", process::id()));
    let _ = fs::remove_dir_all(&base);
    fs::create_dir_all(&base).expect("create temp dir");
    let col_path = base.join("collection.anki2");
    let media_folder = base.join("collection.media");
    let media_db = base.join("collection.media.db");
    fs::create_dir_all(&media_folder).expect("create media dir");

    // The engine looks for taxonomy.json next to the collection, so copy it in.
    let tax_src = PathBuf::from(&args.taxonomy);
    fs::copy(&tax_src, base.join("taxonomy.json"))
        .unwrap_or_else(|e| panic!("could not copy taxonomy from {}: {e}", tax_src.display()));

    let mut builder = CollectionBuilder::new(col_path.clone());
    builder.set_media_paths(media_folder.clone(), media_db.clone());
    let mut col = builder.build()?;

    eprintln!("Generating synthetic deck of {} cards…", args.cards);
    let started = Instant::now();
    let created = col.readymcat_generate_synthetic_deck(args.cards)?;
    eprintln!(
        "  created {created} cards in {:.1}s",
        started.elapsed().as_secs_f64()
    );

    let mcat = col.get_or_create_normal_deck("MCAT")?.id;
    let tax = col
        .load_taxonomy(None)?
        .expect("taxonomy.json not found next to the collection");

    // Warm up each path once (page caches, lazily-initialised state).
    let review_n = col.readymcat_build_study_queue(mcat)?;
    {
        let agg = col.compute_topic_aggregation(&tax)?;
        let _ = col.rank_due_cards(&tax, &agg, None)?;
    }
    eprintln!("Warmup queue contained {review_n} review cards.\n");

    // 1. Queue building, including the points-at-stake re-rank.
    let mut build_ns = Vec::with_capacity(args.iters);
    for _ in 0..args.iters {
        let started = Instant::now();
        col.readymcat_build_study_queue(mcat)?;
        build_ns.push(started.elapsed().as_nanos());
    }

    // 2. Dashboard per-topic mastery query (aggregation + ranking).
    let mut dashboard_ns = Vec::with_capacity(args.iters);
    for _ in 0..args.iters {
        let started = Instant::now();
        let agg = col.compute_topic_aggregation(&tax)?;
        let _ = col.rank_due_cards(&tax, &agg, None)?;
        dashboard_ns.push(started.elapsed().as_nanos());
    }

    // 3. Grading (button press) and fetching the next card.
    let mut answer_ns = Vec::with_capacity(args.grade_iters);
    let mut next_ns = Vec::with_capacity(args.grade_iters);
    for _ in 0..args.grade_iters {
        match col.readymcat_time_answer_and_next()? {
            Some((answer, next)) => {
                answer_ns.push(answer);
                next_ns.push(next);
            }
            None => break,
        }
    }

    println!(
        "\n# ReadyMCAT benchmark — {created} cards, {} iterations",
        args.iters
    );
    println!(
        "{:<32} {:>10} {:>10} {:>10}   PRD target (p95)",
        "operation", "p50", "p95", "worst"
    );
    println!("{}", "-".repeat(86));
    report("queue build (points-at-stake)", &build_ns, None);
    report("button press (grade ack)", &answer_ns, Some(50.0));
    report("next card after grading", &next_ns, Some(100.0));
    report("dashboard per-topic mastery", &dashboard_ns, Some(1000.0));
    println!();

    drop(col);
    let _ = fs::remove_dir_all(&base);
    Ok(())
}

fn report(name: &str, samples_ns: &[u128], target_p95_ms: Option<f64>) {
    if samples_ns.is_empty() {
        println!("{name:<32} (no samples)");
        return;
    }
    let mut ms: Vec<f64> = samples_ns.iter().map(|ns| *ns as f64 / 1e6).collect();
    ms.sort_by(f64::total_cmp);
    let p50 = percentile(&ms, 50.0);
    let p95 = percentile(&ms, 95.0);
    let worst = *ms.last().unwrap();
    let verdict = match target_p95_ms {
        Some(target) if p95 < target => format!("< {target:.0} ms  ✅ PASS"),
        Some(target) => format!("< {target:.0} ms  ❌ FAIL"),
        None => "—".to_string(),
    };
    println!("{name:<32} {p50:>8.3}ms {p95:>8.3}ms {worst:>8.3}ms   {verdict}");
}

fn percentile(sorted_ms: &[f64], p: f64) -> f64 {
    if sorted_ms.is_empty() {
        return 0.0;
    }
    let rank = ((p / 100.0) * (sorted_ms.len() as f64 - 1.0)).round() as usize;
    sorted_ms[rank.min(sorted_ms.len() - 1)]
}
