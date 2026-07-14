// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! ReadyMCAT performance benchmark (`just bench`).
//!
//! Loads a synthetic 50,000-card deck (a few authored cards cloned/padded) on
//! the shared Rust engine and reports p50/p95/worst (for repeatable actions) or
//! a single number (for one-shot actions) for every latency/limit the Speedrun
//! rubric §10 ("Speed & limits") lists. It is a single, re-runnable command and
//! emits both a readable table and machine-readable JSON.
//!
//! Actions measured (all on the SAME on-disk 50k collection):
//!   * queue building, including the points-at-stake review order;
//!   * grading (button-press acknowledgement) and fetching the next card;
//!   * the dashboard's per-topic mastery query (initial load);
//!   * the full honest-scores recompute behind a dashboard/home refresh
//!     (memory + performance + readiness + ranked queue — the same work
//!     `PointsAtStakeService::points_at_stake_queue` does);
//!   * cold start: a fresh process opening the collection and building the
//!     first study queue (process spawn -> first queue ready);
//!   * collection sync against an in-process anki-sync-server on loopback
//!     (full upload of the whole 50k collection, then incremental normal
//!     syncs) — Anki's OWN protocol, the same client path the desktop/phone
//!     use, labelled as excluding WAN latency; and
//!   * peak resident memory (RSS) while holding + operating the collection,
//!     compared against a stated ceiling.
//!
//! Targets (rubric §10): button < 50 ms p95, next card < 100 ms p95, dashboard
//! load < 1 s p95, dashboard refresh < 500 ms p95, sync < 5 s, plus a stated
//! memory ceiling and a stated cold-start target we hold ourselves to.

use std::env;
use std::fs;
use std::path::Path;
use std::path::PathBuf;
use std::process;
use std::process::Command;
use std::process::Stdio;
use std::time::Duration;
use std::time::Instant;

use anki::collection::Collection;
use anki::collection::CollectionBuilder;
use anki::error::Result;
use anki::sync::http_server::default_ip_header;
use anki::sync::http_server::SimpleServer;
use anki::sync::http_server::SyncServerConfig;
use anki::sync::login::sync_login;
use reqwest::Client;
use reqwest::Url;
use serde_json::json;
use serde_json::Value;

// ---- rubric §10 targets ---------------------------------------------------
const TARGET_BUTTON_MS: f64 = 50.0;
const TARGET_NEXT_MS: f64 = 100.0;
const TARGET_DASHBOARD_LOAD_MS: f64 = 1_000.0;
const TARGET_DASHBOARD_REFRESH_MS: f64 = 500.0;
const TARGET_SYNC_MS: f64 = 5_000.0;
/// Not a rubric-fixed number; a target we state and hold ourselves to for a
/// fresh process reaching "first queue ready".
const TARGET_COLD_START_MS: f64 = 2_000.0;
/// The memory ceiling we STATE for a 50k-card collection and stay under. Peak
/// RSS below is reported honestly against this number. Chosen as a tight-but-
/// safe cap: measured peak on 50k is ~290 MB (core) / ~340 MB (full run), so a
/// 512 MB ("half a gig") ceiling holds with margin while staying meaningful.
const DEFAULT_MEM_LIMIT_MB: f64 = 512.0;

struct Args {
    cards: usize,
    iters: usize,
    grade_iters: usize,
    cold_iters: usize,
    sync_iters: usize,
    mem_limit_mb: f64,
    taxonomy: String,
    out_dir: PathBuf,
    run_sync: bool,
    run_cold: bool,
    write_artifact: bool,
}

impl Default for Args {
    fn default() -> Self {
        let out_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        Args {
            cards: 50_000,
            iters: 50,
            grade_iters: 1_000,
            cold_iters: 12,
            sync_iters: 20,
            mem_limit_mb: DEFAULT_MEM_LIMIT_MB,
            taxonomy: "taxonomy.json".to_string(),
            out_dir,
            run_sync: true,
            run_cold: true,
            write_artifact: true,
        }
    }
}

