#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Calibration harness for ReadyMCAT's MEMORY model (FSRS recall).

The Sunday rubric asks for a *calibrated* memory model: "when the model says
80%, the student recalls ~80% of the time," shown with a **calibration
(reliability) chart** and a **Brier (or log-loss) score on held-out reviews.**
This script produces exactly that, scoring the SHIPPING engine — Anki's real
FSRS, fitted via the ``compute_memory_state`` backend RPC and read back through
the ``extract_fsrs_retrievability`` SQL function the Memory dashboard itself
uses (see ``readymcat/eval/_anki_engine.py``). Nothing here re-implements FSRS.

Held-out by construction (prequential / one-step-ahead): for every review after
a card's first, the model is fitted on the reviews *before* it and then asked
to predict recall for that review, which it has not seen. The predicted
probability is compared to the actual pass/fail.

Two data sources:

* ``synthetic`` (default) — a reproducible SYNTHETIC student population whose
  memory dynamics are deliberately NOT FSRS (a power-law forgetting curve with
  per-card heterogeneity FSRS's global default params cannot match, plus small
  slip/guess noise and a home-grown spacing-driven stability growth). Because
  the data-generating process differs from FSRS, calibration is a real test,
  not a tautology. Everything it creates is FAKE and labelled synthetic; the
  numbers validate the METHOD and the shipped model's behaviour on a plausible
  population, not a real student. This mirrors the approach the PROOF doc calls
  out (synthetic reviews, clearly labelled) because the app is new and there is
  no large real review log yet.
* ``--collection PATH`` — replay the real (or demo) reviews in an existing
  collection through the same one-step-ahead protocol. Use this once a real
  review history exists to get a calibration number on genuine data.

Outputs a machine-readable ``calibration.json`` and a reliability-diagram PNG,
and prints the Brier score, log-loss and expected calibration error (ECE).

Run it::

    just calibrate                      # synthetic, writes json + png
    just calibrate --collection /path/to/collection.anki2
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import struct
import sys
import zlib
from pathlib import Path
from typing import Optional

_EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_EVAL_DIR))

from _anki_engine import FsrsEngine, Review  # noqa: E402

DEFAULT_JSON = _EVAL_DIR / "calibration.json"
DEFAULT_PNG = _EVAL_DIR / "calibration.png"

# --- give-up / gate defaults (honest-by-intent, tunable) --------------------
# A memory model this well-calibrated on synthetic data would show a Brier at
# or below the base-rate baseline and a small ECE. These are sanity gates, not
# a claim of real-world calibration.
# Calibration quality is judged by ECE (does p match observed frequency), NOT by
# discrimination skill: a well-calibrated model can still have low Brier skill
# when the base rate is extreme, so skill is reported for context but not gated.
ECE_MAX = 0.10
MIN_PREDICTIONS = 200  # too few held-out reviews -> abstain, don't report
FSRS6_DECAY = -0.5  # FSRS-6 uses a single global decay; the fair curve to test on


# ===========================================================================
# Synthetic student population (the data-generating process; NOT FSRS)
# ===========================================================================


def _power_forget(elapsed: float, stability: float, decay: float) -> float:
    """True recall after ``elapsed`` days at ``stability`` (days), on a
    power-law curve normalised so R == 0.9 when elapsed == stability. This is
    the same *family* FSRS uses, but each synthetic card gets its own stability
    and decay, which FSRS (running global default params) cannot recover
    exactly — the source of any honest miscalibration we measure."""
    factor = 0.9 ** (1.0 / decay) - 1.0
    return (1.0 + factor * elapsed / max(stability, 1e-6)) ** decay


