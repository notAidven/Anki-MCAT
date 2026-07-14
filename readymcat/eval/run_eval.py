#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Eval harness for ReadyMCAT's teach-on-miss ladder generation.

The assignment requires an eval harness for the AI feature; the PRD defines
its contract: a generated ladder must be well-formed, must not simply hand
over the answer, must stay grounded in the card's own material, and must beat
a retrieval baseline. This harness measures exactly that over a held-out
golden set, using three layers:

1. Deterministic checks (schema, answer-leak, source-grounding) - reused
   verbatim from ``readymcat/tools/ladder_gen.py`` so the eval scores the SAME
   validators that gate production. Fully offline, reproducible.
2. LLM-as-judge - a stronger model scores each ladder on a pedagogical rubric
   (does it scaffold toward the answer via retrieval? one level? no leak? is
   every sub-answer correct and grounded?), catching the subtle "gives it
   away" and factually-wrong cases a bag-of-words check cannot. The judge is
   sanity-checked against a couple of hand-labelled examples.
3. Beats-a-baseline - the generated ladder is compared against the PRD's
   "keyword/vector baseline", implemented as TF-IDF cosine retrieval of the
   nearest *authored* ladder from ``subquestions.json``. The authored bank is
   written as ``{q, a}`` rungs, so each retrieved ladder is converted into the
   SAME multiple-choice shape the generator emits (``authored_to_mcq``: the
   authored sub-answer becomes the correct option + explanation, sibling rung
   answers become the distractors) before scoring - so the baseline is scored
   through the SAME layers (deterministic guardrails + judge) as the AI and the
   comparison is apples-to-apples under the MCQ schema.

From those layers the harness computes the two headline metrics the
assignment asks for, side-by-side for the AI generator and the baseline:

* **accuracy** - the fraction of cards whose ladder passes ALL deterministic
  guardrails AND the judge (score >= the pass bar, with no danger flagged);
* **wrong-answer rate** - the fraction whose ladder leaks the answer, is judged
  factually wrong / not grounded (off-topic), or fails to produce a usable
  ladder at all - the dangerous failure mode teach-on-miss must avoid.

Contamination: the generator prompt is zero-shot and never sees a golden card
as a few-shot example, and the baseline retrieves from the authored bank
(``subquestions.json``), disjoint from the held-out ids - so there is no
train/test leakage in our pipeline.

Run it with ``just eval`` (live, needs ``OPENAI_API_KEY``) or
``just eval --stub`` (offline, deterministic; proves the pipeline end-to-end
without any network call). Stdlib-only, loads the pure core by path.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Callable, Optional

_EVAL_DIR = Path(__file__).resolve().parent
_CORE_PATH = _EVAL_DIR.parent / "tools" / "ladder_gen.py"
_REPO_ROOT = _EVAL_DIR.parents[1]

DEFAULT_GOLDEN = _EVAL_DIR / "golden_set.json"
DEFAULT_BANK = _REPO_ROOT / "subquestions.json"

# Report-level gates (honest-by-intent, tunable - same spirit as the core's
# constants and the dashboard's give-up thresholds).
JUDGE_PASS_SCORE = 4  # a ladder "passes" quality at judge score >= 4 (of 5)
JUDGE_MEAN_BAR = 3.5
GROUNDING_PASS_RATE_BAR = 0.9
WIN_RATE_BAR = 0.5

# Below this grounding a ladder's sub-answers do not draw on the card at all,
# so they answer a *different* question - for a teach-on-miss ladder shown to a
# student who missed THIS card that is a dangerous, misleading (off-topic)
# failure. It is the relevance bar the retrieval baseline routinely fails.
RELEVANCE_FLOOR = 0.30

DEFAULT_GEN_MODEL = "gpt-4o-mini"
DEFAULT_JUDGE_MODEL = "gpt-4o"

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)
_WORD_RE = re.compile(r"[a-z0-9]+")