fn parse_args() -> Args {
    let mut args = Args::default();
    let mut rest = env::args().skip(1);
    while let Some(flag) = rest.next() {
        match flag.as_str() {
            "--cards" => set_usize(&mut args.cards, rest.next()),
            "--iters" => set_usize(&mut args.iters, rest.next()),
            "--grade-iters" => set_usize(&mut args.grade_iters, rest.next()),
            "--cold-iters" => set_usize(&mut args.cold_iters, rest.next()),
            "--sync-iters" => set_usize(&mut args.sync_iters, rest.next()),
            "--mem-limit-mb" => {
                if let Some(v) = rest.next().and_then(|v| v.parse().ok()) {
                    args.mem_limit_mb = v;
                }
            }
            "--taxonomy" => {
                if let Some(v) = rest.next() {
                    args.taxonomy = v;
                }
            }
            "--out-dir" => {
                if let Some(v) = rest.next() {
                    args.out_dir = PathBuf::from(v);
                }
            }
            "--no-sync" => args.run_sync = false,
            "--no-cold" => args.run_cold = false,
            "--no-write" => args.write_artifact = false,
            other => eprintln!("ignoring unknown argument: {other}"),
        }
    }
    args
}

fn set_usize(slot: &mut usize, v: Option<String>) {
    if let Some(v) = v.and_then(|v| v.parse().ok()) {
        *slot = v;
    }
}

fn main() {
    // Internal sub-modes dispatched before normal arg parsing.
    let raw: Vec<String> = env::args().collect();
    if let Some(pos) = raw.iter().position(|a| a == "--cold-open") {
        // Fresh-process cold-start child: open the collection + build the first
        // study queue (points-at-stake rerank included), then exit. The parent
        // times this from spawn to exit.
        let path = raw.get(pos + 1).cloned().unwrap_or_default();
        if let Err(err) = cold_open(&path) {
            eprintln!("cold-open failed: {err:?}");
            process::exit(1);
        }
        return;
    }

    if let Err(err) = run() {
        eprintln!("mcat_bench failed: {err:?}");
        process::exit(1);
    }
}

/// Open a collection with the media paths the bench lays out next to it.
fn open_collection(col_path: &Path) -> Result<Collection> {
    let parent = col_path.parent().unwrap_or_else(|| Path::new("."));
    let media_folder = parent.join("collection.media");
    let media_db = parent.join("collection.media.db");
    let _ = fs::create_dir_all(&media_folder);
    let mut builder = CollectionBuilder::new(col_path.to_path_buf());
    builder.set_media_paths(media_folder, media_db);
    builder.build()
}

/// Lay out a fresh collection dir with taxonomy.json copied in beside it, and
/// generate the synthetic deck. Returns (collection, base_dir, created).
fn build_deck_at(base: &Path, taxonomy: &str, cards: usize) -> Result<(Collection, usize)> {
    let _ = fs::remove_dir_all(base);
    fs::create_dir_all(base).expect("create bench dir");
    let col_path = base.join("collection.anki2");
    let media_folder = base.join("collection.media");
    fs::create_dir_all(&media_folder).expect("create media dir");

    let tax_src = PathBuf::from(taxonomy);
    fs::copy(&tax_src, base.join("taxonomy.json"))
        .unwrap_or_else(|e| panic!("could not copy taxonomy from {}: {e}", tax_src.display()));

    let mut col = open_collection(&col_path)?;
    let created = col.readymcat_generate_synthetic_deck(cards)?;
    Ok((col, created))
}

/// `--cold-open` child: open + build first queue, then exit.
fn cold_open(col_path: &str) -> Result<()> {
    let col_path = PathBuf::from(col_path);
    let mut col = open_collection(&col_path)?;
    let mcat = col.get_or_create_normal_deck("MCAT")?.id;
    let _ = col.readymcat_build_study_queue(mcat)?;
    Ok(())
}