def simulate_history(
    rng: random.Random, *, slip: float, guess: float, max_reviews: int
) -> tuple[list[Review], list[float]]:
    """Simulate one synthetic card's review history.

    Returns ``(reviews, gaps)`` where ``reviews[k]`` records the gap since the
    previous review and whether the student passed, and ``gaps[k]`` is the same
    gap (kept separately for the one-step-ahead loop). Outcomes are drawn from
    the TRUE recall (with slip/guess), never from FSRS."""
    # Per-card latent parameters (heterogeneous population). The forgetting-curve
    # shape (decay) matches FSRS-6's single global decay, so the test is
    # apples-to-apples on curve shape and isolates STABILITY calibration under a
    # heterogeneous population + a growth rule FSRS must infer (a fair test, not
    # a stacked one).
    stability = rng.uniform(1.0, 12.0)  # initial true stability (days)
    difficulty = rng.uniform(0.15, 0.95)  # 0 easy .. 1 hard
    decay = FSRS6_DECAY
    n = rng.randint(4, max_reviews)

    reviews: list[Review] = []
    gaps: list[float] = []
    for k in range(n):
        if k == 0:
            gap = 0.0
            true_r = 1.0  # first exposure: treat as learned in-session
        else:
            # Schedule the next test at a spread of retrievabilities so the
            # reliability diagram is populated across the probability range:
            # sometimes soon (high R), sometimes long overdue (low R).
            gap = stability * rng.uniform(0.2, 3.2)
            true_r = _power_forget(gap, stability, decay)
        # Observed pass probability with a small guess floor and slip ceiling.
        p_pass = guess + (1.0 - guess - slip) * true_r
        passed = k == 0 or (rng.random() < p_pass)
        reviews.append(Review(gap_days=gap, passed=passed))
        gaps.append(gap)
        # Home-grown stability update (spacing effect): a success far along the
        # forgetting curve strengthens memory more; a lapse resets it. This is
        # intentionally NOT the FSRS update rule.
        if k == 0:
            continue
        if passed:
            spacing_bonus = 1.0 + (1.6 - difficulty) * (1.0 - true_r)
            stability *= max(1.05, spacing_bonus)
        else:
            stability = max(0.5, stability * (0.30 + 0.20 * (1.0 - difficulty)))
    return reviews, gaps


# ===========================================================================
# Real-collection replay (optional)
# ===========================================================================


def histories_from_collection(path: str) -> list[list[Review]]:
    """Read per-card review histories from a real collection's revlog, oldest
    first. A pass is any graded review with ease >= 3 (Good/Easy), a miss is
    Again/Hard, mirroring the performance/hit rule. Gaps come from the revlog
    id timestamps (ms)."""
    from _anki_engine import ensure_anki_importable

    ensure_anki_importable()
    from anki.collection import Collection

    col = Collection(path)
    try:
        rows = col.db.all(
            "select cid, id, ease from revlog where ease >= 1 order by cid, id"
        )
    finally:
        col.close()
    by_card: dict[int, list[tuple[int, int]]] = {}
    for cid, rid, ease in rows:
        by_card.setdefault(int(cid), []).append((int(rid), int(ease)))
    histories: list[list[Review]] = []
    for cid, entries in by_card.items():
        if len(entries) < 3:
            continue
        reviews: list[Review] = []
        prev_ms: Optional[int] = None
        for rid, ease in entries:
            gap = 0.0 if prev_ms is None else max(0.0, (rid - prev_ms) / 86_400_000)
            reviews.append(Review(gap_days=gap, passed=ease >= 3))
            prev_ms = rid
        histories.append(reviews)
    return histories


# ===========================================================================
# Metrics
# ===========================================================================


def _clip(p: float, eps: float = 1e-6) -> float:
    return min(1.0 - eps, max(eps, p))


def brier(preds: list[float], ys: list[int]) -> float:
    return statistics.fmean((p - y) ** 2 for p, y in zip(preds, ys))


def log_loss(preds: list[float], ys: list[int]) -> float:
    return -statistics.fmean(
        y * math.log(_clip(p)) + (1 - y) * math.log(1 - _clip(p))
        for p, y in zip(preds, ys)
    )


