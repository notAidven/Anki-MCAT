// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Generates a tiny sample `.anki2` collection for the ReadyMCAT iOS app, then
//! smoke-tests the exact protobuf dispatch path the Swift app uses
//! (`Backend::run_service_method`) so we know the service/method indices and
//! message shapes are correct before wiring up Swift.
//!
//! Usage: `sample_deck <out.anki2>` (defaults to `sample.anki2`).

use std::path::PathBuf;
use std::time::SystemTime;
use std::time::UNIX_EPOCH;

use anki::backend::init_backend;
use anki::backend::Backend;
use anki::collection::CollectionBuilder;
use anki::prelude::*;
use anki::version::buildhash;
use anki_proto::card_rendering::rendered_template_node::Value as NodeValue;
use anki_proto::card_rendering::RenderCardResponse;
use anki_proto::card_rendering::RenderExistingCardRequest;
use anki_proto::card_rendering::RenderedTemplateNode;
use anki_proto::collection::OpenCollectionRequest;
use anki_proto::scheduler::card_answer::Rating;
use anki_proto::scheduler::CardAnswer;
use anki_proto::scheduler::GetQueuedCardsRequest;
use anki_proto::scheduler::QueuedCards;
use prost::Message;

// Service / method indices, mirrored from the generated
// out/pylib/anki/_backend_generated.py (the authoritative client index source).
// These are the SAME numbers the Swift app uses.
const SVC_COLLECTION: u32 = 3;
const M_OPEN_COLLECTION: u32 = 0;
const SVC_SCHEDULER: u32 = 13;
const M_GET_QUEUED_CARDS: u32 = 3;
const M_ANSWER_CARD: u32 = 4;
const SVC_CARD_RENDERING: u32 = 27;
const M_RENDER_EXISTING_CARD: u32 = 6;

/// A handful of MCAT-flavoured Basic cards (front, back).
const SAMPLE_CARDS: &[(&str, &str)] = &[
    (
        "Which ion's electrochemical gradient across the inner mitochondrial membrane directly drives ATP synthase?",
        "The proton (H<sup>+</sup>) gradient established by the electron transport chain.",
    ),
    (
        "In Michaelis–Menten kinetics, what does K<sub>m</sub> represent?",
        "The substrate concentration at which the reaction rate is half of V<sub>max</sub> (an inverse measure of enzyme–substrate affinity).",
    ),
    (
        "A weak acid has pKa 4.8. At blood pH 7.4, is it mostly protonated or deprotonated?",
        "Mostly deprotonated — pH &gt; pKa, so by Henderson–Hasselbalch the conjugate base dominates.",
    ),
    (
        "What part of the nephron is primarily responsible for establishing the medullary osmotic gradient?",
        "The loop of Henle (countercurrent multiplier).",
    ),
    (
        "In classical conditioning, what is it called when a conditioned response reappears after a rest period following extinction?",
        "Spontaneous recovery.",
    ),
];

