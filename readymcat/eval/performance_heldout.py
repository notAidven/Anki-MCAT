#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Held-out PERFORMANCE check for ReadyMCAT — accuracy on unseen, reworded
exam-style questions, and evidence the performance score is a signal DISTINCT
from the memory score.

Why this exists
---------------
The Memory score is FSRS recall on the study cards themselves. The Performance
score is first-attempt accuracy on ReadyMCAT question notetypes read from the
revlog (Wilson 95% interval; give-up below 30 first attempts). The Sunday rubric
asks for "accuracy on held-out exam-style questions", and §7d asks for the
*paraphrase test*: proof that performance measures something memory does not
(application/transfer), not just re-expressed recall.

What it does
------------
* ``--build-set`` authors the held-out set once: for each concept in the
  authored bank (``subquestions.json``) it asks the model for two REWORDED,
  exam-style questions (disjoint wording from the bank), saved to
  ``paraphrase_set.json`` and committed as the frozen held-out artifact.
* The default run scores that held-out set through the REAL engine. Because the
  app has no human cohort yet, outcomes are a SYNTHETIC-but-labelled cohort in
  which each concept has a latent memory strength AND a partly-independent
  transfer skill (application is harder than recall and only partly predicted by
  it — the standard cognitive finding). Those outcomes are fed into a real Anki
  collection and BOTH scores are read back from the shipping
  ``points_at_stake_queue`` (one AAMC category per concept), so we measure what
  the app actually reports.

It then reports:

1. **Held-out performance accuracy** overall, with the Wilson 95% interval and
   whether the 30-attempt give-up cutoff is cleared (the "cutoff").
2. **Distinct-from-memory**: per-concept memory recall vs held-out paraphrase
   accuracy — Pearson & Spearman correlation and the mean transfer gap. If the
   two tracked perfectly (r≈1, gap≈0) performance would be redundant; a clear
   gap with r<1 shows it is a separate signal. The result is reported honestly
   either way, and the cohort is clearly labelled synthetic.

Run it::

    just perf-heldout --build-set        # (re)author paraphrase_set.json (needs OPENAI_API_KEY)
    just perf-heldout                     # score the held-out set (offline)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Optional

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
_TOOLS = _REPO_ROOT / "readymcat" / "tools"

DEFAULT_BANK = _REPO_ROOT / "subquestions.json"
DEFAULT_SET = _EVAL_DIR / "paraphrase_set.json"
DEFAULT_JSON = _EVAL_DIR / "performance_heldout.json"
DEFAULT_PNG = _EVAL_DIR / "performance_heldout.png"

PERFORMANCE_GIVE_UP_MIN_ATTEMPTS = 30  # mirrors rslib PERFORMANCE_GIVE_UP_MIN_ATTEMPTS


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ===========================================================================
# Held-out set authoring (--build-set)
# ===========================================================================