fn run() -> Result<()> {
    let args = parse_args();

    let base = env::temp_dir().join(format!("readymcat_bench_{}", process::id()));
    let (mut col, created) = build_deck_at(&base, &args.taxonomy, args.cards)?;
    let col_path = base.join("collection.anki2");
    eprintln!("Generating synthetic deck of {} cards…", args.cards);
    eprintln!("  created {created} cards");

    let mcat = col.get_or_create_normal_deck("MCAT")?.id;
    let tax = col
        .load_taxonomy(None)?
        .expect("taxonomy.json not found next to the collection");

    // Warm up each path once (page caches, lazily-initialised state).
    let review_n = col.readymcat_build_study_queue(mcat)?;
    {
        let agg = col.compute_topic_aggregation(&tax)?;
        let _ = col.rank_due_cards(&tax, &agg, None)?;
        let _ = col.compute_performance(&tax)?;
    }
    eprintln!("Warmup queue contained {review_n} review cards.\n");

    // 1. Queue building, including the points-at-stake re-rank.
    let mut build_ns = Vec::with_capacity(args.iters);
    for _ in 0..args.iters {
        let started = Instant::now();
        col.readymcat_build_study_queue(mcat)?;
        build_ns.push(started.elapsed().as_nanos());
    }

    // 2. Dashboard per-topic mastery query (aggregation + ranking) — the
    //    initial dashboard load.
    let mut dashboard_ns = Vec::with_capacity(args.iters);
    for _ in 0..args.iters {
        let started = Instant::now();
        let agg = col.compute_topic_aggregation(&tax)?;
        let _ = col.rank_due_cards(&tax, &agg, None)?;
        dashboard_ns.push(started.elapsed().as_nanos());
    }

    // 3. Dashboard REFRESH: the full honest-scores recompute (memory +
    //    performance + readiness + ranked queue) — the same work the
    //    PointsAtStakeService does behind a dashboard/home refresh.
    let mut refresh_ns = Vec::with_capacity(args.iters);
    for _ in 0..args.iters {
        let started = Instant::now();
        let agg = col.compute_topic_aggregation(&tax)?;
        let _ranked = col.rank_due_cards(&tax, &agg, None)?;
        let mem = agg.memory_report();
        let cov = agg.coverage_report();
        let memory_meets = agg.meets_data_threshold();
        let perf = col.compute_performance(&tax)?;
        let perf_report = perf.report();
        let _readiness =
            anki::points_at_stake::project_readiness(&mem, memory_meets, &perf_report, &cov);
        refresh_ns.push(started.elapsed().as_nanos());
    }

    // Close the primary collection so its on-disk file is fully consistent, then
    // take a PRISTINE snapshot (its due cards still ungraded) for the sync
    // benchmark: the grade bench below exhausts the primary's due queue, so sync
    // must copy from this pre-grade snapshot to push real graded-review deltas.
    drop(col);
    let pristine = base.join("pristine");
    let _ = fs::create_dir_all(&pristine);
    let pristine_col = pristine.join("collection.anki2");
    let _ = fs::copy(&col_path, &pristine_col);
    let _ = fs::copy(base.join("taxonomy.json"), pristine.join("taxonomy.json"));

    // 4. Cold start: fresh process -> first queue ready, on the pristine
    //    collection so the points-at-stake rerank actually runs on real due cards.
    let exe = env::current_exe().expect("current exe");
    let mut cold_ns: Vec<u128> = Vec::new();
    if args.run_cold {
        eprintln!("Measuring cold start ({} launches)…", args.cold_iters);
        cold_ns = cold_start_samples(&exe, &col_path, args.cold_iters);
    }

    // 5. Grading (button press) and fetching the next card. Reopen the primary
    //    (still pristine — cold_open never grades) and grade its due cards.
    let mut col = open_collection(&col_path)?;
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

    // Peak RSS while HOLDING + OPERATING the single 50k collection (deck build +
    // queue builds + full scores recompute + grading), captured before sync
    // opens a second collection. This is the headline memory number for 50k.
    let peak_rss_core_mb = peak_rss_mb();
    drop(col);

    // 6. Collection sync against an in-process server on loopback, sourced from
    //    the pristine snapshot so incremental syncs push real review deltas.
    let sync = if args.run_sync {
        eprintln!("Measuring sync (in-process server, full upload + {} incremental)…", args.sync_iters);
        run_sync_bench(&base, &pristine_col, args.sync_iters)
    } else {
        SyncResults::skipped("disabled via --no-sync")
    };

    // Peak RSS across the WHOLE run (includes the loopback server + a second
    // collection + the full-upload buffer). Reported for transparency.
    let peak_rss_full_mb = peak_rss_mb();

    // ---- readable summary --------------------------------------------------
    println!(
        "\n# ReadyMCAT benchmark — {created} cards, {} iterations",
        args.iters
    );
    println!(
        "{:<34} {:>10} {:>10} {:>10}   target (p95)",
        "operation", "p50", "p95", "worst"
    );
    println!("{}", "-".repeat(90));
    report("queue build (points-at-stake)", &build_ns, None);
    report("button press (grade ack)", &answer_ns, Some(TARGET_BUTTON_MS));
    report("next card after grading", &next_ns, Some(TARGET_NEXT_MS));
    report(
        "dashboard load (per-topic mastery)",
        &dashboard_ns,
        Some(TARGET_DASHBOARD_LOAD_MS),
    );
    report(
        "dashboard refresh (scores recompute)",
        &refresh_ns,
        Some(TARGET_DASHBOARD_REFRESH_MS),
    );
    if args.run_cold {
        report("cold start (spawn->queue ready)", &cold_ns, Some(TARGET_COLD_START_MS));
    }
    println!();

    // Sync summary
    println!("## Sync (Anki protocol, in-process loopback server — excludes WAN latency)");
    if let Some(err) = &sync.error {
        println!("  sync unavailable: {err}");
    } else {
        println!(
            "  full upload of 50k collection ({:.1} MB on disk): {:.1} ms   {}",
            sync.col_mb,
            sync.full_upload_ms,
            verdict_single(sync.full_upload_ms, TARGET_SYNC_MS)
        );
        if !sync.incremental_ms.is_empty() {
            let mut ms = sync.incremental_ms.clone();
            ms.sort_by(f64::total_cmp);
            let (p50, p95, worst, _mean) = stats_ms(&ms);
            println!(
                "  incremental sync (grade 1 review + normal_sync round trip, {} deltas pushed): p50 {:.1} ms  p95 {:.1} ms  worst {:.1} ms   {}",
                sync.deltas_pushed,
                p50,
                p95,
                worst,
                verdict_single(p95, TARGET_SYNC_MS)
            );
        }
    }
    println!();

    // Memory summary
    let within = peak_rss_core_mb <= args.mem_limit_mb;
    println!("## Memory (50k-card collection)");
    println!(
        "  stated ceiling: {:.0} MB   peak RSS (holding+operating 50k): {:.1} MB   {}",
        args.mem_limit_mb,
        peak_rss_core_mb,
        if within { "✅ WITHIN LIMIT" } else { "❌ OVER LIMIT" }
    );
    println!(
        "  peak RSS across full run (incl. loopback sync + 2nd collection): {:.1} MB",
        peak_rss_full_mb
    );
    println!();

    // ---- machine-readable JSON + artifact ---------------------------------
    let doc = build_json(
        &args,
        created,
        review_n,
        &build_ns,
        &answer_ns,
        &next_ns,
        &dashboard_ns,
        &refresh_ns,
        &cold_ns,
        &sync,
        peak_rss_core_mb,
        peak_rss_full_mb,
        within,
    );

    if args.write_artifact {
        let _ = fs::create_dir_all(&args.out_dir);
        let json_path = args.out_dir.join("bench-results.json");
        let md_path = args.out_dir.join("bench-results.md");
        if let Ok(s) = serde_json::to_string_pretty(&doc) {
            let _ = fs::write(&json_path, format!("{s}\n"));
            eprintln!("wrote {}", json_path.display());
        }
        let md = render_markdown(&doc);
        let _ = fs::write(&md_path, md);
        eprintln!("wrote {}", md_path.display());
    }
    // Always echo the JSON to stdout so a caller can pipe/tee it.
    println!("{}", serde_json::to_string(&doc).unwrap_or_default());

    let _ = fs::remove_dir_all(&base);
    Ok(())
}