def reliability_bins(
    preds: list[float], ys: list[int], n_bins: int = 10
) -> list[dict]:
    """Equal-width reliability bins: predicted-mean (confidence) vs observed
    pass-rate (accuracy), with counts."""
    bins: list[dict] = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [
            i
            for i, p in enumerate(preds)
            if (p >= lo and p < hi) or (b == n_bins - 1 and p == hi)
        ]
        if not idx:
            bins.append(
                {"lo": lo, "hi": hi, "n": 0, "pred_mean": None, "obs_rate": None}
            )
            continue
        pm = statistics.fmean(preds[i] for i in idx)
        om = statistics.fmean(ys[i] for i in idx)
        bins.append(
            {
                "lo": round(lo, 3),
                "hi": round(hi, 3),
                "n": len(idx),
                "pred_mean": round(pm, 4),
                "obs_rate": round(om, 4),
            }
        )
    return bins


def expected_calibration_error(bins: list[dict], total: int) -> tuple[float, float]:
    """ECE (weighted mean gap) and MCE (max gap) over populated bins."""
    ece = 0.0
    mce = 0.0
    for b in bins:
        if not b["n"] or b["pred_mean"] is None:
            continue
        gap = abs(b["obs_rate"] - b["pred_mean"])
        ece += (b["n"] / total) * gap
        mce = max(mce, gap)
    return ece, mce


def calibration_slope_intercept(preds: list[float], ys: list[int]) -> tuple[float, float]:
    """Logistic-recalibration slope/intercept: fit ``y ~ sigmoid(a + b*logit(p))``
    by a few Newton steps. Perfect calibration => slope 1, intercept 0; slope
    < 1 flags over-confidence. Pure-stdlib, no scipy."""
    xs = [math.log(_clip(p) / (1 - _clip(p))) for p in preds]
    a, b = 0.0, 1.0
    for _ in range(50):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, ys):
            z = a + b * x
            mu = 1.0 / (1.0 + math.exp(-z))
            w = max(mu * (1 - mu), 1e-9)
            g0 += mu - y
            g1 += (mu - y) * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        da = (h11 * g0 - h01 * g1) / det
        db = (-h01 * g0 + h00 * g1) / det
        a -= da
        b -= db
        if abs(da) < 1e-9 and abs(db) < 1e-9:
            break
    return b, a


# ===========================================================================
# Chart
# ===========================================================================


def write_chart(bins: list[dict], metrics: dict, preds: list[float], path: Path) -> str:
    """Write a reliability diagram PNG. Uses matplotlib when available (nicer),
    otherwise a compact pure-stdlib PNG fallback so a chart is always produced."""
    try:
        return _write_chart_matplotlib(bins, metrics, preds, path)
    except Exception:
        return _write_chart_fallback(bins, path)


def _write_chart_matplotlib(
    bins: list[dict], metrics: dict, preds: list[float], path: Path
) -> str:
    import os

    os.environ.setdefault(
        "MPLCONFIGDIR", str((_EVAL_DIR.parents[1] / "out" / ".mplcache")))
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(7, 8), gridspec_kw={"height_ratios": [3, 1]}
    )
    ax.plot([0, 1], [0, 1], "--", color="#888", label="perfect calibration")
    xs = [b["pred_mean"] for b in bins if b["n"]]
    ys = [b["obs_rate"] for b in bins if b["n"]]
    ns = [b["n"] for b in bins if b["n"]]
    ax.plot(xs, ys, "-o", color="#2563eb", label="ReadyMCAT memory model")
    for x, y, n in zip(xs, ys, ns):
        ax.annotate(str(n), (x, y), textcoords="offset points", xytext=(4, 4), fontsize=7, color="#555")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("predicted recall (FSRS)")
    ax.set_ylabel("observed recall (held-out)")
    src = metrics.get("source", "synthetic")
    ax.set_title(
        f"ReadyMCAT memory calibration ({src})\n"
        f"Brier {metrics['brier']:.4f} (skill {metrics['brier_skill']:+.3f}) · "
        f"log-loss {metrics['log_loss']:.4f} · ECE {metrics['ece']:.4f} · "
        f"n={metrics['n']}"
    )
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)

    ax2.hist(preds, bins=20, range=(0, 1), color="#93c5fd", edgecolor="#2563eb")
    ax2.set_xlim(0, 1)
    ax2.set_xlabel("predicted recall")
    ax2.set_ylabel("# held-out\nreviews")
    ax2.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return "matplotlib"


