#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Three-build ablation for ReadyMCAT's study feature (teach-on-miss), at EQUAL
STUDY TIME.

The Sunday rubric (section 8) asks for the chosen study feature to be tested
with three builds at equal study time:

* **A — teach-on-miss ON**  : on a miss the student does a retrieval-first
  correction (guiding sub-questions) instead of being handed the answer, and the
  corrected concept is resurfaced (spaced) via the points-at-stake "struggling"
  boost.
* **B — teach-on-miss OFF** : the same app (points-at-stake ordering) but a miss
  just reveals the answer (passive restudy); no ladder, no resurfacing.
* **C — plain Anki**        : default deck order + short relearning step on a
  miss (massed), no points-at-stake ordering, no ladder.

The pre-registered primary metric (PRD): the **corrected-concept re-retrieval
rate** — of concepts missed at least once, the share correctly retrieved at the
final test — plus overall retention accuracy. All three arms get the SAME total
study-time budget, which is the fair, hard part: the ladder costs time, so ON
completes FEWER exposures in the same minutes. If that time cost outweighs the
retrieval-practice benefit, ON will NOT win — and this harness reports that
honestly.

Honesty note
------------
There is no human cohort yet, so this is a MECHANISTIC SIMULATION with explicit,
literature-informed effect sizes (retrieval practice > passive restudy; a ladder
costs more seconds than reading an answer). It is not a human RCT. Its value is
(a) turning the instrumentation into a runnable fair test, (b) reporting the
three-arm outcome at equal time, and (c) a sensitivity sweep showing WHERE the
feature helps and where it does not. All assumptions are printed and saved.
If a real ``readymcat_teach_on_miss_log.jsonl`` is present, its instrumented
counts are summarized alongside the simulation.

Run it::

    just ablation
    just ablation --students 400 --time-budget 1800
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Optional

_EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_JSON = _EVAL_DIR / "ablation.json"
DEFAULT_PNG = _EVAL_DIR / "ablation.png"


# ===========================================================================
# Learner + scheduler simulation
# ===========================================================================


class Params:
    def __init__(self, **kw) -> None:
        self.n_concepts = kw.get("n_concepts", 40)
        self.time_budget = kw.get("time_budget", 1800.0)  # seconds per student
        self.t_review = kw.get("t_review", 8.0)  # a normal graded attempt
        self.t_read = kw.get("t_read", 6.0)  # reading the answer on a miss (B/C)
        self.t_ladder = kw.get("t_ladder", 22.0)  # retrieval-first ladder on a miss (A)
        self.a_success = kw.get("a_success", 0.12)  # gain from a correct retrieval
        self.a_retrieval = kw.get("a_retrieval", 0.30)  # gain from ladder correction (A)
        self.a_restudy = kw.get("a_restudy", 0.15)  # gain from passive restudy (B/C)
        self.decay_per_min = kw.get("decay_per_min", 0.010)  # forgetting per study-minute
        self.x0_low = kw.get("x0_low", 0.05)
        self.x0_high = kw.get("x0_high", 0.35)
        self.spacing_gap = kw.get("spacing_gap", 90.0)  # A: resurface a miss after N s
        self.plain_relearn_gap = kw.get("plain_relearn_gap", 20.0)  # C: massed relearn

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class Concept:
    __slots__ = ("x", "missed", "not_before", "last_seen")

    def __init__(self, x: float) -> None:
        self.x = x  # current recall probability
        self.missed = False  # ever missed during study
        self.not_before = 0.0  # earliest clock time it may be picked again
        self.last_seen = 0.0


def _decay(c: Concept, now: float, p: Params) -> None:
    dt_min = max(0.0, (now - c.last_seen)) / 60.0
    c.x *= math.exp(-p.decay_per_min * dt_min)
    c.last_seen = now