// ---- cold start -----------------------------------------------------------

fn cold_start_samples(exe: &Path, col_path: &Path, iters: usize) -> Vec<u128> {
    let mut samples = Vec::with_capacity(iters);
    for _ in 0..iters {
        let started = Instant::now();
        let status = Command::new(exe)
            .arg("--cold-open")
            .arg(col_path)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        let elapsed = started.elapsed().as_nanos();
        match status {
            Ok(s) if s.success() => samples.push(elapsed),
            Ok(s) => eprintln!("  cold-open child exited with {s}"),
            Err(e) => eprintln!("  cold-open spawn failed: {e}"),
        }
    }
    samples
}

// ---- sync -----------------------------------------------------------------

struct SyncResults {
    full_upload_ms: f64,
    incremental_ms: Vec<f64>,
    deltas_pushed: usize,
    col_mb: f64,
    endpoint: String,
    error: Option<String>,
}

impl SyncResults {
    fn skipped(reason: &str) -> Self {
        SyncResults {
            full_upload_ms: 0.0,
            incremental_ms: Vec::new(),
            deltas_pushed: 0,
            col_mb: 0.0,
            endpoint: String::new(),
            error: Some(reason.to_string()),
        }
    }
}

/// Start an in-process anki-sync-server on loopback, then time a full upload of
/// the whole 50k collection followed by `iters` incremental normal syncs (each
/// after grading one card). Uses Anki's OWN sync protocol and the shared client
/// path — the same code the desktop/phone drive. Non-fatal: any failure is
/// captured in `SyncResults.error` so the rest of the bench still reports.
fn run_sync_bench(base: &Path, src_col: &Path, iters: usize) -> SyncResults {
    let rt = match tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(e) => return SyncResults::skipped(&format!("tokio runtime: {e}")),
    };
    match rt.block_on(sync_bench_async(base, src_col, iters)) {
        Ok(r) => r,
        Err(e) => SyncResults::skipped(&e),
    }
}

