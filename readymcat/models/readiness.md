# Readiness model — one-page description

**Question it answers:** "If you sat the MCAT today, roughly where would you
land on the 472–528 scale?"

## What it is

Readiness is an **explicitly heuristic** projection that blends the other two
honest scores and maps them onto the MCAT total-score scale:

```
blend     = 0.6 · performance + 0.4 · memory
readiness = 472 + blend · (528 − 472)          # linear map onto 472–528
```

Performance is weighted more than Memory because first-attempt application is a
closer proxy for exam behavior than raw recall. The score is surfaced as a
**range**, propagated from the Memory and Performance intervals (not a single
point), and is **always labelled "heuristic."**

- **Inputs:** the Memory score and the Performance score (each with its interval).
- **Output:** a 472–528 range + the heuristic label.

## Give-up rule

Readiness is shown **only when BOTH** inputs clear their own thresholds:

- Memory: ≥ 200 graded reviews **and** ≥ 50% coverage, **and**
- Performance: ≥ 30 first attempts.

If either abstains, Readiness reads **"not enough data yet."** It never shows a
score off one signal alone.

## Honesty caveat

This is a **heuristic, not a validated concordance.** The 0.6/0.4 weights and the
linear scale map are a reasoned default, **not** fitted against real AAMC
outcomes (we have none). It is a directional "are you trending toward test-ready"
signal, explicitly marked as such in the UI — not a predicted scaled score. The
weights are the obvious first thing to calibrate once real score data exists.
