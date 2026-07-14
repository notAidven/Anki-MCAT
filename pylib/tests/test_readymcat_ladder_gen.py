# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Offline, deterministic tests for the ReadyMCAT ladder generator core.

The core (``readymcat/tools/ladder_gen.py``) is pure stdlib and the OpenAI
call is injectable, so these tests exercise the prompt, parser and guardrails
with a stub chat function and never touch the network. Loaded by path,
mirroring ``test_readymcat_bank.py``.

Each guiding rung is a multiple-choice question
(``{"question", "options", "correctIndex", "explanation"}``): the student works
it out by choosing. The guardrails validate that shape (schema + option
sanity + in-range correctIndex), keep the first rung from leaking the answer,
and require the correct option + explanation to be grounded in the card.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "readymcat" / "tools" / "ladder_gen.py"


def _load_core():
    spec = importlib.util.spec_from_file_location(
        "readymcat_ladder_gen_test", _MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load_core()

# A card with rich answer/source text so grounding is meaningful.
_QUESTION = "What is the net ATP yield of glycolysis?"
_ANSWER = (
    "Glycolysis invests 2 ATP in the investment phase at hexokinase and "
    "phosphofructokinase, then produces 4 ATP and 2 NADH in the payoff phase, "
    "for a net yield of 2 ATP and 2 NADH."
)


def _context():
    return gen.CardContext(_QUESTION, _ANSWER, source="", tags=["#Biochemistry"])


def _good_ladder():
    """Two well-formed MCQ rungs whose correct options + explanations are drawn
    straight from the card's own material (so grounding is high) and whose first
    rung establishes a prerequisite without handing over the answer."""
    return [
        {
            "question": "In the investment phase, how many ATP does glycolysis consume?",
            "options": ["2 ATP", "4 ATP", "0 ATP"],
            "correctIndex": 0,
            "explanation": "Glycolysis invests 2 ATP, at hexokinase and phosphofructokinase.",
        },
        {
            "question": "In the payoff phase, how many ATP and NADH are produced?",
            "options": ["2 ATP and 2 NADH", "4 ATP and 2 NADH", "4 ATP and 4 NADH"],
            "correctIndex": 1,
            "explanation": "The payoff phase produces 4 ATP and 2 NADH.",
        },
    ]


# --- parsing ----------------------------------------------------------------


def test_parse_ladder_handles_code_fences_and_prose():
    raw = "Sure! Here is the ladder:\n```json\n" + json.dumps(_good_ladder()) + "\n```"
    assert gen.parse_ladder(raw) == _good_ladder()


def test_parse_ladder_drops_malformed_rungs():
    raw = json.dumps(
        [
            _good_ladder()[0],
            {"question": "no options or explanation"},  # missing fields -> dropped
            "junk",  # not an object -> dropped
            {  # no question -> dropped
                "options": ["a", "b", "c"],
                "correctIndex": 0,
                "explanation": "no stem",
            },
            {  # uninterpretable correctIndex -> dropped
                "question": "bad index?",
                "options": ["a", "b", "c"],
                "correctIndex": "two",
                "explanation": "x",
            },
        ]
    )
    assert gen.parse_ladder(raw) == [_good_ladder()[0]]


def test_parse_ladder_coerces_string_and_float_index():
    raw = json.dumps(
        [
            {
                "question": "q1?",
                "options": ["a", "b", "c"],
                "correctIndex": "1",  # model sometimes stringifies the index
                "explanation": "e1",
            },
            {
                "question": "q2?",
                "options": ["a", "b", "c"],
                "correctIndex": 2.0,  # or emits a float
                "explanation": "e2",
            },
        ]
    )
    parsed = gen.parse_ladder(raw)
    assert parsed is not None
    assert [rung["correctIndex"] for rung in parsed] == [1, 2]


def test_parse_ladder_returns_none_on_garbage():
    assert gen.parse_ladder("no json here") is None
    assert gen.parse_ladder("") is None
    assert gen.parse_ladder('{"question": "obj not array"}') is None


# --- schema -----------------------------------------------------------------


def test_check_schema_flags_rung_count():
    assert gen.check_schema([_good_ladder()[0]])  # too few (1 < MIN_RUNGS)
    too_many = [_good_ladder()[0]] * (gen.MAX_RUNGS + 1)
    assert gen.check_schema(too_many)
    assert gen.check_schema(_good_ladder()) == []


def test_check_schema_flags_non_list_and_empty_fields():
    assert gen.check_schema("not a list")
    problems = gen.check_schema(
        [
            {
                "question": "",
                "options": ["a", "b", "c"],
                "correctIndex": 0,
                "explanation": "x",
            },
            {
                "question": "y",
                "options": ["a", "b", "c"],
                "correctIndex": 0,
                "explanation": "",
            },
        ]
    )
    assert any("empty question" in p for p in problems)
    assert any("empty explanation" in p for p in problems)


def test_check_schema_flags_option_count_empty_and_duplicates():
    good_second = _good_ladder()[1]

    too_few = [dict(_good_ladder()[0], options=["only", "two"]), good_second]
    assert any("options" in p for p in gen.check_schema(too_few))

    empty_option = [dict(_good_ladder()[0], options=["a", "", "c"]), good_second]
    assert any("empty option" in p for p in gen.check_schema(empty_option))

    duplicates = [dict(_good_ladder()[0], options=["Same", "same", "b"]), good_second]
    assert any("duplicate" in p for p in gen.check_schema(duplicates))


def test_check_schema_flags_out_of_range_or_missing_correct_index():
    good_second = _good_ladder()[1]

    out_of_range = [dict(_good_ladder()[0], correctIndex=9), good_second]
    assert any("correctIndex" in p for p in gen.check_schema(out_of_range))

    missing = [
        {"question": "q", "options": ["a", "b", "c"], "explanation": "e"},
        good_second,
    ]
    assert any("correctIndex" in p for p in gen.check_schema(missing))


# --- answer-leak ------------------------------------------------------------


def test_answer_leak_catches_verbatim_answer_in_first_rung():
    short_answer = "The net yield is 2 ATP and 2 NADH."
    context = gen.CardContext(_QUESTION, short_answer)
    # The first rung's correct option IS the final answer -> a blatant leak.
    leaky = [
        {
            "question": "What is the result?",
            "options": [short_answer, "Only 2 ATP", "Only 2 NADH"],
            "correctIndex": 0,
            "explanation": "That is the net result.",
        },
        _good_ladder()[1],
    ]
    assert gen.check_answer_leak(leaky, context) is True


def test_answer_leak_allows_a_scaffolded_first_rung():
    # A prerequisite-first rung must NOT be flagged as a leak.
    assert gen.check_answer_leak(_good_ladder(), _context()) is False


# --- grounding --------------------------------------------------------------


def test_grounding_high_when_correct_options_use_card_material():
    score = gen.grounding_score(_good_ladder(), _context())
    assert score >= gen.GROUNDING_MIN


def test_grounding_low_when_answers_are_invented():
    invented = [
        {
            "question": "q1?",
            "options": ["Chloroplast thylakoid membranes", "Cytosol", "Nucleus"],
            "correctIndex": 0,
            "explanation": "Photosynthesis occurs in chloroplast thylakoid membranes.",
        },
        {
            "question": "q2?",
            "options": ["Rubisco carboxylation", "Hydrolysis", "Osmosis"],
            "correctIndex": 0,
            "explanation": "Rubisco fixes carbon dioxide in the Calvin cycle.",
        },
    ]
    assert gen.grounding_score(invented, _context()) < gen.GROUNDING_MIN


def test_grounding_ignores_wrong_distractors():
    # Distractors are deliberately off-topic; grounding scores only the correct
    # option + explanation, so a rung with wild distractors still grounds high.
    ladder = [
        dict(
            _good_ladder()[0],
            options=["2 ATP", "The Krebs cycle in the mitochondria", "Photosystem II"],
        ),
        _good_ladder()[1],
    ]
    assert gen.grounding_score(ladder, _context()) >= gen.GROUNDING_MIN


# --- validate_ladder aggregate ----------------------------------------------


def test_validate_ladder_passes_a_good_ladder():
    result = gen.validate_ladder(_good_ladder(), _context())
    assert result.passed is True
    assert result.schema_ok is True
    assert result.answer_leak is False
    assert result.grounded is True


def test_validate_ladder_safe_on_none_and_malformed():
    result = gen.validate_ladder(None, _context())
    assert result.passed is False
    assert result.schema_ok is False


# --- generate_ladder orchestration (stubbed, offline) -----------------------


def test_generate_ladder_ok_with_a_valid_stub():
    ladder_json = json.dumps(_good_ladder())

    def stub(messages, model):
        assert isinstance(messages, list) and messages[0]["role"] == "system"
        # The prompt must ask for the MCQ shape the parser expects.
        assert "correctIndex" in messages[0]["content"]
        return ladder_json

    outcome = gen.generate_ladder(_context(), chat_fn=stub)
    assert outcome.ok is True
    assert outcome.attempts == 1
    assert outcome.validation is not None and outcome.validation.passed
    assert outcome.ladder is not None
    assert all("options" in rung for rung in outcome.ladder)


def test_generate_ladder_retries_then_fails_on_bad_output():
    calls = {"n": 0}

    def stub(messages, model):
        calls["n"] += 1
        return "[]"  # empty ladder -> schema fail every attempt

    outcome = gen.generate_ladder(_context(), chat_fn=stub, attempts=2)
    assert outcome.ok is False
    assert calls["n"] == 2  # retried
    assert outcome.validation is not None and not outcome.validation.schema_ok


def test_generate_ladder_records_transport_error():
    def stub(messages, model):
        raise gen.LadderGenError("boom")

    outcome = gen.generate_ladder(_context(), chat_fn=stub, attempts=2)
    assert outcome.ok is False
    assert "boom" in outcome.error


def test_generate_ladder_not_ok_means_caller_falls_back():
    # AI-off / generation-failure contract: the reviewer shows a generated ladder
    # ONLY when ok is True. When the model is unavailable (no key -> transport
    # error) there is no usable ladder, so the caller falls back to a normal
    # reveal instead of stranding the student.
    def unavailable(messages, model):
        raise gen.LadderGenError("OPENAI_API_KEY is not set")

    outcome = gen.generate_ladder(_context(), chat_fn=unavailable, attempts=1)
    assert outcome.ok is False
    assert not outcome.ladder


# --- grounding-text cleaning (diagram / fill-in-the-blank cards) -------------
#
# Imported cards often render a diagram with a blank to fill in. Their HTML is
# dominated by NON-content markup — the notetype <style>, a drawing <script>,
# LaTeX/TikZ/SVG source, image filenames, data: URIs, image-occlusion shape
# data — none of which is the biology/chemistry topic being tested. If that
# leaks into the grounding text the model grounds the ladder on the diagram's
# SOURCE CODE. clean_grounding_text strips it so only the readable prompt (and
# inline math) remains.

# A diagram/fill-in-the-blank card exactly as ``card.question()`` renders it:
# the card's own <style>, a drawing <script>, an <img>, and TikZ source wrapped
# around a one-line human prompt.
_DIAGRAM_QUESTION_HTML = (
    "<style>.card{font-family:arial;font-size:20px;text-align:center;}</style>"
    "<div class=front>Which glycolysis intermediate fills the blank in the "
    "diagram?</div>"
    '<img src="glycolysis_pathway_final_v2.png">'
    "<script>const shapes=[{x:10,y:20,label:'ATP'}];drawDiagram(shapes);</script>"
    "\\begin{tikzpicture}\\draw (0,0) circle (1cm);\\node at (0,0){G6P};"
    "\\end{tikzpicture}"
)
_DIAGRAM_ANSWER_HTML = (
    "<style>.card{color:#000}</style>"
    "The blank is <b>fructose-1,6-bisphosphate</b>, produced by "
    "phosphofructokinase-1."
)


def test_clean_grounding_text_strips_code_and_diagram_markup():
    cleaned = gen.clean_grounding_text(_DIAGRAM_QUESTION_HTML)
    # the human-readable prompt survives...
    assert "fills the blank in the diagram" in cleaned
    # ...but none of the CSS / JS / TikZ / image-filename source does.
    for leak in [
        "font-family",
        "arial",
        "text-align",  # <style> body
        "drawDiagram",
        "shapes",
        "const",  # <script> body
        "tikzpicture",
        "circle",
        "node",  # LaTeX/TikZ source
        ".png",
        "glycolysis_pathway_final_v2",  # image filename
    ]:
        assert leak not in cleaned, f"leaked {leak!r}: {cleaned!r}"


def test_clean_grounding_text_keeps_inline_math():
    # Inline math IS the concept on a lot of cards, so it must survive intact
    # (only *drawing* environments like tikzpicture are stripped).
    cleaned = gen.clean_grounding_text(
        "<style>x</style>Compute \\(\\Delta G = -RT\\ln K\\) when K &gt; 1."
    )
    assert cleaned == "Compute \\(\\Delta G = -RT\\ln K\\) when K > 1."


def test_clean_grounding_text_empty_for_image_only_and_occlusion():
    # A pure image, a markup-only card, and an image-occlusion card all clean to
    # nothing groundable.
    assert gen.clean_grounding_text('<img src="unlabeled_slide.png">') == ""
    assert gen.clean_grounding_text("<style>a{}</style><script>f()</script>") == ""
    occlusion = (
        '<div id="image-occlusion-container"><img src="heart.jpg">'
        '<div class="cloze" data-shape="{{c1::image-occlusion:rect:top=.1:'
        'left=.2:width=.4:height=.5}}"></div></div>'
    )
    assert gen.clean_grounding_text(occlusion) == ""


def test_clean_grounding_text_strips_data_uris_and_media_tags():
    html = (
        "Name this heart chamber: "
        '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg"> '
        "[sound:beat.mp3]"
    )
    assert gen.clean_grounding_text(html) == "Name this heart chamber:"


def test_diagram_card_grounds_on_topic_not_its_source_code():
    context = gen.CardContext(
        gen.clean_grounding_text(_DIAGRAM_QUESTION_HTML),
        gen.clean_grounding_text(_DIAGRAM_ANSWER_HTML),
    )
    # A ladder about the DIAGRAM'S SOURCE CODE (the bug's symptom) is not
    # grounded in the cleaned card, so the guardrail rejects it...
    about_source_code = [
        {
            "question": "What shape does the tikzpicture draw?",
            "options": ["A circle", "A square", "A line"],
            "correctIndex": 0,
            "explanation": "The \\draw command renders a circle at the node.",
        },
        {
            "question": "What is the image filename?",
            "options": ["glycolysis_pathway_final_v2.png", "a.png", "b.png"],
            "correctIndex": 0,
            "explanation": "The img src points to the png file.",
        },
    ]
    assert gen.grounding_score(about_source_code, context) < gen.GROUNDING_MIN
    # ...while a ladder about the biochemistry topic grounds high.
    about_topic = [
        {
            "question": "Which enzyme acts just before the blank in glycolysis?",
            "options": ["Phosphofructokinase-1", "Amylase", "Lipase"],
            "correctIndex": 0,
            "explanation": "Phosphofructokinase-1 produces the intermediate.",
        },
        {
            "question": "Which intermediate fills the blank?",
            "options": ["Fructose-1,6-bisphosphate", "Glucose", "Pyruvate"],
            "correctIndex": 0,
            "explanation": "The blank is fructose-1,6-bisphosphate.",
        },
    ]
    assert gen.grounding_score(about_topic, context) >= gen.GROUNDING_MIN


def test_has_min_grounding_flags_image_only_cards():
    image_only = gen.CardContext(
        gen.clean_grounding_text('<img src="unlabeled_slide.png">'),
        gen.clean_grounding_text('<img src="answer_slide.png">'),
    )
    assert gen.has_min_grounding(image_only) is False
    assert gen.has_min_grounding(_context()) is True


def test_generate_ladder_bails_on_ungroundable_card_without_calling_model():
    # An image-only/diagram card with no readable text must NOT reach the model
    # (no wasted request, no invented ladder); the caller then falls back to a
    # normal reveal because ``ok`` is False.
    calls = {"n": 0}

    def stub(messages, model):
        calls["n"] += 1
        return json.dumps(_good_ladder())

    image_only = gen.CardContext(
        gen.clean_grounding_text('<img src="unlabeled_slide.png">'),
        gen.clean_grounding_text('<img src="answer_slide.png">'),
    )
    outcome = gen.generate_ladder(image_only, chat_fn=stub, attempts=2)
    assert outcome.ok is False
    assert outcome.ladder is None
    assert calls["n"] == 0
    assert "grounding" in outcome.error