async fn sync_bench_async(base: &Path, src_col: &Path, iters: usize) -> std::result::Result<SyncResults, String> {
    // A throwaway copy of the generated collection, so the sync's schema
    // downgrade/close never disturbs the primary collection files.
    let sync_dir = base.join("sync");
    let _ = fs::remove_dir_all(&sync_dir);
    fs::create_dir_all(&sync_dir).map_err(|e| format!("mkdir sync: {e}"))?;
    let col_copy = sync_dir.join("collection.anki2");
    fs::copy(src_col, &col_copy).map_err(|e| format!("copy collection: {e}"))?;
    // taxonomy beside the copy so reopening keeps the points-at-stake order.
    let _ = fs::copy(
        src_col.with_file_name("taxonomy.json"),
        col_copy.with_file_name("taxonomy.json"),
    );
    let col_mb = fs::metadata(&col_copy).map(|m| m.len()).unwrap_or(0) as f64 / (1024.0 * 1024.0);

    // Start the server on an ephemeral port with a throwaway base folder.
    let server_base = base.join("sync-server");
    fs::create_dir_all(&server_base).map_err(|e| format!("mkdir server: {e}"))?;
    env::set_var("SYNC_USER1", "user:pass");
    let (addr, server_fut) = SimpleServer::make_server(SyncServerConfig {
        host: "127.0.0.1".parse().unwrap(),
        port: 0,
        base_folder: server_base,
        ip_header: default_ip_header(),
    })
    .await
    .map_err(|e| format!("start server: {e}"))?;
    tokio::spawn(server_fut);

    let endpoint = format!("http://{addr}/");
    let client = Client::new();

    // Wait until the server answers /health.
    let health = format!("{endpoint}health");
    let mut up = false;
    for _ in 0..50 {
        if client.get(&health).send().await.map(|r| r.status().is_success()).unwrap_or(false) {
            up = true;
            break;
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    if !up {
        return Err("sync server did not become healthy".to_string());
    }

    // Log in for a host key, then point the auth at our loopback endpoint.
    let endpoint_url = Url::parse(&endpoint).map_err(|e| format!("endpoint url: {e}"))?;
    let mut auth = sync_login(
        "user".to_string(),
        "pass".to_string(),
        Some(endpoint.clone()),
        client.clone(),
    )
    .await
    .map_err(|e| format!("sync_login: {e:?}"))?;
    auth.endpoint = Some(endpoint_url);

    // Full upload of the whole 50k collection (worst-case initial sync).
    let col = open_collection(&col_copy).map_err(|e| format!("open (upload): {e:?}"))?;
    let t0 = Instant::now();
    col.full_upload(auth.clone(), client.clone())
        .await
        .map_err(|e| format!("full_upload: {e:?}"))?;
    let full_upload_ms = t0.elapsed().as_secs_f64() * 1000.0;

    // Incremental normal syncs: reopen once, then grade 1 card + sync per iter.
    let mut col = open_collection(&col_copy).map_err(|e| format!("open (incr): {e:?}"))?;
    let mcat = col
        .get_or_create_normal_deck("MCAT")
        .map(|d| d.id)
        .map_err(|e| format!("mcat deck: {e:?}"))?;
    let _ = col.set_current_deck(mcat);
    let mut incremental_ms = Vec::with_capacity(iters);
    let mut deltas_pushed = 0usize;
    for i in 0..iters {
        // Grade one due card so the sync has a real review delta to upload.
        // (`normal_sync` always reports NoChanges as its POST-sync state, so we
        // count grades to prove each round trip actually pushed a change.)
        if matches!(col.readymcat_time_answer_and_next(), Ok(Some(_))) {
            deltas_pushed += 1;
        }
        let t = Instant::now();
        match col.normal_sync(auth.clone(), client.clone()).await {
            Ok(_) => incremental_ms.push(t.elapsed().as_secs_f64() * 1000.0),
            Err(e) => {
                if i == 0 {
                    return Err(format!("normal_sync: {e:?}"));
                }
                break;
            }
        }
    }

    Ok(SyncResults {
        full_upload_ms,
        incremental_ms,
        deltas_pushed,
        col_mb,
        endpoint,
        error: None,
    })
}

// ---- memory ---------------------------------------------------------------

/// Peak resident set size of THIS process, in MB. `ru_maxrss` is a high-water
/// mark over the process lifetime; it is bytes on macOS and kilobytes on Linux.
fn peak_rss_mb() -> f64 {
    unsafe {
        let mut usage: libc::rusage = std::mem::zeroed();
        if libc::getrusage(libc::RUSAGE_SELF, &mut usage) != 0 {
            return 0.0;
        }
        let maxrss = usage.ru_maxrss as f64;
        if cfg!(target_os = "macos") {
            maxrss / (1024.0 * 1024.0)
        } else {
            maxrss / 1024.0
        }
    }
}

// ---- stats + reporting ----------------------------------------------------

fn report(name: &str, samples_ns: &[u128], target_p95_ms: Option<f64>) {
    if samples_ns.is_empty() {
        println!("{name:<34} (no samples)");
        return;
    }
    let mut ms: Vec<f64> = samples_ns.iter().map(|ns| *ns as f64 / 1e6).collect();
    ms.sort_by(f64::total_cmp);
    let (p50, p95, worst, _mean) = stats_ms(&ms);
    let verdict = match target_p95_ms {
        Some(target) if p95 < target => format!("< {target:.0} ms  ✅ PASS"),
        Some(target) => format!("< {target:.0} ms  ❌ FAIL"),
        None => "—".to_string(),
    };
    println!("{name:<34} {p50:>8.3}ms {p95:>8.3}ms {worst:>8.3}ms   {verdict}");
}

/// (p50, p95, worst, mean) over an already-sorted slice of milliseconds.
fn stats_ms(sorted_ms: &[f64]) -> (f64, f64, f64, f64) {
    if sorted_ms.is_empty() {
        return (0.0, 0.0, 0.0, 0.0);
    }
    let p50 = percentile(sorted_ms, 50.0);
    let p95 = percentile(sorted_ms, 95.0);
    let worst = *sorted_ms.last().unwrap();
    let mean = sorted_ms.iter().sum::<f64>() / sorted_ms.len() as f64;
    (p50, p95, worst, mean)
}

fn percentile(sorted_ms: &[f64], p: f64) -> f64 {
    if sorted_ms.is_empty() {
        return 0.0;
    }
    let rank = ((p / 100.0) * (sorted_ms.len() as f64 - 1.0)).round() as usize;
    sorted_ms[rank.min(sorted_ms.len() - 1)]
}

fn verdict_single(value_ms: f64, target_ms: f64) -> String {
    if value_ms < target_ms {
        format!("< {target_ms:.0} ms  ✅ PASS")
    } else {
        format!("< {target_ms:.0} ms  ❌ FAIL")
    }
}

// ---- JSON assembly --------------------------------------------------------

fn dist_json(samples_ns: &[u128], target_p95_ms: Option<f64>) -> Value {
    if samples_ns.is_empty() {
        return json!({ "kind": "distribution", "n": 0, "available": false });
    }
    let mut ms: Vec<f64> = samples_ns.iter().map(|ns| *ns as f64 / 1e6).collect();
    ms.sort_by(f64::total_cmp);
    let (p50, p95, worst, mean) = stats_ms(&ms);
    let verdict = target_p95_ms.map(|t| if p95 < t { "PASS" } else { "FAIL" });
    json!({
        "kind": "distribution",
        "unit": "ms",
        "n": ms.len(),
        "p50": round3(p50),
        "p95": round3(p95),
        "worst": round3(worst),
        "mean": round3(mean),
        "target_p95_ms": target_p95_ms,
        "verdict": verdict,
        "available": true,
    })
}

fn dist_json_ms(samples_ms: &[f64], target_p95_ms: Option<f64>) -> Value {
    if samples_ms.is_empty() {
        return json!({ "kind": "distribution", "n": 0, "available": false });
    }
    let mut ms = samples_ms.to_vec();
    ms.sort_by(f64::total_cmp);
    let (p50, p95, worst, mean) = stats_ms(&ms);
    let verdict = target_p95_ms.map(|t| if p95 < t { "PASS" } else { "FAIL" });
    json!({
        "kind": "distribution",
        "unit": "ms",
        "n": ms.len(),
        "p50": round3(p50),
        "p95": round3(p95),
        "worst": round3(worst),
        "mean": round3(mean),
        "target_p95_ms": target_p95_ms,
        "verdict": verdict,
        "available": true,
    })
}

fn round3(v: f64) -> f64 {
    (v * 1000.0).round() / 1000.0
}

#[allow(clippy::too_many_arguments)]
fn build_json(
    args: &Args,
    created: usize,
    review_n: usize,
    build_ns: &[u128],
    answer_ns: &[u128],
    next_ns: &[u128],
    dashboard_ns: &[u128],
    refresh_ns: &[u128],
    cold_ns: &[u128],
    sync: &SyncResults,
    peak_rss_core_mb: f64,
    peak_rss_full_mb: f64,
    within_limit: bool,
) -> Value {
    let sync_json = if let Some(err) = &sync.error {
        json!({ "available": false, "reason": err })
    } else {
        json!({
            "available": true,
            "note": "Anki's own sync protocol against an in-process anki-sync-server on loopback; EXCLUDES WAN latency (measures engine + protocol work only).",
            "endpoint": sync.endpoint,
            "collection_mb_on_disk": round3(sync.col_mb),
            "full_upload": {
                "kind": "single",
                "unit": "ms",
                "value_ms": round3(sync.full_upload_ms),
                "target_ms": TARGET_SYNC_MS,
                "verdict": if sync.full_upload_ms < TARGET_SYNC_MS { "PASS" } else { "FAIL" },
                "what": "full upload of the entire 50k collection (worst-case initial sync)"
            },
            "incremental": {
                "deltas_pushed": sync.deltas_pushed,
                "what": "grade one review, then an incremental normal_sync round trip (typical everyday sync)",
                "stats": dist_json_ms(&sync.incremental_ms, Some(TARGET_SYNC_MS))
            }
        })
    };

    json!({
        "benchmark": "readymcat-speed",
        "generated_at": chrono_now(),
        "one_command": "just bench",
        "host": {
            "os": env::consts::OS,
            "arch": env::consts::ARCH,
            "logical_cpus": std::thread::available_parallelism().map(|n| n.get()).unwrap_or(0),
        },
        "deck": {
            "cards": created,
            "review_cards_in_queue": review_n,
        },
        "config": {
            "iters": args.iters,
            "grade_iters": args.grade_iters,
            "cold_iters": args.cold_iters,
            "sync_iters": args.sync_iters,
        },
        "metrics": {
            "queue_build": dist_json(build_ns, None),
            "button_press": dist_json(answer_ns, Some(TARGET_BUTTON_MS)),
            "next_card": dist_json(next_ns, Some(TARGET_NEXT_MS)),
            "dashboard_load": dist_json(dashboard_ns, Some(TARGET_DASHBOARD_LOAD_MS)),
            "dashboard_refresh": dist_json(refresh_ns, Some(TARGET_DASHBOARD_REFRESH_MS)),
            "cold_start": dist_json(cold_ns, Some(TARGET_COLD_START_MS)),
        },
        "sync": sync_json,
        "memory": {
            "stated_limit_mb": args.mem_limit_mb,
            "peak_rss_mb": round3(peak_rss_core_mb),
            "peak_rss_full_run_mb": round3(peak_rss_full_mb),
            "within_limit": within_limit,
            "what": "peak process RSS (ru_maxrss) while holding + operating the 50k collection",
        },
        "notes": [
            "All desktop numbers are measured on the same on-disk 50k synthetic deck built by this binary.",
            "dashboard_load = per-topic mastery (aggregation + ranking); dashboard_refresh = the full memory+performance+readiness recompute (PointsAtStakeService).",
            "cold_start times a fresh child process from spawn to first study queue ready (points-at-stake rerank included).",
            "sync is measured over a loopback in-process server and therefore excludes real network latency.",
        ],
    })
}

fn chrono_now() -> String {
    chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}

// ---- markdown artifact ----------------------------------------------------

fn render_markdown(doc: &Value) -> String {
    let mut s = String::new();
    let m = &doc["metrics"];
    s.push_str("# ReadyMCAT — Speed & limits benchmark (§10)\n\n");
    s.push_str("_Self-contained, re-runnable evidence for the rubric §10 targets. Every number below is measured by `tools/mcat_bench` on a synthetic 50,000-card deck built on the shared Rust engine._\n\n");
    s.push_str(&format!(
        "- **Generated:** {}\n- **Host:** {} / {} ({} logical CPUs)\n- **Deck:** {} cards, {} review cards in the built queue\n- **One command:** `just bench`\n\n",
        doc["generated_at"].as_str().unwrap_or("?"),
        doc["host"]["os"].as_str().unwrap_or("?"),
        doc["host"]["arch"].as_str().unwrap_or("?"),
        doc["host"]["logical_cpus"],
        doc["deck"]["cards"],
        doc["deck"]["review_cards_in_queue"],
    ));

    s.push_str("## Latency (p50 / p95 / worst)\n\n");
    s.push_str("| Action | p50 | p95 | worst | Target (p95) | Verdict |\n");
    s.push_str("|---|--:|--:|--:|--:|:--|\n");
    md_row(&mut s, "Queue build (points-at-stake)", &m["queue_build"]);
    md_row(&mut s, "Button press (grade ack)", &m["button_press"]);
    md_row(&mut s, "Next card after grading", &m["next_card"]);
    md_row(&mut s, "Dashboard load (per-topic mastery)", &m["dashboard_load"]);
    md_row(&mut s, "Dashboard refresh (scores recompute)", &m["dashboard_refresh"]);
    md_row(&mut s, "Cold start (spawn → first queue ready)", &m["cold_start"]);
    s.push('\n');

    // Sync
    s.push_str("## Sync (Anki's own protocol)\n\n");
    let sync = &doc["sync"];
    if sync["available"].as_bool() == Some(true) {
        s.push_str(&format!("_{}_\n\n", sync["note"].as_str().unwrap_or("")));
        s.push_str("| Sync operation | Value | Target | Verdict |\n|---|--:|--:|:--|\n");
        let fu = &sync["full_upload"];
        s.push_str(&format!(
            "| Full upload of 50k collection ({:.1} MB) | {} ms | < {} ms | {} |\n",
            sync["collection_mb_on_disk"].as_f64().unwrap_or(0.0),
            fmt_num(&fu["value_ms"]),
            fmt_num(&fu["target_ms"]),
            verdict_badge(fu["verdict"].as_str()),
        ));
        let inc = &sync["incremental"]["stats"];
        if inc["available"].as_bool() == Some(true) {
            s.push_str(&format!(
                "| Incremental normal_sync p95 ({} review deltas pushed) | {} ms | < {} ms | {} |\n",
                sync["incremental"]["deltas_pushed"].as_u64().unwrap_or(0),
                fmt_num(&inc["p95"]),
                fmt_num(&inc["target_p95_ms"]),
                verdict_badge(inc["verdict"].as_str()),
            ));
        }
        s.push('\n');
    } else {
        s.push_str(&format!(
            "Sync not measured this run: {}\n\n",
            sync["reason"].as_str().unwrap_or("unavailable")
        ));
    }

    // Memory
    let mem = &doc["memory"];
    s.push_str("## Memory (50k-card collection)\n\n");
    s.push_str(&format!(
        "- **Stated ceiling:** {} MB\n- **Peak RSS holding+operating 50k:** {} MB — {}\n- **Peak RSS across full run** (incl. loopback sync + 2nd collection): {} MB\n\n",
        fmt_num(&mem["stated_limit_mb"]),
        fmt_num(&mem["peak_rss_mb"]),
        if mem["within_limit"].as_bool() == Some(true) { "✅ within limit" } else { "❌ over limit" },
        fmt_num(&mem["peak_rss_full_run_mb"]),
    ));

    s.push_str("\n## What's measured / caveats\n\n");
    if let Some(notes) = doc["notes"].as_array() {
        for n in notes {
            if let Some(t) = n.as_str() {
                s.push_str(&format!("- {t}\n"));
            }
        }
    }
    s.push_str("\n_Machine-readable numbers: `tools/mcat_bench/bench-results.json`._\n");
    s
}

fn md_row(s: &mut String, label: &str, metric: &Value) {
    if metric["available"].as_bool() != Some(true) {
        s.push_str(&format!("| {label} | — | — | — | — | not measured |\n"));
        return;
    }
    s.push_str(&format!(
        "| {} | {} ms | {} ms | {} ms | {} | {} |\n",
        label,
        fmt_num(&metric["p50"]),
        fmt_num(&metric["p95"]),
        fmt_num(&metric["worst"]),
        target_str(&metric["target_p95_ms"]),
        verdict_badge(metric["verdict"].as_str()),
    ));
}

fn target_str(v: &Value) -> String {
    match v.as_f64() {
        Some(t) => format!("< {t:.0} ms"),
        None => "—".to_string(),
    }
}

fn fmt_num(v: &Value) -> String {
    match v.as_f64() {
        Some(n) => {
            if n >= 100.0 {
                format!("{n:.0}")
            } else {
                format!("{n:.3}")
            }
        }
        None => "?".to_string(),
    }
}

fn verdict_badge(v: Option<&str>) -> String {
    match v {
        Some("PASS") => "✅ PASS".to_string(),
        Some("FAIL") => "❌ FAIL".to_string(),
        _ => "—".to_string(),
    }
}
