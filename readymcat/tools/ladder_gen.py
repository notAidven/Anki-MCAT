#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Runtime generation of ReadyMCAT teach-on-miss ladders (the AI feature).

ReadyMCAT's spiky point of view (SPOV 1) is that showing a wrong-answer
explanation is passive reading; the fix is to make the student *retrieve* the
correction through guiding sub-questions. The bundled bank ships those
sub-questions authored by hand, but that only covers ReadyMCAT's own cards.
This module closes the gap the PRD flags as the #1 next step: when a student
misses a card that has **no authored ladder** (an imported/community deck, or
their own cards), generate a short, source-grounded guiding ladder at runtime
via an LLM, so teach-on-miss works on *any* deck.

Design (kept deliberately small and honest):

* This is the single **source of truth** shared by the desktop runtime
  (``qt/aqt/readymcat_ladder_gen.py``) and the eval harness
  (``readymcat/eval/``). The prompt, the parser and the guardrail validators
  live here so what ships is exactly what the eval scores — the harness can't
  drift from production.
* The OpenAI call is a thin ``urllib`` HTTPS request (no third-party
  dependency) and is **injectable** (``chat_fn``) so tests run fully offline
  and deterministically.
* The guardrails ARE the eval checks: a generated ladder must be well-formed
  (schema), must not simply hand over the answer on the first rung
  (answer-leak), and must stay grounded in the card's own material
  (source-grounding). These are lexical proxies chosen for the MVP — honest
  about being heuristics, not a calibrated model — and their thresholds are
  named constants the eval work can tune.

Each generated rung is a **multiple-choice question** so the student *works it
out* by choosing, not by reading: ``{"question", "options", "correctIndex",
"explanation"}``. The reviewer renders each rung interactively (select an
option -> immediate correct/incorrect feedback + a one-line explanation ->
advance), scaffolding toward the flashcard's answer while the real answer stays
hidden until the ladder is done (retrieve-before-reveal). The ``correctIndex``
is 0-based into ``options``; the distractors are plausible-but-wrong given the
card's own material.

Stdlib-only (no ``anki`` import), so its unit tests run without a built
backend, mirroring the other pure helpers under ``readymcat/tools/``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from html import unescape
from typing import Any, Callable, Optional

# --- Tunable, honest-by-intent constants ------------------------------------
#
# Chosen for the MVP, not derived from data (same spirit as the dashboard's
# give-up thresholds). The eval harness reports against these and they are the
# knobs the calibration work will turn.

#: Ladders shorter than this teach nothing; longer than this stop being a
#: "short ladder" and start drilling (the PRD's single-level rule).
MIN_RUNGS = 2
MAX_RUNGS = 4

#: Each guiding MCQ rung offers this many options. A stem with fewer than three
#: choices barely tests retrieval; more than four is noise for a scaffold rung.
MIN_OPTIONS = 3
MAX_OPTIONS = 4

#: A rung's correct option + explanation is considered grounded when at least
#: this fraction of its content words appear in the card's own material
#: (question + answer + source). A lexical containment proxy for "traces to a
#: named source". Distractors are intentionally wrong, so grounding scores the
#: correct answer + explanation only, never the distractors.
GROUNDING_MIN = 0.5

#: The FIRST rung must not already contain most of the final answer's content
#: words in its stem/correct option — otherwise the ladder just reveals the
#: answer instead of scaffolding toward it. Leak when containment of the answer
#: in rung 1 meets this.
ANSWER_LEAK_MAX = 0.7

#: A card must yield at least this many human-readable content words (after
#: :func:`clean_grounding_text` strips diagram/markup) for generation to be
#: attempted. Below it the card is effectively image-only — a pure diagram, an
#: image-occlusion mask, a bare media card — with nothing to ground a guiding
#: ladder in, so generation returns not-ok and the reviewer falls back to a
#: normal reveal instead of inventing questions about a picture it cannot read.
#: Honest heuristic, not a tuned value (same spirit as the thresholds above).
MIN_GROUNDING_TOKENS = 3