fn main() {
    let out_path =
        PathBuf::from(std::env::args().nth(1).unwrap_or_else(|| "sample.anki2".to_string()));
    if out_path.exists() {
        std::fs::remove_file(&out_path).ok();
    }
    // A fresh on-disk media db/folder for this collection.
    let media_folder = out_path.with_extension("media");
    let media_db = with_suffix(&out_path, ".media.db");
    std::fs::create_dir_all(&media_folder).expect("create media folder");

    // ---- Phase 1: author the collection with the high-level Rust API ----
    {
        let mut builder = CollectionBuilder::new(out_path.clone());
        builder.set_media_paths(media_folder.clone(), media_db.clone());
        let mut col = builder.build().expect("build collection");

        // A newly created collection already has the stock "Basic" notetype and
        // the Default deck (see storage::sqlite create path).
        let basic = col
            .get_notetype_by_name("Basic")
            .expect("query notetype")
            .expect("Basic notetype present in fresh collection");

        for (front, back) in SAMPLE_CARDS {
            let mut note = basic.new_note();
            note.set_field(0, *front).expect("set front");
            note.set_field(1, *back).expect("set back");
            col.add_note(&mut note, DeckId(1)).expect("add note");
        }
        println!(
            "[phase 1] wrote {} Basic notes to {}",
            SAMPLE_CARDS.len(),
            out_path.display()
        );
        // dropping `col` closes the collection cleanly.
    }

    // ---- Phase 2: drive the SAME path the iOS app drives, via protobuf ----
    // Run the smoke test against a throwaway COPY so the shipped deck stays
    // pristine (all cards new).
    let smoke_path = with_suffix(&out_path, ".smoke.anki2");
    let smoke_media_folder = smoke_path.with_extension("media");
    let smoke_media_db = with_suffix(&smoke_path, ".media.db");
    std::fs::copy(&out_path, &smoke_path).expect("copy collection for smoke test");
    std::fs::create_dir_all(&smoke_media_folder).expect("create smoke media folder");

    let backend = init_backend(&[]).expect("init backend");

    let open = OpenCollectionRequest {
        collection_path: path_str(&smoke_path),
        media_folder_path: path_str(&smoke_media_folder),
        media_db_path: path_str(&smoke_media_db),
    };
    run(&backend, SVC_COLLECTION, M_OPEN_COLLECTION, &open.encode_to_vec())
        .expect("open_collection");
    println!("[phase 2] opened collection via FFI dispatch");

    let req = GetQueuedCardsRequest {
        fetch_limit: 10,
        intraday_learning_only: false,
    };
    let bytes = run(&backend, SVC_SCHEDULER, M_GET_QUEUED_CARDS, &req.encode_to_vec())
        .expect("get_queued_cards");
    let queued = QueuedCards::decode(bytes.as_slice()).expect("decode QueuedCards");
    println!(
        "[phase 2] queued: {} new / {} learning / {} review",
        queued.new_count, queued.learning_count, queued.review_count
    );
    let first = queued.cards.first().expect("a queued card");
    let card = first.card.as_ref().expect("card present");
    let states = first.states.clone().expect("states present");

    let rreq = RenderExistingCardRequest {
        card_id: card.id,
        browser: false,
        partial_render: false,
    };
    let bytes = run(
        &backend,
        SVC_CARD_RENDERING,
        M_RENDER_EXISTING_CARD,
        &rreq.encode_to_vec(),
    )
    .expect("render_existing_card");
    let render = RenderCardResponse::decode(bytes.as_slice()).expect("decode RenderCardResponse");
    let question = assemble(&render.question_nodes);
    let answer = assemble(&render.answer_nodes);
    println!("[phase 2] question: {}", truncate(&question, 90));
    println!("[phase 2] answer:   {}", truncate(&answer, 90));
    assert!(!question.is_empty(), "rendered question should be non-empty");
    assert!(!answer.is_empty(), "rendered answer should be non-empty");

    let answer_msg = CardAnswer {
        card_id: card.id,
        current_state: states.current.clone(),
        new_state: states.good.clone(),
        rating: Rating::Good as i32,
        answered_at_millis: now_millis(),
        milliseconds_taken: 2500,
    };
    run(&backend, SVC_SCHEDULER, M_ANSWER_CARD, &answer_msg.encode_to_vec())
        .expect("answer_card");
    println!("[phase 2] answered first card 'Good'");

    let bytes = run(&backend, SVC_SCHEDULER, M_GET_QUEUED_CARDS, &req.encode_to_vec())
        .expect("get_queued_cards 2");
    let queued2 = QueuedCards::decode(bytes.as_slice()).expect("decode QueuedCards 2");
    println!(
        "[phase 2] after grading: {} new remaining",
        queued2.new_count
    );

    // Clean up the throwaway smoke-test copy; the shipped deck is untouched.
    drop(backend);
    std::fs::remove_file(&smoke_path).ok();
    std::fs::remove_file(&smoke_media_db).ok();
    std::fs::remove_dir_all(&smoke_media_folder).ok();

    println!("buildhash = {}", buildhash());
    println!("SMOKE TEST OK");
}

/// Invoke a single backend command, returning the response bytes or a stringy
/// error (the error path encodes a BackendError protobuf, which we don't need
/// to decode for the smoke test).
fn run(backend: &Backend, service: u32, method: u32, input: &[u8]) -> Result<Vec<u8>, String> {
    backend
        .run_service_method(service, method, input)
        .map_err(|e| format!("backend error ({} bytes)", e.len()))
}

/// Flatten rendered template nodes into a single HTML string. When
/// `partial_render` is false the backend has already substituted every field,
/// so we just concatenate literal text and each replacement's current_text.
fn assemble(nodes: &[RenderedTemplateNode]) -> String {
    let mut out = String::new();
    for node in nodes {
        match &node.value {
            Some(NodeValue::Text(t)) => out.push_str(t),
            Some(NodeValue::Replacement(r)) => out.push_str(&r.current_text),
            None => {}
        }
    }
    out
}

fn path_str(p: &PathBuf) -> String {
    p.to_string_lossy().to_string()
}

fn with_suffix(path: &PathBuf, suffix: &str) -> PathBuf {
    let mut s = path.to_string_lossy().to_string();
    // strip the .anki2 extension, then append the suffix
    if let Some(stripped) = s.strip_suffix(".anki2") {
        s = stripped.to_string();
    }
    PathBuf::from(format!("{s}{suffix}"))
}

fn now_millis() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as i64
}

fn truncate(s: &str, max: usize) -> String {
    let one_line = s.replace('\n', " ");
    if one_line.chars().count() <= max {
        one_line
    } else {
        let cut: String = one_line.chars().take(max).collect();
        format!("{cut}…")
    }
}