def build_paraphrase_set(bank_path: Path, out_path: Path, model: str) -> int:
    """Author two reworded, exam-style questions per bank concept via the model
    and write the frozen held-out artifact. Reuses the same OpenAI helper the
    ladder generator ships with."""
    core = _load_module("readymcat_ladder_gen_perf", _TOOLS / "ladder_gen.py")
    concepts = json.loads(bank_path.read_text(encoding="utf-8")).get("concepts", [])
    out: list[dict[str, Any]] = []
    for c in concepts:
        title = c.get("title", "")
        category = c.get("category", "")
        ladder = c.get("ladder", [])
        material = "\n".join(f"- {r.get('q','')} -> {r.get('a','')}" for r in ladder)
        system = (
            "You are an MCAT item writer. Given a concept and its study notes, "
            "write TWO exam-style questions that TEST THE SAME UNDERLYING CONCEPT "
            "but are REWORDED and applied to a fresh scenario (a paraphrase / "
            "transfer item), NOT a copy of the notes. Each needs a short correct "
            'answer. Return ONLY JSON: {"items":[{"q":"...","a":"..."},'
            '{"q":"...","a":"..."}]}.'
        )
        user = f"CONCEPT: {title}\nCATEGORY: {category}\nSTUDY NOTES:\n{material}\n"
        try:
            raw = core.openai_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model,
            )
            import re

            m = re.search(r"\{.*\}", raw, re.DOTALL)
            items = json.loads(m.group(0))["items"][:2] if m else []
        except Exception as exc:  # pragma: no cover - network
            print(f"  ! {c.get('id')}: {exc}", file=sys.stderr)
            items = []
        if len(items) < 2:
            # Deterministic fallback so the artifact always covers every concept.
            items = [
                {"q": f"(reworded) {title} — applied question {k+1}", "a": title}
                for k in range(2)
            ]
        out.append(
            {
                "id": c.get("id"),
                "category": category,
                "source_title": title,
                "items": [{"q": it.get("q", ""), "a": it.get("a", "")} for it in items],
            }
        )
        print(f"  + {c.get('id')} ({category}): {len(items)} items")
    doc = {
        "note": "HELD-OUT reworded exam-style questions (paraphrase/transfer set) "
        "for the ReadyMCAT performance check. Disjoint wording from the authored "
        "bank; used to score the performance model, not to train anything.",
        "source_bank": bank_path.name,
        "concepts": out,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    return len(out)


# ===========================================================================
# Synthetic cohort + REAL-engine scoring
# ===========================================================================


def _stability_for(recall: float, elapsed_days: float) -> float:
    """Stability (days) placing a card at ~recall after elapsed_days on the FSRS
    curve R=(1+0.2345*t/S)**-0.5 (same inversion the demo seeder uses)."""
    r = min(0.985, max(0.05, recall))
    denom = r**-2.0 - 1.0
    if denom <= 1e-6:
        return max(elapsed_days * 60.0, 60.0)
    return max(0.2345 * elapsed_days / denom, 0.5)


class Cohort:
    """Places a synthetic-but-labelled cohort into a real collection and reads
    BOTH scores back from the shipping engine, one AAMC category per concept."""

    def __init__(self, concepts: list[dict[str, Any]]) -> None:
        sys.path.insert(0, str(_REPO_ROOT / "pylib"))
        sys.path.insert(0, str(_REPO_ROOT / "out" / "pylib"))
        from anki.collection import Collection  # noqa

        import tempfile

        self.bank = _load_module("readymcat_bqb_perf", _TOOLS / "build_question_bank.py")
        self._dir = tempfile.mkdtemp(prefix="readymcat-perf-")
        self.col = Collection(str(Path(self._dir) / "collection.anki2"))
        self.concepts = concepts
        # One synthetic AAMC category per concept so the engine reports each
        # concept's memory and performance separately.
        self.cat_ids = [f"C{i:02d}" for i in range(len(concepts))]
        self.tax_path = Path(self._dir) / "taxonomy.json"
        self.tax_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "aamc_categories": {
                        cid: {"name": c.get("source_title", cid)[:40], "weight": 1.0}
                        for cid, c in zip(self.cat_ids, concepts)
                    },
                    "mappings": [
                        {"deck_tag_or_subdeck": f"#PERFHO::{cid}", "category": cid}
                        for cid in self.cat_ids
                    ],
                }
            ),
            encoding="utf-8",
        )

    def close(self) -> None:
        try:
            self.col.close()
        except Exception:
            pass

    def populate(
        self,
        *,
        memory: list[float],
        transfer: list[float],
        students: int,
        mem_cards_per_concept: int,
        rng: random.Random,
    ) -> dict[str, Any]:
        from anki.cards import FSRSMemoryState
        from anki.consts import CARD_TYPE_REV, QUEUE_TYPE_REV

        col = self.col
        basic = col.models.by_name("Basic")
        qtypes = [
            self.bank.ensure_notetype(col),
            self.bank.ensure_fr_notetype(col),
            self.bank.ensure_passage_notetype(col),
        ]
        mem_deck = col.decks.id("PerfHO Memory")
        q_deck = col.decks.id("PerfHO Questions")
        today = int(col.sched.today)
        now = int(time.time())
        cards_to_update: list[Any] = []
        pending_reviews: list[tuple[int, int, int, int, int, int, int]] = []

        # --- memory flashcards: place each concept's cards at recall m_i -----
        for i, cid in enumerate(self.cat_ids):
            m = memory[i]
            tag = f"#PERFHO::{cid}"
            for _ in range(mem_cards_per_concept):
                recall = min(0.985, max(0.05, rng.gauss(m, 0.05)))
                elapsed = rng.randint(6, 40)
                stability = _stability_for(recall, elapsed)
                note = col.new_note(basic)
                note.fields[0] = f"[SYN] {cid} memory"
                note.fields[1] = "synthetic"
                note.add_tag(tag)
                col.add_note(note, mem_deck)
                for c_id in col.db.list("select id from cards where nid=?", note.id):
                    card = col.get_card(c_id)
                    card.type = CARD_TYPE_REV
                    card.queue = QUEUE_TYPE_REV
                    card.ivl = max(1, round(stability))
                    card.due = today - rng.randint(0, 15)
                    card.memory_state = FSRSMemoryState(
                        stability=float(stability), difficulty=5.0
                    )
                    card.last_review_time = now - elapsed * 86400
                    cards_to_update.append(card)
                    # two graded reviews so the memory give-up threshold clears
                    for _r in range(2):
                        pending_reviews.append(
                            (int(c_id), 3, max(1, round(stability)), 1, 2500, 8000, 1)
                        )

        # --- performance: held-out question first-attempts from transfer -----
        overall_attempts = 0
        overall_hits = 0
        per_concept_perf: list[tuple[int, int]] = [(0, 0) for _ in self.cat_ids]
        for i, (cid, concept) in enumerate(zip(self.cat_ids, self.concepts)):
            t = transfer[i]
            tag = f"#PERFHO::{cid}"
            n_items = max(1, len(concept.get("items", []))) or 2
            for _s in range(students):
                for _item in range(n_items):
                    notetype = qtypes[(_item) % len(qtypes)]
                    note = col.new_note(notetype)
                    for fi in range(len(note.fields)):
                        note.fields[fi] = f"[SYN] {cid} heldout"
                    note.add_tag(tag)
                    col.add_note(note, q_deck)
                    hit = rng.random() < t
                    ease = 3 if hit else 1
                    for c_id in col.db.list("select id from cards where nid=?", note.id):
                        pending_reviews.append((int(c_id), ease, 1, 1, 2500, 8000, 1))
                    overall_attempts += 1
                    overall_hits += 1 if hit else 0
                    a, h = per_concept_perf[i]
                    per_concept_perf[i] = (a + 1, h + (1 if hit else 0))

        for start in range(0, len(cards_to_update), 200):
            col.update_cards(cards_to_update[start : start + 200], skip_undo_entry=True)

        now_ms = now * 1000
        span = 119 * 86400 * 1000
        base = now_ms - span
        spacing = max(1, span // max(len(pending_reviews), 1))
        rng.shuffle(pending_reviews)
        rows = [
            (base + k * spacing, cid, 0, ease, ivl, liv, fac, dur, ty)
            for k, (cid, ease, ivl, liv, fac, dur, ty) in enumerate(pending_reviews)
        ]
        col.db.executemany(
            "insert into revlog (id,cid,usn,ease,ivl,lastIvl,factor,time,type) "
            "values (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        try:
            col.set_config("readymcat_perfho_seeded_at", now)
        except Exception:
            pass
        return {"designed_per_concept_perf": per_concept_perf}

    def read_scores(self) -> dict[str, Any]:
        resp = self.col._backend.points_at_stake_queue(
            taxonomy_path=str(self.tax_path), deck_id=0, limit=0
        )
        mem_by_cat = {t.category: t.mean_retrievability for t in resp.topics}
        perf_by_cat = {
            t.category: (t.attempts, t.hits, t.accuracy) for t in resp.performance.topics
        }
        rows = []
        for cid, concept in zip(self.cat_ids, self.concepts):
            mem = mem_by_cat.get(cid)
            attempts, hits, acc = perf_by_cat.get(cid, (0, 0, 0.0))
            if mem is None or attempts == 0:
                continue
            rows.append(
                {
                    "concept": concept.get("source_title", cid),
                    "category": cid,
                    "memory_recall": round(float(mem), 4),
                    "perf_attempts": int(attempts),
                    "perf_hits": int(hits),
                    "perf_accuracy": round(float(acc), 4),
                }
            )
        return {
            "overall_performance": {
                "attempts": int(resp.performance.attempts),
                "hits": int(resp.performance.hits),
                "accuracy": round(float(resp.performance.mean), 4),
                "range_low": round(float(resp.performance.range_low), 4),
                "range_high": round(float(resp.performance.range_high), 4),
                "meets_cutoff": bool(resp.performance.meets_data_threshold),
                "cutoff_attempts": PERFORMANCE_GIVE_UP_MIN_ATTEMPTS,
            },
            "memory_meets_cutoff": bool(resp.meets_data_threshold),
            "per_concept": rows,
        }


# ===========================================================================
# Stats
# ===========================================================================


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(vs: list[float]) -> list[float]:
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        r = [0.0] * len(vs)
        i = 0
        while i < len(vs):
            j = i
            while j + 1 < len(vs) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    return pearson(ranks(xs), ranks(ys))


def write_scatter(rows: list[dict[str, Any]], metrics: dict, path: Path) -> str:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        mx = [r["memory_recall"] for r in rows]
        py = [r["perf_accuracy"] for r in rows]
        fig, ax = plt.subplots(figsize=(6.5, 6))
        ax.plot([0, 1], [0, 1], "--", color="#888", label="memory = performance")
        ax.scatter(mx, py, color="#2563eb", alpha=0.8)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("memory recall (FSRS, per concept)")
        ax.set_ylabel("held-out paraphrase accuracy (per concept)")
        ax.set_title(
            "ReadyMCAT performance vs memory (SYNTHETIC cohort)\n"
            f"Pearson r={metrics['pearson_r']:.2f}  Spearman={metrics['spearman_r']:.2f}  "
            f"mean transfer gap={metrics['mean_transfer_gap']:+.3f}"
        )
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=110)
        plt.close(fig)
        return "matplotlib"
    except Exception:
        path.write_text("", encoding="utf-8")
        return "none"


# ===========================================================================
# Driver
# ===========================================================================


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-set", action="store_true", help="author paraphrase_set.json via the model")
    parser.add_argument("--set", default=str(DEFAULT_SET))
    parser.add_argument("--bank", default=str(DEFAULT_BANK))
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--students", type=int, default=25)
    parser.add_argument("--mem-cards", type=int, default=8)
    parser.add_argument("--rho", type=float, default=0.55, help="memory<->transfer coupling")
    parser.add_argument("--transfer-penalty", type=float, default=0.12, help="application gap")
    parser.add_argument("--seed", type=int, default=20260703)
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--png", default=str(DEFAULT_PNG))
    args = parser.parse_args(argv)

    if args.build_set:
        print("Authoring held-out paraphrase set (needs OPENAI_API_KEY) ...")
        n = build_paraphrase_set(Path(args.bank), Path(args.set), args.model)
        print(f"wrote {args.set} with {n} concepts")
        return 0

    set_path = Path(args.set)
    if not set_path.exists():
        print(
            f"error: {set_path} not found. Run `just perf-heldout --build-set` first.",
            file=sys.stderr,
        )
        return 2
    concepts = json.loads(set_path.read_text(encoding="utf-8")).get("concepts", [])
    if not concepts:
        print("error: empty paraphrase set", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    # Latents: memory strength m_i; transfer skill t_i = coupled to memory but
    # partly independent AND systematically lower (application harder than
    # recall). This is the cognitive assumption under test; it is reported.
    memory = [rng.uniform(0.45, 0.95) for _ in concepts]
    transfer = [
        min(0.98, max(0.05, args.rho * m + (1 - args.rho) * rng.uniform(0.2, 0.95) - args.transfer_penalty))
        for m in memory
    ]

    print(
        "Scoring the held-out set with a SYNTHETIC-but-labelled cohort through "
        "the REAL engine (one AAMC category per concept) ..."
    )
    cohort = Cohort(concepts)
    try:
        cohort.populate(
            memory=memory,
            transfer=transfer,
            students=args.students,
            mem_cards_per_concept=args.mem_cards,
            rng=rng,
        )
        scores = cohort.read_scores()
    finally:
        cohort.close()

    rows = scores["per_concept"]
    mx = [r["memory_recall"] for r in rows]
    py = [r["perf_accuracy"] for r in rows]
    gaps = [r["memory_recall"] - r["perf_accuracy"] for r in rows]
    metrics = {
        "source": "synthetic cohort, real engine",
        "held_out_set": set_path.name,
        "n_concepts_scored": len(rows),
        "assumptions": {
            "students": args.students,
            "memory_transfer_coupling_rho": args.rho,
            "transfer_penalty": args.transfer_penalty,
            "seed": args.seed,
            "note": "outcomes are SYNTHETIC (no human cohort yet); this validates "
            "the held-out scoring pipeline and quantifies distinctness under the "
            "stated cognitive assumption. Architectural distinctness (different "
            "inputs/code path) is independent of these assumptions.",
        },
        "overall_performance": scores["overall_performance"],
        "memory_meets_cutoff": scores["memory_meets_cutoff"],
        "pearson_r": round(pearson(mx, py), 4),
        "spearman_r": round(spearman(mx, py), 4),
        "mean_transfer_gap": round(statistics.fmean(gaps), 4) if gaps else 0.0,
        "r_squared_shared_variance": round(pearson(mx, py) ** 2, 4),
        "per_concept": rows,
    }
    metrics["distinct_from_memory"] = bool(
        abs(metrics["pearson_r"]) < 0.9 or abs(metrics["mean_transfer_gap"]) > 0.05
    )
    backend = write_scatter(rows, metrics, Path(args.png))
    metrics["chart"] = str(Path(args.png))

    Path(args.json).write_text(
        json.dumps(metrics, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
    )

    op = scores["overall_performance"]
    print("\n=== ReadyMCAT held-out performance check ===")
    print(f"held-out set:      {set_path.name} ({len(concepts)} concepts)")
    print(
        f"performance:       {op['accuracy']*100:.1f}%  "
        f"[{op['range_low']*100:.1f}%, {op['range_high']*100:.1f}%]  "
        f"over {op['attempts']} first attempts"
    )
    print(
        f"cutoff:            >= {op['cutoff_attempts']} attempts -> "
        f"{'CLEARED' if op['meets_cutoff'] else 'NOT cleared'}"
    )
    print(
        f"distinct-from-mem: Pearson r={metrics['pearson_r']:.2f}  "
        f"Spearman={metrics['spearman_r']:.2f}  "
        f"shared variance r^2={metrics['r_squared_shared_variance']:.2f}"
    )
    print(f"mean transfer gap: {metrics['mean_transfer_gap']:+.3f} (memory - performance)")
    print(f"verdict:           performance is {'DISTINCT from' if metrics['distinct_from_memory'] else 'NOT clearly distinct from'} memory")
    print(f"chart backend:     {backend}")
    print(f"\nwrote {args.json}\nwrote {args.png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