#: Cheap, capable default; the eval harness uses a stronger judge model.
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECS = 30
DEFAULT_ATTEMPTS = 2

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# Short, deliberately generic stopword set — enough to stop the lexical
# proxies keying on filler words, without pretending to be real NLP.
_STOPWORDS = frozenset(
    """
    the a an and or but if then than that this these those of to in on at for
    with without from by as is are was were be been being it its it's do does
    did done have has had having will would can could should may might must
    not no yes into onto over under about above below between which who whom
    whose what when where why how each any all both some such more most other
    another one two three you your they them their he she his her we our us
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_WS_RE = re.compile(r"\s+")


class CardContext:
    """The grounding material for one card, extracted from its fields.

    A plain class (not a ``@dataclass``) so it loads cleanly when this module
    is imported by path — the same deliberate choice the other ``readymcat``
    tools make (``@dataclass`` + ``from __future__ import annotations`` breaks
    under path-based import on 3.13).
    """

    def __init__(
        self,
        question: str,
        answer: str,
        *,
        source: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        self.question = (question or "").strip()
        self.answer = (answer or "").strip()
        self.source = (source or "").strip()
        self.tags = list(tags or [])

    @property
    def has_source(self) -> bool:
        """True when the card cites a real source; otherwise generation is
        grounded on the card's own answer text only (flagged 'card-only')."""
        return bool(self.source)

    @property
    def grounding_text(self) -> str:
        """All material a sub-answer is allowed to draw on."""
        return "\n".join(p for p in (self.question, self.answer, self.source) if p)

    def as_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "answer": self.answer,
            "source": self.source,
            "tags": self.tags,
            "hasSource": self.has_source,
        }


class ValidationResult:
    """Outcome of running the deterministic guardrails over a ladder."""

    def __init__(
        self,
        *,
        schema_problems: list[str],
        answer_leak: bool,
        grounding_score: float,
    ) -> None:
        self.schema_problems = schema_problems
        self.schema_ok = not schema_problems
        self.answer_leak = answer_leak
        self.grounding_score = grounding_score
        self.grounded = grounding_score >= GROUNDING_MIN
        # Schema + no-leak are hard gates; grounding is a hard gate too, so a
        # ladder shown to a student is always well-formed, retrieval-first and
        # traceable to the card's material.
        self.passed = self.schema_ok and (not answer_leak) and self.grounded

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "schemaOk": self.schema_ok,
            "schemaProblems": self.schema_problems,
            "answerLeak": self.answer_leak,
            "groundingScore": round(self.grounding_score, 3),
            "grounded": self.grounded,
        }


# --- lexical helpers (pure) --------------------------------------------------


def _content_tokens(text: str) -> set[str]:
    """Lowercased content words (>= 3 chars, non-stopword) from ``text``."""
    return {
        tok
        for tok in _TOKEN_RE.findall((text or "").lower())
        if len(tok) >= 3 and tok not in _STOPWORDS
    }


def _containment(part: str, whole: str) -> float:
    """Fraction of ``part``'s content words that also appear in ``whole``.

    Asymmetric on purpose: "how much of A is covered by B". Returns 0.0 when
    ``part`` has no content words (nothing to support / nothing to leak).
    """
    part_tokens = _content_tokens(part)
    if not part_tokens:
        return 0.0
    whole_tokens = _content_tokens(whole)
    return len(part_tokens & whole_tokens) / len(part_tokens)


# --- grounding-text extraction (pure) ---------------------------------------
#
# Card HTML carries far more than the human-readable prompt: the notetype's
# <style>, template <script>, inline <svg>, image/media tags with their
# filenames or data: URIs, LaTeX/TikZ diagram source, and image-occlusion shape
# data. If any of that leaks into the grounding text the model grounds a guiding
# ladder on the DIAGRAM'S SOURCE CODE instead of the biology/chemistry/etc.
# concept being tested. clean_grounding_text drops those artifacts and keeps
# only the text a student actually reads, so both the prompt and the grounding
# guardrails see the concept, not its markup. Shared by the desktop host and the
# eval harness.