def run_arm(arm: str, p: Params, rng: random.Random) -> dict:
    """Simulate one student under ``arm`` in {"A_on","B_off","C_plain"} until the
    time budget is spent. Returns per-student metrics."""
    concepts = [Concept(rng.uniform(p.x0_low, p.x0_high)) for _ in range(p.n_concepts)]
    clock = 0.0
    exposures = 0
    misses = 0
    rr_deck_idx = 0  # plain-Anki round-robin pointer
    relearn_queue: list[tuple[float, int]] = []  # plain: one-shot massed relearn steps

    def pick() -> Optional[int]:
        nonlocal rr_deck_idx
        if arm == "C_plain":
            # default deck order; a just-missed card gets ONE massed relearning
            # step (Anki learning step) then rejoins the deck cycle. No weakness
            # targeting and no teach-on-miss resurfacing.
            if relearn_queue and relearn_queue[0][0] <= clock:
                return relearn_queue.pop(0)[1]
            i = rr_deck_idx % p.n_concepts
            rr_deck_idx += 1
            return i
        # A/B: points-at-stake — study the weakest first. A also boosts a
        # resurfaced (struggling) concept once its spacing gap has elapsed.
        best_i, best_score = None, -1.0
        for i, c in enumerate(concepts):
            if c.not_before > clock:
                continue
            weakness = 1.0 - c.x
            score = weakness
            if arm == "A_on" and c.missed:
                score = weakness * 1.8  # struggling resurfacing boost
            if score > best_score:
                best_score, best_i = score, i
        return best_i

    while clock < p.time_budget:
        i = pick()
        if i is None:
            break
        c = concepts[i]
        _decay(c, clock, p)
        recalled = rng.random() < c.x
        exposures += 1
        if recalled:
            c.x += p.a_success * (1.0 - c.x)
            clock += p.t_review
            c.not_before = clock
        else:
            misses += 1
            c.missed = True
            if arm == "A_on":
                c.x += p.a_retrieval * (1.0 - c.x)  # retrieval-first correction
                clock += p.t_review + p.t_ladder
                c.not_before = clock + p.spacing_gap  # spaced resurfacing
            elif arm == "B_off":
                c.x += p.a_restudy * (1.0 - c.x)  # passive restudy
                clock += p.t_review + p.t_read
                c.not_before = clock
            else:  # C_plain
                c.x += p.a_restudy * (1.0 - c.x)
                clock += p.t_review + p.t_read
                c.not_before = clock + p.plain_relearn_gap  # short massed relearn
        c.last_seen = clock

    # Final test: decay to a common horizon, then expected retention.
    horizon = p.time_budget + 60.0
    for c in concepts:
        _decay(c, horizon, p)
    retention = statistics.fmean(c.x for c in concepts)
    corrected = [c for c in concepts if c.missed]
    reretrieval = statistics.fmean(c.x for c in corrected) if corrected else float("nan")
    return {
        "retention": retention,
        "reretrieval_rate": reretrieval,
        "exposures": exposures,
        "misses": misses,
        "corrected_concepts": len(corrected),
    }


def _mean_ci(vals: list[float]) -> tuple[float, float, float]:
    vals = [v for v in vals if not math.isnan(v)]
    if not vals:
        return (float("nan"), float("nan"), float("nan"))
    m = statistics.fmean(vals)
    if len(vals) < 2:
        return (m, m, m)
    sd = statistics.stdev(vals)
    half = 1.96 * sd / math.sqrt(len(vals))
    return (m, m - half, m + half)


def run_sim(p: Params, students: int, seed: int) -> dict:
    arms = ["A_on", "B_off", "C_plain"]
    raw = {a: {"retention": [], "reretrieval_rate": [], "exposures": [], "misses": [], "corrected_concepts": []} for a in arms}
    for s in range(students):
        for a in arms:
            # Same student seed across arms => same initial strengths & draws,
            # isolating the policy difference (paired design).
            rng = random.Random(seed * 100003 + s)
            m = run_arm(a, p, rng)
            for k, v in m.items():
                raw[a][k].append(v)
    out = {}
    for a in arms:
        ret_m, ret_lo, ret_hi = _mean_ci(raw[a]["retention"])
        rr_m, rr_lo, rr_hi = _mean_ci(raw[a]["reretrieval_rate"])
        out[a] = {
            "retention_mean": round(ret_m, 4),
            "retention_ci": [round(ret_lo, 4), round(ret_hi, 4)],
            "reretrieval_mean": round(rr_m, 4),
            "reretrieval_ci": [round(rr_lo, 4), round(rr_hi, 4)],
            "exposures_mean": round(statistics.fmean(raw[a]["exposures"]), 1),
            "misses_mean": round(statistics.fmean(raw[a]["misses"]), 1),
            "corrected_mean": round(statistics.fmean(raw[a]["corrected_concepts"]), 1),
        }
    return out


