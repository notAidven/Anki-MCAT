# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Offline, deterministic tests for the ReadyMCAT ladder generator core.

The core (``readymcat/tools/ladder_gen.py``) is pure stdlib and the OpenAI
call is injectable, so these tests exercise the prompt, parser and guardrails
with a stub chat function and never touch the network. Loaded by path,
mirroring ``test_readymcat_bank.py``.
"""

from __future__ import annotations

import importlib.util
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
    return [
        {
            "q": "In the investment phase, how many ATP does glycolysis consume?",
            "a": "Glycolysis invests 2 ATP, at hexokinase and phosphofructokinase.",
        },
        {
            "q": "In the payoff phase, how many ATP and NADH are produced?",
            "a": "The payoff phase produces 4 ATP and 2 NADH.",
        },
    ]


# --- parsing ----------------------------------------------------------------


def test_parse_ladder_handles_code_fences_and_prose():
    raw = (
        "Sure! Here is the ladder:\n```json\n"
        '[{"q": "q1?", "a": "a1"}, {"q": "q2?", "a": "a2"}]\n```'
    )
    ladder = gen.parse_ladder(raw)
    assert ladder == [{"q": "q1?", "a": "a1"}, {"q": "q2?", "a": "a2"}]


def test_parse_ladder_drops_malformed_rungs():
    raw = '[{"q": "ok?", "a": "yes"}, {"q": "no answer"}, "junk", {"a": "no q"}]'
    assert gen.parse_ladder(raw) == [{"q": "ok?", "a": "yes"}]


def test_parse_ladder_returns_none_on_garbage():
    assert gen.parse_ladder("no json here") is None
    assert gen.parse_ladder("") is None
    assert gen.parse_ladder('{"q": "obj not array"}') is None


# --- schema -----------------------------------------------------------------


def test_check_schema_flags_rung_count():
    assert gen.check_schema([{"q": "a", "a": "b"}])  # too few (1 < MIN_RUNGS)
    too_many = [{"q": "q", "a": "a"}] * (gen.MAX_RUNGS + 1)
    assert gen.check_schema(too_many)
    assert gen.check_schema(_good_ladder()) == []


def test_check_schema_flags_empty_fields_and_non_list():
    assert gen.check_schema("not a list")
    problems = gen.check_schema([{"q": "", "a": "x"}, {"q": "y", "a": ""}])
    assert any("empty question" in p for p in problems)
    assert any("empty answer" in p for p in problems)


# --- answer-leak ------------------------------------------------------------


def test_answer_leak_catches_verbatim_answer_in_first_rung():
    short_answer = "The net yield is 2 ATP and 2 NADH."
    context = gen.CardContext(_QUESTION, short_answer)
    leaky = [
        {"q": "What is the result?", "a": f"{short_answer} That is the result."},
        {"q": "Why?", "a": "Because of the payoff phase."},
    ]
    assert gen.check_answer_leak(leaky, context) is True


def test_answer_leak_allows_a_scaffolded_first_rung():
    # A prerequisite-first rung must NOT be flagged as a leak.
    assert gen.check_answer_leak(_good_ladder(), _context()) is False


# --- grounding --------------------------------------------------------------


def test_grounding_high_when_subanswers_use_card_material():
    score = gen.grounding_score(_good_ladder(), _context())
    assert score >= gen.GROUNDING_MIN


def test_grounding_low_when_subanswers_are_invented():
    invented = [
        {"q": "q1?", "a": "Photosynthesis occurs in chloroplast thylakoid membranes."},
        {"q": "q2?", "a": "Rubisco fixes carbon dioxide in the Calvin cycle."},
    ]
    score = gen.grounding_score(invented, _context())
    assert score < gen.GROUNDING_MIN


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
    ladder_json = (
        '[{"q": "In the investment phase, how many ATP does glycolysis '
        'consume?", "a": "Glycolysis invests 2 ATP, at hexokinase and '
        'phosphofructokinase."}, {"q": "In the payoff phase, how many ATP and '
        'NADH are produced?", "a": "The payoff phase produces 4 ATP and 2 '
        'NADH."}]'
    )

    def stub(messages, model):
        assert isinstance(messages, list) and messages[0]["role"] == "system"
        return ladder_json

    outcome = gen.generate_ladder(_context(), chat_fn=stub)
    assert outcome.ok is True
    assert outcome.attempts == 1
    assert outcome.validation is not None and outcome.validation.passed


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