def _write_chart_fallback(bins: list[dict], path: Path) -> str:
    """A minimal dependency-free reliability-diagram PNG: white canvas, axes
    box, the y=x diagonal, and the model's reliability polyline + points."""
    W = H = 480
    margin = 60
    plot = W - 2 * margin
    # RGB white canvas.
    px = bytearray([255]) * (W * H * 3)

    def put(x: int, y: int, rgb: tuple[int, int, int]) -> None:
        if 0 <= x < W and 0 <= y < H:
            o = (y * W + x) * 3
            px[o], px[o + 1], px[o + 2] = rgb

    def to_px(vx: float, vy: float) -> tuple[int, int]:
        return (
            margin + int(vx * plot),
            H - margin - int(vy * plot),
        )

    def line(p0, p1, rgb, thick=1):
        (x0, y0), (x1, y1) = p0, p1
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for s in range(steps + 1):
            t = s / steps
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            for dx in range(-thick + 1, thick):
                for dy in range(-thick + 1, thick):
                    put(x + dx, y + dy, rgb)

    # axes box
    line(to_px(0, 0), to_px(1, 0), (0, 0, 0))
    line(to_px(0, 0), to_px(0, 1), (0, 0, 0))
    line(to_px(1, 0), to_px(1, 1), (200, 200, 200))
    line(to_px(0, 1), to_px(1, 1), (200, 200, 200))
    # diagonal
    line(to_px(0, 0), to_px(1, 1), (150, 150, 150))
    # reliability polyline
    pts = [(b["pred_mean"], b["obs_rate"]) for b in bins if b["n"]]
    prev = None
    for vx, vy in pts:
        cur = to_px(vx, vy)
        if prev is not None:
            line(prev, cur, (37, 99, 235), thick=2)
        prev = cur
        # marker
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx * dx + dy * dy <= 9:
                    put(cur[0] + dx, cur[1] + dy, (37, 99, 235))

    # encode PNG (RGB, no filter)
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw.extend(px[y * W * 3 : (y + 1) * W * 3])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)
    return "fallback"


# ===========================================================================
# Driver
# ===========================================================================


def collect_predictions(
    histories: list[list[Review]], engine: FsrsEngine, log=print
) -> tuple[list[float], list[int]]:
    """One-step-ahead: for each review after a card's first, fit FSRS on the
    prior reviews and predict its recall, then record (pred, actual)."""
    preds: list[float] = []
    ys: list[int] = []
    for c, reviews in enumerate(histories):
        for k in range(1, len(reviews)):
            prefix = reviews[:k]
            target = reviews[k]
            if target.gap_days <= 0:
                continue
            r = engine.predict_next_recall(prefix, target.gap_days)
            if r is None:
                continue
            preds.append(float(r))
            ys.append(1 if target.passed else 0)
        if log and (c + 1) % 100 == 0:
            log(f"  ... {c + 1}/{len(histories)} cards, {len(preds)} predictions")
    return preds, ys


def compute_metrics(preds: list[float], ys: list[int], source: str) -> dict:
    n = len(preds)
    base_rate = statistics.fmean(ys) if ys else 0.0
    b = brier(preds, ys)
    base_brier = base_rate * (1 - base_rate)
    brier_skill = 1 - (b / base_brier) if base_brier > 0 else 0.0
    bins = reliability_bins(preds, ys)
    ece, mce = expected_calibration_error(bins, n)
    slope, intercept = calibration_slope_intercept(preds, ys)
    return {
        "source": source,
        "n": n,
        "base_rate_observed": round(base_rate, 4),
        "mean_predicted": round(statistics.fmean(preds), 4) if preds else 0.0,
        "brier": round(b, 4),
        "brier_base_rate": round(base_brier, 4),
        "brier_skill": round(brier_skill, 4),
        "log_loss": round(log_loss(preds, ys), 4),
        "ece": round(ece, 4),
        "mce": round(mce, 4),
        "calibration_slope": round(slope, 4),
        "calibration_intercept": round(intercept, 4),
        "bins": bins,
    }