#: Blocks whose *contents* are code/markup rather than prose — dropped whole
#: (removing only the tags would leave the CSS/JS/SVG body behind as "text").
_MARKUP_BLOCK_RE = re.compile(r"(?is)<(script|style|svg|head|noscript)\b.*?</\1>")
_HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
_HTML_TAG_RE = re.compile(r"(?s)<[^>]+>")
#: LaTeX/TikZ (and friends) drawing environments: the source of a rendered
#: diagram, never the concept. Inline math (\(...\), \[...\]) is left intact.
_DIAGRAM_ENV_RE = re.compile(
    r"(?is)\\begin\{(tikzpicture|circuitikz|pgfplots|axis|forest|tikzcd|"
    r"dependency|chemfig)\}.*?\\end\{\1\}"
)
#: Artifacts that survive as *text* once tags are gone: data: URIs / base64
#: blobs, Anki [sound:]/[anki:] media tags, image-occlusion shape specs, and
#: bare media filenames.
_DATA_URI_RE = re.compile(r"(?i)data:[^\s'\"<>]+")
_ANKI_MEDIA_TAG_RE = re.compile(r"(?is)\[(?:sound|anki):[^\]]*\]")
_OCCLUSION_SPEC_RE = re.compile(r"(?i)image-occlusion:[^\s<>{}]*")
_MEDIA_FILENAME_RE = re.compile(
    r"(?i)\b[\w./-]+\.(?:png|jpe?g|gif|svg|webp|bmp|tiff?|avif|ico|"
    r"mp3|mp4|wav|ogg|oga|webm|m4a|mov|avi|mkv|flac)\b"
)


def clean_grounding_text(html: str) -> str:
    """Extract only the human-readable prompt text from card HTML/markup.

    Strips the non-content artifacts that would otherwise make a generated
    ladder about a card's *rendering* rather than its topic: ``<script>``/
    ``<style>``/``<svg>`` bodies, HTML comments, every remaining tag (so
    image/media filenames living in attributes go with them), LaTeX/TikZ diagram
    source, ``data:`` URIs, Anki media tags, image-occlusion shape data and bare
    media filenames. Inline math and ordinary prose are preserved. Returns
    collapsed, entity-unescaped plain text (``""`` for empty or markup-only
    input, which the caller treats as "nothing to ground on").
    """
    if not html:
        return ""
    text = _MARKUP_BLOCK_RE.sub(" ", html)
    text = _HTML_COMMENT_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = unescape(text)
    # The rest are not wrapped in HTML tags, so strip them once tags are gone
    # and entities decoded.
    text = _DIAGRAM_ENV_RE.sub(" ", text)
    text = _DATA_URI_RE.sub(" ", text)
    text = _ANKI_MEDIA_TAG_RE.sub(" ", text)
    text = _OCCLUSION_SPEC_RE.sub(" ", text)
    text = _MEDIA_FILENAME_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def has_min_grounding(context: CardContext) -> bool:
    """False when a card has too little readable text to ground a ladder.

    After :func:`clean_grounding_text` strips diagram/markup, an image-only or
    image-occlusion card is left with (almost) nothing; generating from it would
    invent questions about a picture the model cannot see, so the caller must
    fall back to a normal reveal. Uses the same content-token notion as the
    grounding guardrail.
    """
    return len(_content_tokens(context.grounding_text)) >= MIN_GROUNDING_TOKENS


# --- prompt + parsing --------------------------------------------------------


