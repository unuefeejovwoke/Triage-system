"""Tests for the rule-based decision engine."""
import json
import time
from pathlib import Path

import pytest

from app.engine import (
    NextQuestion, ProtocolError, TriageResult, evaluate, rules_from_dict, triage,
)
from app.protocols import SEVERITY, load_all

PROTOCOLS = {p["name"]: rules_from_dict(p) for p in load_all()}
SCENARIOS = json.loads((Path(__file__).resolve().parent.parent / "data" / "scenarios.json").read_text(encoding="utf-8"))

ALL_QUESTIONS = [(name, q) for name, r in PROTOCOLS.items() for q in r.questions]


def answers_with_yes_at(rules, orders):
    """All questions answered No, except the given ones answered Yes."""
    return {q.order: (q.order in orders) for q in rules.questions}


# ---------------------------------------------------------------- every question

@pytest.mark.parametrize("name,question", ALL_QUESTIONS, ids=[f"{n[:20]}-Q{q.order}" for n, q in ALL_QUESTIONS])
def test_yes_to_each_question_returns_its_disposition(name, question):
    rules = PROTOCOLS[name]
    answers = {q.order: False for q in rules.questions if q.order < question.order}
    answers[question.order] = True
    result = evaluate(rules, answers)
    assert isinstance(result, TriageResult)
    assert result.level == question.level
    assert result.triggered_by == question
    assert result.questions_asked == question.order
    assert result.advice == rules.advice[question.level]


@pytest.mark.parametrize("name", PROTOCOLS)
def test_no_to_everything_returns_self_care(name):
    rules = PROTOCOLS[name]
    result = triage(rules, {q.order: False for q in rules.questions})
    assert result.level == "self_care"
    assert result.triggered_by is None
    assert result.advice == rules.advice["self_care"]


# ---------------------------------------------------------------- flow

@pytest.mark.parametrize("name", PROTOCOLS)
def test_questions_are_asked_one_at_a_time_in_order(name):
    rules = PROTOCOLS[name]
    answers = {}
    for position, q in enumerate(rules.questions, start=1):
        step = evaluate(rules, answers)
        assert isinstance(step, NextQuestion)
        assert step.question == q and step.number == position and step.total == rules.total
        answers[q.order] = False


def test_first_yes_wins_and_later_answers_are_ignored():
    rules = PROTOCOLS["Chest Pain"]
    answers = answers_with_yes_at(rules, {3, 5, 7})
    assert triage(rules, answers).level == "emergency"
    assert triage(rules, answers).triggered_by.order == 3


def test_missing_earlier_answer_is_asked_before_deciding():
    """A danger sign can never be skipped, even if later questions were answered."""
    rules = PROTOCOLS["Chest Pain"]
    step = evaluate(rules, {1: False, 3: False, 5: True})
    assert isinstance(step, NextQuestion) and step.question.order == 2


def test_triage_refuses_incomplete_answers():
    with pytest.raises(ValueError, match="no answer yet"):
        triage(PROTOCOLS["Chest Pain"], {1: False})


def test_non_boolean_answer_is_rejected():
    with pytest.raises(ValueError, match="True or False"):
        evaluate(PROTOCOLS["Chest Pain"], {1: "yes"})


# ---------------------------------------------------------------- safety and consistency

def test_engine_refuses_unsafe_protocol():
    bad = {
        "name": "Unsafe", "version": "1", "population": "adult", "source_guidance": "x",
        "questions": [{"order": 1, "text": "a", "disposition": "routine"},
                      {"order": 2, "text": "b", "disposition": "emergency"}],
        "advice": {"routine": ["r"], "emergency": ["e"], "self_care": ["s"]},
    }
    with pytest.raises(ProtocolError):
        rules_from_dict(bad)


def test_same_answers_always_give_same_result():
    rules = PROTOCOLS["Fever in Children (under 5)"]
    answers = answers_with_yes_at(rules, {7})
    results = {triage(rules, answers) for _ in range(1000)}
    assert len(results) == 1


def test_result_is_never_less_serious_than_any_yes_answer_asked():
    """Safety property: across every protocol and every single-Yes pattern,
    the result is at least as serious as the triggering question."""
    for rules in PROTOCOLS.values():
        for q in rules.questions:
            r = triage(rules, answers_with_yes_at(rules, {q.order}))
            assert r.severity_rank <= SEVERITY[q.level]


def test_engine_is_fast():
    """Non-functional requirement: result in under one second. Engine alone should take well under 1 ms."""
    rules = PROTOCOLS["Fever in Children (under 5)"]
    answers = {q.order: False for q in rules.questions}
    start = time.perf_counter()
    for _ in range(10_000):
        triage(rules, answers)
    per_call = (time.perf_counter() - start) / 10_000
    assert per_call < 0.001


# ---------------------------------------------------------------- clinical scenarios

@pytest.mark.parametrize("s", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_clinical_scenario(s):
    rules = PROTOCOLS[s["protocol"]]
    result = triage(rules, answers_with_yes_at(rules, set(s["yes_answers"])))
    assert result.level == s["expected"], s["scenario"]