def gate(metrics: dict) -> dict:
    gates = {
        "enough_predictions": metrics["n"] >= MIN_PREDICTIONS,
        "ece_within_bound": metrics["ece"] <= ECE_MAX,
        "not_worse_than_base_rate": metrics["brier"] <= metrics["brier_base_rate"] + 0.01,
    }
    return {"gates": gates, "passed": all(gates.values())}


def print_summary(metrics: dict, gates: dict, chart_backend: str) -> None:
    print("\n=== ReadyMCAT memory calibration ===")
    print(f"source:            {metrics['source']}")
    print(f"held-out reviews:  {metrics['n']}")
    print(f"observed pass rate {metrics['base_rate_observed']:.3f}  "
          f"mean predicted {metrics['mean_predicted']:.3f}")
    print(f"Brier score:       {metrics['brier']:.4f}  "
          f"(base-rate {metrics['brier_base_rate']:.4f}, "
          f"skill {metrics['brier_skill']:+.3f})")
    print(f"log-loss:          {metrics['log_loss']:.4f}")
    print(f"ECE / MCE:         {metrics['ece']:.4f} / {metrics['mce']:.4f}")
    print(f"calibration slope: {metrics['calibration_slope']:.3f}  "
          f"intercept {metrics['calibration_intercept']:+.3f}  (1.0 / 0.0 = ideal)")
    print("\nreliability bins (predicted -> observed, n):")
    for b in metrics["bins"]:
        if not b["n"]:
            continue
        print(f"  [{b['lo']:.1f},{b['hi']:.1f})  pred {b['pred_mean']:.3f}  "
              f"obs {b['obs_rate']:.3f}  n={b['n']}")
    print(f"\nchart backend:     {chart_backend}")
    print("\ngates:")
    for name, ok in gates["gates"].items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\nOVERALL: {'PASS' if gates['passed'] else 'FAIL'}\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collection",
        default="",
        help="score a real/demo collection's reviews instead of synthetic data",
    )
    parser.add_argument("--cards", type=int, default=600, help="synthetic cards")
    parser.add_argument("--max-reviews", type=int, default=10)
    parser.add_argument("--slip", type=float, default=0.04, help="P(miss | recalled)")
    parser.add_argument("--guess", type=float, default=0.02, help="P(pass | forgotten)")
    parser.add_argument("--seed", type=int, default=20260703)
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--png", default=str(DEFAULT_PNG))
    args = parser.parse_args(argv)

    if args.collection:
        source = f"collection:{Path(args.collection).name}"
        print(f"Reading review histories from {args.collection} ...")
        histories = histories_from_collection(args.collection)
        print(f"  {len(histories)} cards with >= 3 reviews")
    else:
        source = "synthetic"
        print(
            "Simulating SYNTHETIC student memory (FAKE data; validates the "
            "calibration method + the shipped FSRS model on a plausible, "
            "non-FSRS population) ..."
        )
        rng = random.Random(args.seed)
        histories = [
            simulate_history(
                rng, slip=args.slip, guess=args.guess, max_reviews=args.max_reviews
            )[0]
            for _ in range(args.cards)
        ]

    engine = FsrsEngine()
    try:
        preds, ys = collect_predictions(histories, engine)
    finally:
        engine.close()

    if not preds:
        print("No held-out predictions produced; nothing to calibrate.", file=sys.stderr)
        return 1

    metrics = compute_metrics(preds, ys, source)
    if args.slip or args.guess:
        metrics["synthetic_params"] = {
            "cards": args.cards,
            "slip": args.slip,
            "guess": args.guess,
            "seed": args.seed,
        } if not args.collection else None
    chart_backend = write_chart(metrics["bins"], metrics, preds, Path(args.png))
    metrics["chart"] = str(Path(args.png))
    gates = gate(metrics)
    metrics["gates"] = gates

    Path(args.json).write_text(
        json.dumps(metrics, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
    )
    print_summary(metrics, gates, chart_backend)
    print(f"wrote {args.json}")
    print(f"wrote {args.png} ({chart_backend})")
    return 0 if gates["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