def build_messages(context: CardContext) -> list[dict[str, str]]:
    """The chat messages sent to the model. Shared by runtime and eval so the
    thing scored is exactly the thing that ships."""
    system = (
        "You are a tutor for the MCAT. A student just answered a question "
        "WRONG. Do NOT reveal the answer outright. Instead, write a short "
        "ladder of guiding MULTIPLE-CHOICE questions that make the student "
        "WORK IT OUT by choosing (active retrieval, not passive reading).\n\n"
        "Hard rules:\n"
        f"- Output {MIN_RUNGS}-{MAX_RUNGS} rungs, ordered from foundational to "
        "the step just before the answer; the LAST rung should lead the student "
        "to recall the final answer themselves.\n"
        f"- Each rung is one multiple-choice question with a short stem "
        f"('question'), {MIN_OPTIONS}-{MAX_OPTIONS} answer 'options', a "
        "'correctIndex' (0-based index of the correct option), and a one-line "
        "'explanation' of why that option is correct.\n"
        "- The FIRST rung must NOT state or give away the final answer; it "
        "establishes a prerequisite idea.\n"
        "- Distractors must be plausible but clearly WRONG given the material; "
        "options must be distinct.\n"
        "- Every stem, option, correct answer and explanation must be grounded "
        "ONLY in the provided material — do not introduce facts that are not "
        "supported by it.\n"
        "- Word the correct option and its explanation in the provided "
        "material's OWN terms: reuse the key terms and phrasing that appear in "
        "the material rather than substituting outside synonyms, and keep each "
        "explanation to a single concise clause that the material directly "
        "supports.\n"
        'Return ONLY a JSON array: [{"question": "...", "options": ["...", '
        '"...", "..."], "correctIndex": 0, "explanation": "..."}, ...] with no '
        "prose, no markdown, no code fences."
    )
    parts = [f"QUESTION THE STUDENT MISSED:\n{context.question}"]
    if context.answer:
        parts.append(
            f"\nCORRECT ANSWER / EXPLANATION (for your reference only, "
            f"do NOT reveal it directly):\n{context.answer}"
        )
    if context.source:
        parts.append(f"\nCITED SOURCE MATERIAL:\n{context.source}")
    parts.append(
        f"\nWrite the {MIN_RUNGS}-{MAX_RUNGS} guiding multiple-choice questions "
        "now as the JSON array described."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]


def parse_ladder(raw_completion: str) -> Optional[list[dict[str, Any]]]:
    """Extract a multiple-choice ladder from a model completion.

    Tolerant of code fences / stray prose around the JSON. Returns a normalized
    list of MCQ rungs (``{"question", "options", "correctIndex",
    "explanation"}``), or ``None`` when nothing parseable is found. Structurally
    malformed rungs (missing stem/explanation, no usable options, or an
    uninterpretable ``correctIndex``) are dropped rather than crashing — the
    reviewer then simply runs a shorter (or, if empty, no) ladder.
    """
    if not raw_completion:
        return None
    text = raw_completion.strip()
    if text.startswith("```"):
        # strip a leading ```json / ``` fence and trailing fence
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    match = _JSON_ARRAY_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    rungs: list[dict[str, Any]] = []
    for entry in data:
        rung = _parse_rung(entry)
        if rung is not None:
            rungs.append(rung)
    return rungs


def _parse_rung(entry: object) -> Optional[dict[str, Any]]:
    """Normalize one raw MCQ rung, or ``None`` if it is structurally unusable.

    Kept lenient about *counts* (three-vs-four options, ``correctIndex`` range)
    so :func:`check_schema` remains the single place that gates those — this
    only rejects rungs that could not be rendered/graded at all.
    """
    if not isinstance(entry, dict):
        return None
    question = str(entry.get("question", "")).strip()
    explanation = str(entry.get("explanation", "")).strip()
    raw_options = entry.get("options")
    if not question or not explanation or not isinstance(raw_options, list):
        return None
    options = [str(opt).strip() for opt in raw_options if str(opt).strip()]
    if len(options) < 2:
        return None
    raw_index = entry.get("correctIndex")
    if isinstance(raw_index, bool):
        return None
    try:
        correct_index = int(raw_index)  # tolerate "0" / 0.0 from the model
    except (TypeError, ValueError):
        return None
    return {
        "question": question,
        "options": options,
        "correctIndex": correct_index,
        "explanation": explanation,
    }


# --- guardrails (pure) -------------------------------------------------------


def _correct_option(rung: dict[str, Any]) -> str:
    """The text of a rung's correct option, or '' if the index is unusable."""
    options = rung.get("options")
    index = rung.get("correctIndex")
    if (
        isinstance(options, list)
        and isinstance(index, int)
        and not isinstance(index, bool)
        and 0 <= index < len(options)
    ):
        return str(options[index])
    return ""