# ===========================================================================
# Sensitivity sweep
# ===========================================================================


def sensitivity(p: Params, students: int, seed: int) -> list[dict]:
    """Sweep the two knobs that decide whether the ladder pays off at equal
    time: its time cost and the retrieval-practice advantage over restudy."""
    grid = []
    for t_ladder in (12.0, 18.0, 24.0, 32.0):
        for a_retrieval in (0.20, 0.26, 0.32, 0.40):
            pp = Params(**{**p.as_dict(), "t_ladder": t_ladder, "a_retrieval": a_retrieval})
            res = run_sim(pp, students, seed)
            on = res["A_on"]["retention_mean"]
            off = res["B_off"]["retention_mean"]
            grid.append(
                {
                    "t_ladder": t_ladder,
                    "a_retrieval": a_retrieval,
                    "on_retention": on,
                    "off_retention": off,
                    "on_minus_off": round(on - off, 4),
                    "on_helps": on > off,
                }
            )
    return grid


# ===========================================================================
# Real instrumentation (optional)
# ===========================================================================


def summarize_log(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    starts = selfmarks = reattempts = generated = authored = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        ev = e.get("event", "")
        starts += ev == "ladder_start"
        selfmarks += ev == "self_mark"
        reattempts += ev == "reattempt"
        if e.get("source") == "generated":
            generated += 1
        elif e.get("source") == "authored":
            authored += 1
    return {
        "path": str(path),
        "ladder_start": starts,
        "self_mark": selfmarks,
        "reattempt": reattempts,
        "generated": generated,
        "authored": authored,
    }


# ===========================================================================
# Chart
# ===========================================================================


def write_chart(result: dict, path: Path) -> str:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        arms = ["A_on", "B_off", "C_plain"]
        labels = ["A: teach-on-miss ON", "B: OFF (answer)", "C: plain Anki"]
        ret = [result["arms"][a]["retention_mean"] for a in arms]
        ret_err = [
            [result["arms"][a]["retention_mean"] - result["arms"][a]["retention_ci"][0] for a in arms],
            [result["arms"][a]["retention_ci"][1] - result["arms"][a]["retention_mean"] for a in arms],
        ]
        rr = [result["arms"][a]["reretrieval_mean"] for a in arms]
        x = range(len(arms))
        fig, ax = plt.subplots(figsize=(7.5, 5))
        w = 0.38
        ax.bar([i - w / 2 for i in x], ret, w, yerr=ret_err, capsize=4,
               color="#2563eb", label="retention (all concepts)")
        ax.bar([i + w / 2 for i in x], rr, w, color="#f59e0b",
               label="re-retrieval (corrected concepts)")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_ylim(0, 1)
        ax.set_ylabel("probability")
        ax.set_title(
            "ReadyMCAT teach-on-miss ablation at EQUAL study time (SIMULATION)\n"
            f"budget {int(result['params']['time_budget'])}s · "
            f"{result['students']} simulated students"
        )
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, axis="y", alpha=0.25)
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
    parser.add_argument("--students", type=int, default=300)
    parser.add_argument("--concepts", type=int, default=40)
    parser.add_argument("--time-budget", type=float, default=1800.0)
    parser.add_argument("--t-ladder", type=float, default=22.0)
    parser.add_argument("--seed", type=int, default=20260703)
    parser.add_argument("--no-sweep", action="store_true")
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--png", default=str(DEFAULT_PNG))
    parser.add_argument(
        "--log",
        default=str(_EVAL_DIR.parent / "readymcat_teach_on_miss_log.jsonl"),
        help="optional real instrumentation log to summarize",
    )
    args = parser.parse_args(argv)

    p = Params(n_concepts=args.concepts, time_budget=args.time_budget, t_ladder=args.t_ladder)
    print(
        "Running teach-on-miss ablation (SIMULATION with stated effect sizes; "
        "not a human RCT) ..."
    )
    arms = run_sim(p, args.students, args.seed)
    sweep = [] if args.no_sweep else sensitivity(p, max(80, args.students // 3), args.seed)
    log = summarize_log(Path(args.log))

    on = arms["A_on"]
    off = arms["B_off"]
    plain = arms["C_plain"]
    on_beats_off = on["retention_mean"] > off["retention_mean"]
    on_beats_plain = on["retention_mean"] > plain["retention_mean"]
    # honest verdict
    if on_beats_off and on_beats_plain:
        verdict = (
            "teach-on-miss ON beats both OFF and plain Anki at equal study time "
            "on retention"
        )
    elif on_beats_plain and not on_beats_off:
        verdict = (
            "teach-on-miss ON beats plain Anki but NOT the feature-off build at "
            "equal time — the ladder's time cost offsets its retrieval benefit "
            "(a partial / null result, reported honestly)"
        )
    else:
        verdict = (
            "teach-on-miss ON does NOT win at equal study time under these "
            "assumptions (null result, reported honestly)"
        )
    frac_helps = (
        round(sum(1 for g in sweep if g["on_helps"]) / len(sweep), 3) if sweep else None
    )

    result = {
        "source": "mechanistic simulation (stated effect sizes; not a human RCT)",
        "students": args.students,
        "params": p.as_dict(),
        "primary_metric": "corrected-concept re-retrieval rate (+ overall retention)",
        "arms": arms,
        "on_minus_off_retention": round(on["retention_mean"] - off["retention_mean"], 4),
        "on_minus_plain_retention": round(on["retention_mean"] - plain["retention_mean"], 4),
        "on_minus_off_reretrieval": round(on["reretrieval_mean"] - off["reretrieval_mean"], 4),
        "verdict": verdict,
        "sensitivity_fraction_on_helps": frac_helps,
        "sensitivity": sweep,
        "instrumentation_log": log,
    }
    backend = write_chart(result, Path(args.png))
    result["chart"] = str(Path(args.png))
    Path(args.json).write_text(
        json.dumps(result, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
    )

    print("\n=== ReadyMCAT teach-on-miss ablation (equal study time) ===")
    print(f"students: {args.students}   concepts: {p.n_concepts}   "
          f"budget: {int(p.time_budget)}s   ladder cost: {p.t_ladder}s")
    print(f"\n{'arm':<22}{'retention':>12}{'re-retrieval':>14}{'exposures':>11}{'misses':>8}")
    for a, label in (("A_on", "A teach-on-miss ON"), ("B_off", "B OFF (answer)"), ("C_plain", "C plain Anki")):
        r = arms[a]
        print(f"{label:<22}{r['retention_mean']:>11.3f} "
              f"{r['reretrieval_mean']:>13.3f} {r['exposures_mean']:>10.1f} {r['misses_mean']:>7.1f}")
    print(f"\nON - OFF retention:   {result['on_minus_off_retention']:+.3f}")
    print(f"ON - plain retention: {result['on_minus_plain_retention']:+.3f}")
    print(f"ON - OFF re-retrieval:{result['on_minus_off_reretrieval']:+.3f}")
    if frac_helps is not None:
        print(f"sensitivity: ON beats OFF in {frac_helps*100:.0f}% of swept "
              f"(ladder-cost x retrieval-benefit) settings")
    if log:
        print(f"instrumentation log: {log['ladder_start']} ladder starts, "
              f"{log['reattempt']} reattempts, {log['generated']} generated / {log['authored']} authored")
    else:
        print("instrumentation log: none found yet (no live teach-on-miss sessions logged)")
    print(f"\nVERDICT: {verdict}")
    print(f"chart backend: {backend}")
    print(f"\nwrote {args.json}\nwrote {args.png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