def _load_core() -> Any:
    spec = importlib.util.spec_from_file_location(
        "readymcat_ladder_gen_core_eval", _CORE_PATH
    )
    assert spec and spec.loader, f"cannot load core from {_CORE_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()

# A chat function: (messages, model) -> assistant text. Same shape the core
# uses, so real and stub paths are interchangeable.
ChatFn = Callable[[list[dict[str, str]], str], str]


# --- golden set --------------------------------------------------------------


def load_golden(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data.get("cards") if isinstance(data, dict) else data
    if not isinstance(cards, list) or not cards:
        raise ValueError(f"no cards in golden set at {path}")
    return cards


def context_for(card: dict[str, Any]) -> Any:
    return core.CardContext(
        card.get("question", ""),
        card.get("answer", ""),
        source=card.get("source", ""),
    )


# --- baseline: TF-IDF retrieval of the nearest AUTHORED ladder ---------------
#
# The PRD's "keyword/vector baseline": for a missed card, retrieve the nearest
# existing authored sub-question ladder from the bank (subquestions.json) and
# reuse its content. It has no notion of the missed card's own material, so its
# ladder is grounded in ANOTHER concept's source, not this card's - which is
# why it collapses on held-out cards with no close authored analog. The authored
# bank is ``{q, a}``; ``authored_to_mcq`` reshapes each retrieved ladder into the
# generator's MCQ shape (authored answer -> correct option + explanation; sibling
# answers -> distractors) so it is scored by the SAME guardrails + judge as the
# AI - the side-by-side is fair, and the baseline's weakness that shows through is
# genuine (off-topic grounding), not a format mismatch.


def _tokens(text: str) -> list[str]:
    """Lowercased content tokens (>= 3 chars, non-stopword), reusing the core's
    stopword set so the baseline and the guardrails tokenise identically."""
    return [
        tok
        for tok in _WORD_RE.findall((text or "").lower())
        if len(tok) >= 3 and tok not in core._STOPWORDS
    ]


class TfidfRetriever:
    """A tiny, deterministic TF-IDF cosine retriever over authored concepts."""

    def __init__(self, concepts: list[dict[str, Any]]) -> None:
        self.concepts = concepts
        self.docs: list[list[str]] = [self._concept_tokens(c) for c in concepts]
        n = len(self.docs)
        df: dict[str, int] = {}
        for doc in self.docs:
            for tok in set(doc):
                df[tok] = df.get(tok, 0) + 1
        # Smoothed idf so a term in every doc still carries a little weight.
        self.idf = {
            tok: math.log((n + 1) / (freq + 1)) + 1.0 for tok, freq in df.items()
        }
        self.doc_vecs = [self._vec(doc) for doc in self.docs]

    @staticmethod
    def _concept_tokens(concept: dict[str, Any]) -> list[str]:
        parts = [str(concept.get("title", ""))]
        for rung in concept.get("ladder", []):
            parts.append(str(rung.get("q", "")))
            parts.append(str(rung.get("a", "")))
        return _tokens(" ".join(parts))

    def _vec(self, tokens: list[str]) -> dict[str, float]:
        tf: dict[str, float] = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0.0) + 1.0
        return {tok: count * self.idf.get(tok, 0.0) for tok, count in tf.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        common = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def retrieve(self, query: str) -> tuple[Optional[dict[str, Any]], float]:
        qvec = self._vec(_tokens(query))
        best_i, best_sim = -1, 0.0
        for i, dvec in enumerate(self.doc_vecs):
            sim = self._cosine(qvec, dvec)
            if sim > best_sim:
                best_sim, best_i = sim, i
        if best_i < 0:
            return None, 0.0
        return self.concepts[best_i], best_sim


def load_bank_concepts(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    concepts = data.get("concepts", [])
    return [c for c in concepts if c.get("ladder") and c.get("title")]


# Generic, never-correct options used ONLY to pad a converted baseline rung up to
# the minimum option count when an authored ladder has too few rungs to supply
# enough sibling distractors. Grounding + answer-leak score the correct option
# only, so padding can neither inflate nor sink the baseline - it just keeps the
# rung schema-valid.
_BASELINE_PAD_DISTRACTORS = (
    "None of the above",
    "Cannot be determined from the information given",
    "None of these apply",
)


def authored_to_mcq(
    ladder: Optional[list[dict[str, Any]]],
) -> Optional[list[dict[str, Any]]]:
    """Convert an authored ``{q, a}`` ladder into the shipping MCQ shape.

    The retrieval baseline reuses the nearest authored ladder, but the bank is
    written as ``{q, a}`` rungs while the generator (and thus every guardrail)
    now speaks MCQ. To score the baseline through the SAME validators + judge as
    the AI, each rung becomes a multiple-choice question whose CORRECT option and
    explanation are the authored sub-answer ``a`` *verbatim*, and whose
    distractors are the OTHER rungs' authored answers - real, same-concept,
    plausible-but-wrong for THIS sub-question. Nothing is invented: the correct
    content is exactly the authored answer, so the baseline keeps its genuine
    strength on its own concept and its genuine weakness (ungrounded/off-topic)
    when the retrieved concept does not match the missed card. Distractors do not
    affect grounding or answer-leak (both score the correct option only); the
    generic pad options are used only when a ladder is too short to supply enough
    distractors. Returns ``None`` for empty/unusable input.
    """
    if not isinstance(ladder, list) or not ladder:
        return None
    rungs = [r for r in ladder if isinstance(r, dict)]
    answers = [str(r.get("a", "")).strip() for r in rungs]
    mcq: list[dict[str, Any]] = []
    for i, rung in enumerate(rungs):
        question = str(rung.get("q", "")).strip()
        correct = answers[i]
        if not question or not correct:
            continue
        # Distractors: sibling rungs' answers, de-duplicated case-insensitively
        # (matching check_schema) and capped so the option count stays within
        # [MIN_OPTIONS, MAX_OPTIONS].
        seen = {correct.lower()}
        distractors: list[str] = []
        for j, other in enumerate(answers):
            if j == i or not other or other.lower() in seen:
                continue
            seen.add(other.lower())
            distractors.append(other)
        options = [correct] + distractors[: core.MAX_OPTIONS - 1]
        for pad in _BASELINE_PAD_DISTRACTORS:
            if len(options) >= core.MIN_OPTIONS:
                break
            if pad.lower() not in {opt.lower() for opt in options}:
                options.append(pad)
        mcq.append(
            {
                "question": question,
                "options": options,
                "correctIndex": 0,
                "explanation": correct,
            }
        )
    return mcq or None


# --- LLM-as-judge ------------------------------------------------------------


def _empty_verdict(rationale: str) -> dict[str, Any]:
    """The verdict for a missing/unusable ladder: it leaks, is off-topic and
    dangerous, and passes nothing - so "failed to produce a usable ladder"
    counts as a wrong answer in the metrics."""
    return {
        "score": 0,
        "leaks": True,
        "factuallyWrong": False,
        "offTopic": True,
        "dangerous": True,
        "scaffolds": False,
        "grounded": False,
        "groundingScore": 0.0,
        "schemaOk": False,
        "rationale": rationale,
    }


def build_judge_messages(
    context: Any, ladder: list[dict[str, str]]
) -> list[dict[str, str]]:
    system = (
        "You are grading a teach-on-miss ladder: a set of guiding "
        "sub-questions meant to make a student RETRIEVE their way to an answer "
        "they got wrong, without being handed the answer. Judge ONLY the "
        "ladder's pedagogy and correctness, strictly.\n"
        "Score 1-5 where 5 = an excellent retrieval scaffold (ordered, each "
        "rung answerable, builds toward the answer, first rung does NOT reveal "
        "it, every sub-answer factually correct and grounded in the given "
        "material) and 1 = useless, factually wrong, or just restates the "
        "answer.\n"
        'Return ONLY JSON: {"score": <1-5>, "leaks": <true|false>, '
        '"factuallyWrong": <true|false>, "offTopic": <true|false>, '
        '"scaffolds": <true|false>, "grounded": <true|false>, '
        '"rationale": "<one sentence>"}. '
        '"leaks" is true if the FIRST rung gives away the final answer; '
        '"factuallyWrong" is true if any sub-answer is incorrect; "offTopic" '
        "is true if the ladder does not address this question."
    )
    user = (
        f"QUESTION: {context.question}\n\n"
        f"CORRECT ANSWER: {context.answer}\n\n"
        f"LADDER TO GRADE:\n{json.dumps(ladder, ensure_ascii=False, indent=2)}\n\n"
        "Grade it now as the JSON object described."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_judge(
    raw: str, context: Any, ladder: Optional[list[dict[str, str]]]
) -> dict[str, Any]:
    """Parse a judge completion, then re-derive the deterministic fields
    (grounding, schema) from the ladder itself rather than trusting the model
    for them - the model only supplies the pedagogy/correctness judgment."""
    match = _JSON_OBJ_RE.search(raw or "")
    if not match:
        return _empty_verdict("unparseable judge output")
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return _empty_verdict("unparseable judge JSON")
    try:
        score = max(0, min(5, int(round(float(data.get("score", 0))))))
    except (ValueError, TypeError):
        score = 0
    leak = bool(data.get("leaks", False))
    wrong = bool(data.get("factuallyWrong", False))
    off_topic = bool(data.get("offTopic", False))
    g = core.grounding_score(ladder, context) if ladder else 0.0
    return {
        "score": score,
        "leaks": leak,
        "factuallyWrong": wrong,
        "offTopic": off_topic,
        "dangerous": bool(leak or wrong or off_topic),
        "scaffolds": bool(data.get("scaffolds", score >= JUDGE_PASS_SCORE)),
        "grounded": g >= core.GROUNDING_MIN,
        "groundingScore": round(g, 3),
        "schemaOk": not core.check_schema(ladder),
        "rationale": str(data.get("rationale", "")),
    }


def judge_ladder(
    context: Any,
    ladder: Optional[list[dict[str, str]]],
    judge_chat: ChatFn,
    model: str,
) -> dict[str, Any]:
    if not ladder:
        return _empty_verdict("no ladder produced")
    messages = build_judge_messages(context, ladder)
    try:
        raw = judge_chat(messages, model)
    except Exception as exc:  # pragma: no cover - network
        return _empty_verdict(f"judge error: {exc}")
    return parse_judge(raw, context, ladder)


# --- stub chat fns (offline, deterministic) ----------------------------------


def _answer_from_prompt(messages: list[dict[str, str]]) -> str:
    """Recover the card's answer text from a generation prompt (stub only)."""
    user = messages[-1]["content"] if messages else ""
    match = re.search(
        r"reference only[^)]*\):\n(.+?)(?:\n\nCITED|\n\nWrite)", user, re.DOTALL
    )
    if match:
        return match.group(1).strip()
    return user


def stub_generator(messages: list[dict[str, str]], model: str) -> str:
    """Offline stand-in for the model: builds a small grounded, non-leaking
    MCQ ladder from answer keywords so the pipeline runs without a network
    call. Emits the SAME shape the shipping generator does
    (``{question, options, correctIndex, explanation}``) so the offline run
    exercises the production MCQ parser + guardrails. Not meant to be high
    quality - just deterministic and well-formed."""
    answer = _answer_from_prompt(messages)
    toks: list[str] = []
    seen: set[str] = set()
    for tok in _WORD_RE.findall(answer.lower()):
        if len(tok) >= 4 and tok not in seen:
            seen.add(tok)
            toks.append(tok)
    half = max(1, len(toks) // 2)
    first = " ".join(toks[:half]) or "the underlying concept"
    second = " ".join(toks[half : half * 2]) or "the remaining steps"
    # Correct option + explanation are drawn from the card's own answer (so the
    # deterministic grounding gate passes); the first rung only carries HALF the
    # answer tokens so it does not trip the answer-leak gate. Distractors are
    # deliberately ungrounded (grounding scores the correct option only).
    ladder = [
        {
            "question": "Which prerequisite idea does this question build on?",
            "options": [first, "an unrelated idea", "a different unrelated idea"],
            "correctIndex": 0,
            "explanation": first,
        },
        {
            "question": "How do those combine to reach the answer?",
            "options": ["an unrelated idea", second, "a different unrelated idea"],
            "correctIndex": 1,
            "explanation": second,
        },
    ]
    return json.dumps(ladder)


def stub_judge(messages: list[dict[str, str]], model: str) -> str:
    """Offline stand-in judge: scores via the deterministic validators plus the
    relevance floor, so a well-formed grounded non-leaking ladder scores high
    and a leaking or off-topic (retrieved-from-another-concept) baseline scores
    low. Deterministic - lets the whole harness run offline. Factual-correctness
    needs a real model, so the stub reports ``factuallyWrong`` False and leaves
    that signal to the live judge."""
    user = messages[-1]["content"]
    q = re.search(r"QUESTION: (.+?)\n\n", user, re.DOTALL)
    a = re.search(r"CORRECT ANSWER: (.+?)\n\n", user, re.DOTALL)
    lad = re.search(r"LADDER TO GRADE:\n(.+?)\n\nGrade it", user, re.DOTALL)
    context = core.CardContext(q.group(1) if q else "", a.group(1) if a else "")
    ladder = json.loads(lad.group(1)) if lad else []
    usable = [r for r in ladder if isinstance(r, dict)]
    problems = core.check_schema(ladder)
    leak = core.check_answer_leak(usable, context) if usable else False
    g = core.grounding_score(usable, context) if usable else 0.0
    grounded = g >= core.GROUNDING_MIN
    off_topic = g < RELEVANCE_FLOOR
    if problems:
        score, rationale = 1, "malformed ladder"
    elif leak:
        score, rationale = 2, "first rung hands over the answer"
    elif off_topic:
        score, rationale = 2, "sub-answers are not grounded in this card (off-topic)"
    elif not grounded:
        score, rationale = 3, "only weakly grounded in the card's material"
    else:
        first = usable[0]
        first_text = f"{first.get('question', '')} {core._correct_option(first)}"
        if core._containment(context.answer, first_text) < 0.4 and g >= 0.7:
            score, rationale = 5, "grounded retrieval-first scaffold; no leak"
        else:
            score, rationale = 4, "grounded scaffold toward the answer"
    return json.dumps(
        {
            "score": score,
            "leaks": leak,
            "factuallyWrong": False,
            "offTopic": off_topic,
            "scaffolds": score >= JUDGE_PASS_SCORE,
            "grounded": grounded,
            "rationale": f"stub judge (deterministic validator proxy): {rationale}",
        }
    )


# --- judge sanity check ------------------------------------------------------


def _calibration_cases() -> list[tuple[Any, list[dict[str, str]], bool]]:
    """A tiny hand-labelled set: (context, ladder, expected_pass). Used to
    sanity-check that the judge agrees with obvious human verdicts."""
    ctx = core.CardContext(
        "Why does hemoglobin bind oxygen cooperatively?",
        "Hemoglobin has four subunits; oxygen binding at one raises affinity at "
        "the others, giving a sigmoidal curve.",
    )
    good = [
        {"q": "How many subunits does hemoglobin have?", "a": "Four subunits."},
        {
            "q": "What happens to the other subunits when one binds oxygen?",
            "a": "Their affinity for oxygen increases.",
        },
    ]
    leaky = [
        {
            "q": "Why is binding cooperative?",
            "a": "Because oxygen binding at one subunit raises affinity at the "
            "others, giving a sigmoidal curve.",
        },
        {"q": "And so?", "a": "That is cooperativity."},
    ]
    return [(ctx, good, True), (ctx, leaky, False)]


def check_judge_calibration(judge_chat: ChatFn, model: str) -> dict[str, Any]:
    cases = _calibration_cases()
    agree = 0
    details = []
    for context, ladder, expected_pass in cases:
        verdict = judge_ladder(context, ladder, judge_chat, model)
        got_pass = verdict["score"] >= JUDGE_PASS_SCORE
        ok = got_pass == expected_pass
        agree += 1 if ok else 0
        details.append(
            {"expectedPass": expected_pass, "score": verdict["score"], "agree": ok}
        )
    return {"agreement": agree / len(cases), "cases": details}


# --- scoring one ladder ------------------------------------------------------


def _score(
    ladder: Optional[list[dict[str, str]]],
    det: dict[str, Any],
    verdict: dict[str, Any],
) -> dict[str, Any]:
    """Fold the deterministic report and the judge verdict for one ladder into
    the per-ladder record the metrics aggregate over.

    * ``passedCutoff`` (the accuracy numerator) - passes ALL deterministic
      guardrails AND the judge score clears the pass bar AND the judge sees no
      danger; only such ladders would ever be shown to a student.
    * ``dangerous`` (the wrong-answer numerator) - leaks the answer, is
      factually wrong, or is off-topic/not-grounded (or no ladder at all).
    """
    passed_cutoff = bool(
        det["passed"]
        and verdict["score"] >= JUDGE_PASS_SCORE
        and not verdict["dangerous"]
    )
    return {
        "ladder": ladder,
        "deterministic": det,
        "judge": verdict,
        "groundingScore": det["groundingScore"],
        "grounded": det["grounded"],
        "passedCutoff": passed_cutoff,
        "dangerous": bool(verdict["dangerous"]),
    }


# --- eval loop + aggregation -------------------------------------------------


def eval_card(
    card: dict[str, Any],
    gen_chat: ChatFn,
    judge_chat: ChatFn,
    gen_model: str,
    judge_model: str,
    retriever: TfidfRetriever,
) -> dict[str, Any]:
    context = context_for(card)

    # AI ladder: generated through the exact production path, then scored by
    # the production guardrails + judge.
    outcome = core.generate_ladder(context, chat_fn=gen_chat, model=gen_model)
    ai_det = (
        outcome.validation.as_dict()
        if outcome.validation
        else core.validate_ladder(outcome.ladder, context).as_dict()
    )
    ai_verdict = judge_ladder(context, outcome.ladder, judge_chat, judge_model)
    ai = _score(outcome.ladder, ai_det, ai_verdict)

    # Baseline ladder: nearest authored concept's ladder, reshaped into the same
    # MCQ form the generator emits and scored on THIS card by the identical
    # guardrails + judge.
    concept, sim = retriever.retrieve(
        f"{card.get('question', '')} {card.get('answer', '')}"
    )
    base_ladder = authored_to_mcq(concept.get("ladder")) if concept else None
    base_det = core.validate_ladder(base_ladder, context).as_dict()
    base_verdict = judge_ladder(context, base_ladder, judge_chat, judge_model)
    base = _score(base_ladder, base_det, base_verdict)
    base["retrievedConceptId"] = concept.get("id") if concept else None
    base["retrievedConceptTitle"] = concept.get("title") if concept else None
    base["similarity"] = round(sim, 3)

    return {
        "id": card.get("id"),
        "section": card.get("section"),
        "attempts": outcome.attempts,
        "error": outcome.error,
        "ai": ai,
        "baseline": base,
        "win": ai_verdict["score"] > base_verdict["score"],
    }


def _rate(values: list[bool]) -> float:
    return sum(1 for v in values if v) / len(values) if values else 0.0


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _side(items: list[dict[str, Any]]) -> dict[str, float]:
    """Compute the metrics for one column (AI or baseline)."""
    det = [it["deterministic"] for it in items]
    return {
        "accuracy": round(_rate([it["passedCutoff"] for it in items]), 3),
        "wrongAnswerRate": round(_rate([it["dangerous"] for it in items]), 3),
        "groundingMean": round(_mean([it["groundingScore"] for it in items]), 3),
        "groundingPassRate": round(_rate([it["grounded"] for it in items]), 3),
        "schemaPassRate": round(_rate([d["schemaOk"] for d in det]), 3),
        "answerLeakRate": round(_rate([d["answerLeak"] for d in det]), 3),
        "judgeMean": round(_mean([it["judge"]["score"] for it in items]), 3),
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    ai = [r["ai"] for r in results]
    base = [r["baseline"] for r in results]
    ai_s = _side(ai)
    base_s = _side(base)
    return {
        "n": len(results),
        # headline metrics, side-by-side (AI generator vs retrieval baseline)
        "accuracyGenerated": ai_s["accuracy"],
        "accuracyBaseline": base_s["accuracy"],
        "wrongAnswerRateGenerated": ai_s["wrongAnswerRate"],
        "wrongAnswerRateBaseline": base_s["wrongAnswerRate"],
        # grounding / schema / leak, side-by-side
        "groundingMean": ai_s["groundingMean"],
        "groundingMeanBaseline": base_s["groundingMean"],
        "groundingPassRate": ai_s["groundingPassRate"],
        "groundingPassRateBaseline": base_s["groundingPassRate"],
        "schemaPassRate": ai_s["schemaPassRate"],
        "schemaPassRateBaseline": base_s["schemaPassRate"],
        "answerLeakRate": ai_s["answerLeakRate"],
        "answerLeakRateBaseline": base_s["answerLeakRate"],
        # judge, side-by-side + generated pass-rate + head-to-head win-rate
        "judgeMeanGenerated": ai_s["judgeMean"],
        "judgeMeanBaseline": base_s["judgeMean"],
        "judgePassRate": round(
            _rate([it["judge"]["score"] >= JUDGE_PASS_SCORE for it in ai]), 3
        ),
        "winRateVsBaseline": round(_rate([r["win"] for r in results]), 3),
    }


def gate_report(agg: dict[str, Any]) -> dict[str, Any]:
    gates = {
        "schema_100pct": agg["schemaPassRate"] >= 1.0,
        "no_answer_leak": agg["answerLeakRate"] <= 0.0,
        "grounding_ok": agg["groundingPassRate"] >= GROUNDING_PASS_RATE_BAR,
        "judge_mean_ok": agg["judgeMeanGenerated"] >= JUDGE_MEAN_BAR,
        "ai_higher_accuracy": agg["accuracyGenerated"] > agg["accuracyBaseline"],
        "ai_lower_wrong_answer_rate": (
            agg["wrongAnswerRateGenerated"] < agg["wrongAnswerRateBaseline"]
        ),
        "beats_baseline": agg["winRateVsBaseline"] > WIN_RATE_BAR,
    }
    return {"gates": gates, "passed": all(gates.values())}


# --- human-readable summary --------------------------------------------------


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _winner(ai_val: float, base_val: float, *, higher_better: bool) -> str:
    if ai_val == base_val:
        return "tie"
    ai_better = (ai_val > base_val) if higher_better else (ai_val < base_val)
    return "AI" if ai_better else "baseline"


def print_summary(
    agg: dict[str, Any], gates: dict[str, Any], calib: dict[str, Any]
) -> None:
    acc_win = _winner(
        agg["accuracyGenerated"], agg["accuracyBaseline"], higher_better=True
    )
    war_win = _winner(
        agg["wrongAnswerRateGenerated"],
        agg["wrongAnswerRateBaseline"],
        higher_better=False,
    )
    ground_win = _winner(
        agg["groundingMean"], agg["groundingMeanBaseline"], higher_better=True
    )
    judge_win = _winner(
        agg["judgeMeanGenerated"], agg["judgeMeanBaseline"], higher_better=True
    )
    print("\n=== ReadyMCAT ladder-generation eval ===")
    print(f"cards evaluated:  {agg['n']}")
    print(
        "baseline:         TF-IDF retrieval of nearest authored ladder "
        "(subquestions.json)"
    )
    print()
    rows = [
        ("metric", "AI", "baseline", "winner"),
        ("-" * 30, "-" * 9, "-" * 9, "-" * 8),
        (
            "accuracy (guardrails+judge)",
            _pct(agg["accuracyGenerated"]),
            _pct(agg["accuracyBaseline"]),
            acc_win,
        ),
        (
            "wrong-answer rate",
            _pct(agg["wrongAnswerRateGenerated"]),
            _pct(agg["wrongAnswerRateBaseline"]),
            war_win,
        ),
        (
            "grounding (mean 0-1)",
            f"{agg['groundingMean']:.3f}",
            f"{agg['groundingMeanBaseline']:.3f}",
            ground_win,
        ),
        (
            "judge mean (of 5)",
            f"{agg['judgeMeanGenerated']:.2f}",
            f"{agg['judgeMeanBaseline']:.2f}",
            judge_win,
        ),
        (
            "win-rate (AI vs baseline)",
            _pct(agg["winRateVsBaseline"]),
            "-",
            "AI" if agg["winRateVsBaseline"] > WIN_RATE_BAR else "baseline",
        ),
    ]
    for name, a, b, w in rows:
        print(f"  {name:<30} {a:>9} {b:>9}  {w}")
    print()
    print(
        f"schema valid:   AI {_pct(agg['schemaPassRate'])} / "
        f"base {_pct(agg['schemaPassRateBaseline'])}      "
        f"answer-leak:  AI {_pct(agg['answerLeakRate'])} / "
        f"base {_pct(agg['answerLeakRateBaseline'])}"
    )
    print(
        f"grounding pass (>= {core.GROUNDING_MIN}):  "
        f"AI {_pct(agg['groundingPassRate'])} / "
        f"base {_pct(agg['groundingPassRateBaseline'])}   "
        f"judge pass (>= {JUDGE_PASS_SCORE}): {_pct(agg['judgePassRate'])}"
    )
    print(f"judge calibration:  {calib['agreement']:.0%} agreement with labels")
    print("\ngates:")
    for name, ok in gates["gates"].items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\nOVERALL: {'PASS' if gates['passed'] else 'FAIL'}\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN), help="golden set JSON")
    parser.add_argument(
        "--bank",
        default=str(DEFAULT_BANK),
        help="authored ladder bank (subquestions.json) for the retrieval baseline",
    )
    parser.add_argument("--gen-model", default=DEFAULT_GEN_MODEL)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="only the first N cards")
    parser.add_argument(
        "--stub",
        action="store_true",
        help="run fully offline with deterministic stub model + judge (no API "
        "call) - proves the harness end-to-end",
    )
    parser.add_argument("--report", default="", help="write the full JSON report here")
    args = parser.parse_args(argv)

    cards = load_golden(Path(args.golden))
    if args.limit > 0:
        cards = cards[: args.limit]

    if args.stub:
        gen_chat: ChatFn = stub_generator
        judge_chat: ChatFn = stub_judge
    else:
        gen_chat = core.openai_chat
        judge_chat = core.openai_chat

    retriever = TfidfRetriever(load_bank_concepts(Path(args.bank)))

    calib = check_judge_calibration(judge_chat, args.judge_model)
    results = [
        eval_card(
            card, gen_chat, judge_chat, args.gen_model, args.judge_model, retriever
        )
        for card in cards
    ]
    agg = aggregate(results)
    gates = gate_report(agg)
    print_summary(agg, gates, calib)

    report = {
        "mode": "stub" if args.stub else "live",
        "genModel": args.gen_model,
        "judgeModel": args.judge_model,
        "baseline": "TF-IDF retrieval of nearest authored ladder (subquestions.json)",
        "aggregate": agg,
        "gates": gates,
        "judgeCalibration": calib,
        "perCard": results,
    }
    if args.report:
        # indent=4 + trailing newline so the emitted report is dprint-clean
        # (matches .dprint.json's JSON indentWidth), keeping `just check` green
        # when the committed report.json is regenerated.
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )
        print(f"full report written to {args.report}")

    return 0 if gates["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