def check_schema(ladder: object) -> list[str]:
    """Structural problems with a parsed MCQ ladder (empty list == valid)."""
    problems: list[str] = []
    if not isinstance(ladder, list):
        return ["ladder is not a list"]
    if not (MIN_RUNGS <= len(ladder) <= MAX_RUNGS):
        problems.append(
            f"ladder must have {MIN_RUNGS}-{MAX_RUNGS} rungs, got {len(ladder)}"
        )
    for i, rung in enumerate(ladder):
        if not isinstance(rung, dict):
            problems.append(f"rung {i} is not an object")
            continue
        if not str(rung.get("question", "")).strip():
            problems.append(f"rung {i} has an empty question")
        if not str(rung.get("explanation", "")).strip():
            problems.append(f"rung {i} has an empty explanation")
        options = rung.get("options")
        if not isinstance(options, list):
            problems.append(f"rung {i} has no options list")
            continue
        cleaned = [str(opt).strip() for opt in options]
        if not (MIN_OPTIONS <= len(cleaned) <= MAX_OPTIONS):
            problems.append(
                f"rung {i} must have {MIN_OPTIONS}-{MAX_OPTIONS} options, "
                f"got {len(cleaned)}"
            )
        if any(not opt for opt in cleaned):
            problems.append(f"rung {i} has an empty option")
        present = [opt.lower() for opt in cleaned if opt]
        if len(set(present)) != len(present):
            problems.append(f"rung {i} has duplicate options")
        index = rung.get("correctIndex")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not (0 <= index < len(cleaned))
        ):
            problems.append(f"rung {i} has an out-of-range correctIndex")
    return problems


def check_answer_leak(ladder: list[dict[str, Any]], context: CardContext) -> bool:
    """True when the FIRST rung *blatantly* gives away the final answer.

    Checks the first rung's stem plus its correct option (the mini-answer the
    student would arrive at). Two triggers: the answer text appears
    near-verbatim there, or a high fraction (``ANSWER_LEAK_MAX``) of the
    answer's content words are already present. This is deliberately a coarse,
    high-precision gate: a bag-of-words comparison cannot reliably tell a
    conclusion-first rung from a prerequisite-first rung that happens to share
    vocabulary, so subtle "hands it over" leaks are left to the eval harness's
    LLM-as-judge (the reason the eval is hybrid). The generation prompt also
    instructs the model not to reveal the answer on rung 1, so subtle leaks are
    rare.
    """
    if not ladder:
        return False
    first = ladder[0]
    first_text = f"{first.get('question', '')} {_correct_option(first)}".strip()
    answer = context.answer
    if not answer:
        return False
    normalized_answer = " ".join(answer.lower().split())
    normalized_first = " ".join(first_text.lower().split())
    if normalized_answer and normalized_answer in normalized_first:
        return True
    return _containment(answer, first_text) >= ANSWER_LEAK_MAX


def grounding_score(ladder: list[dict[str, Any]], context: CardContext) -> float:
    """Mean fraction of each rung's correct option + explanation supported by
    the card's own material. 1.0 == fully grounded, 0.0 == invented.

    Only the *correct* answer and its explanation are scored: distractors are
    meant to be wrong, so requiring them to be grounded would penalize good
    plausible-but-wrong options.
    """
    if not ladder:
        return 0.0
    grounding = context.grounding_text
    scores = [
        _containment(
            f"{_correct_option(rung)} {rung.get('explanation', '')}".strip(),
            grounding,
        )
        for rung in ladder
    ]
    return sum(scores) / len(scores) if scores else 0.0


def validate_ladder(
    ladder: Optional[list[dict[str, Any]]], context: CardContext
) -> ValidationResult:
    """Run all deterministic guardrails. Safe on ``None``/malformed input."""
    problems = check_schema(ladder)
    safe_ladder = ladder if isinstance(ladder, list) else []
    # Only score leak/grounding on structurally-usable rungs.
    usable = [r for r in safe_ladder if isinstance(r, dict)]
    leak = check_answer_leak(usable, context) if usable else False
    score = grounding_score(usable, context) if usable else 0.0
    return ValidationResult(
        schema_problems=problems, answer_leak=leak, grounding_score=score
    )


# --- OpenAI call (the one bit of IO; injectable for tests) -------------------

#: A chat function takes (messages, model) and returns the assistant's text.
ChatFn = Callable[[list[dict[str, str]], str], str]


def openai_chat(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    *,
    api_key: Optional[str] = None,
    temperature: float = 0.4,
    timeout: int = DEFAULT_TIMEOUT_SECS,
) -> str:
    """Minimal OpenAI Chat Completions call over stdlib ``urllib`` (no dep).

    Reads ``OPENAI_API_KEY`` from the environment when ``api_key`` is not
    given. Raises ``LadderGenError`` on any transport/API error so callers can
    fall back gracefully.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LadderGenError("OPENAI_API_KEY is not set")
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "text"},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise LadderGenError(f"OpenAI HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:  # pragma: no cover
        raise LadderGenError(f"OpenAI request failed: {exc}") from exc
    try:
        return str(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover
        raise LadderGenError("unexpected OpenAI response shape") from exc


class LadderGenError(RuntimeError):
    """Raised when generation cannot produce a valid ladder."""


class GenerationOutcome:
    """Everything a caller needs: the ladder (if any), why, and the checks."""

    def __init__(
        self,
        *,
        ladder: Optional[list[dict[str, Any]]],
        validation: Optional[ValidationResult],
        attempts: int,
        raw: str = "",
        error: str = "",
    ) -> None:
        self.ladder = ladder
        self.validation = validation
        self.attempts = attempts
        self.raw = raw
        self.error = error

    @property
    def ok(self) -> bool:
        return (
            bool(self.ladder) and self.validation is not None and self.validation.passed
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "attempts": self.attempts,
            "ladder": self.ladder,
            "validation": self.validation.as_dict() if self.validation else None,
            "error": self.error,
        }


def generate_ladder(
    context: CardContext,
    *,
    chat_fn: Optional[ChatFn] = None,
    model: str = DEFAULT_MODEL,
    attempts: int = DEFAULT_ATTEMPTS,
) -> GenerationOutcome:
    """Generate + validate a ladder, retrying up to ``attempts`` times.

    ``chat_fn`` defaults to :func:`openai_chat`; tests inject a stub so no
    network is touched. Returns a :class:`GenerationOutcome` whose ``ok`` is
    True only when a produced ladder passed every guardrail — the caller shows
    it to the student iff ``ok``, and otherwise falls back gracefully.
    """
    if chat_fn is None:
        chat_fn = openai_chat
    # An image-only / diagram / occlusion card has nothing to ground on once its
    # markup is stripped: bail before spending a request so the reviewer falls
    # back to a normal reveal instead of the model inventing questions.
    if not has_min_grounding(context):
        return GenerationOutcome(
            ladder=None,
            validation=None,
            attempts=0,
            error="insufficient grounding text (image-only/diagram card)",
        )
    messages = build_messages(context)
    last: GenerationOutcome | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            raw = chat_fn(messages, model)
        except Exception as exc:  # transport/API error -> record and retry
            last = GenerationOutcome(
                ladder=None, validation=None, attempts=attempt, error=str(exc)
            )
            continue
        ladder = parse_ladder(raw)
        validation = validate_ladder(ladder, context)
        outcome = GenerationOutcome(
            ladder=ladder, validation=validation, attempts=attempt, raw=raw
        )
        if outcome.ok:
            return outcome
        last = outcome
    return last or GenerationOutcome(
        ladder=None, validation=None, attempts=0, error="no attempts made"
    )


# --- CLI (ad-hoc preview) ----------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a ReadyMCAT teach-on-miss ladder for a single card and "
            "print it (with its guardrail report) as JSON. Requires "
            "OPENAI_API_KEY unless --raw is given."
        )
    )
    parser.add_argument("--question", required=True, help="the missed question")
    parser.add_argument("--answer", default="", help="the correct answer/explanation")
    parser.add_argument("--source", default="", help="cited source material")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--raw",
        default=None,
        help="validate this completion string instead of calling the API "
        "(offline; useful for testing the guardrails)",
    )
    args = parser.parse_args(argv)

    context = CardContext(args.question, args.answer, source=args.source)
    if args.raw is not None:
        ladder = parse_ladder(args.raw)
        validation = validate_ladder(ladder, context)
        outcome = GenerationOutcome(
            ladder=ladder, validation=validation, attempts=0, raw=args.raw
        )
    else:
        outcome = generate_ladder(context, model=args.model)
    print(json.dumps(outcome.as_dict(), indent=2, ensure_ascii=False))
    return 0 if outcome.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
