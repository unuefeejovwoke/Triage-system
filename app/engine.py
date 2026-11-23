"""Rule-based decision engine (Chapter Three, Section 3.5.5).

How it works:
    The questions in a protocol are ordered from most to least serious.
    The engine walks through them in order. The first question answered
    "Yes" decides the disposition. If every answer is "No", the result is
    self-care.

The engine is stateless and has no database code in it. It only needs the
protocol rules and the answers so far. That makes it:
    - consistent: the same answers always give the same result
    - easy to test on its own
    - easy to explain and check by a clinician
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.protocols import SEVERITY, ProtocolError, validate

SELF_CARE = "self_care"


@dataclass(frozen=True)
class Question:
    order: int
    text: str
    level: str  # disposition if the answer is Yes


@dataclass(frozen=True)
class ProtocolRules:
    name: str
    version: str
    questions: tuple[Question, ...]
    advice: dict[str, tuple[str, ...]] = field(hash=False)

    @property
    def total(self) -> int:
        return len(self.questions)


@dataclass(frozen=True)
class NextQuestion:
    """The engine needs another answer before it can decide."""
    question: Question
    number: int  # 1-based position, for "Question 4 of 7"
    total: int
    done: bool = False


@dataclass(frozen=True)
class TriageResult:
    """The final disposition for this consultation."""
    level: str
    severity_rank: int
    triggered_by: Question | None  # None means every answer was No
    advice: tuple[str, ...]
    questions_asked: int
    done: bool = True


# ---------------------------------------------------------------- loading

def rules_from_dict(data: dict) -> ProtocolRules:
    """Build rules from a protocol JSON file. Unsafe protocols are refused."""
    validate(data, data.get("name", "<protocol>"))
    questions = tuple(
        Question(order=q["order"], text=q["text"], level=q["disposition"])
        for q in sorted(data["questions"], key=lambda q: q["order"])
    )
    advice = {level: tuple(lines) for level, lines in data["advice"].items()}
    return ProtocolRules(data["name"], data["version"], questions, advice)


def rules_from_db(protocol) -> ProtocolRules:
    """Build rules from a Protocol row loaded from the database."""
    data = {
        "name": protocol.name,
        "version": protocol.version,
        "population": protocol.population,
        "source_guidance": protocol.source_guidance,
        "questions": [
            {"order": q.question_order, "text": q.question_text, "disposition": q.disposition.level}
            for q in protocol.questions
        ],
        "advice": {a.disposition.level: a.advice_text.splitlines() for a in protocol.advice},
    }
    return rules_from_dict(data)


# ---------------------------------------------------------------- engine

def evaluate(rules: ProtocolRules, answers: dict[int, bool]) -> NextQuestion | TriageResult:
    """Return the next question to ask, or the final result.

    answers maps question order -> True (Yes) or False (No).
    Answers for questions after the first Yes are ignored.
    If an earlier question has no answer yet, that question is asked first,
    even if later questions were answered, so a danger sign is never skipped.
    """
    for position, q in enumerate(rules.questions, start=1):
        if q.order not in answers:
            return NextQuestion(question=q, number=position, total=rules.total)
        answer = answers[q.order]
        if not isinstance(answer, bool):
            raise ValueError(f"answer to question {q.order} must be True or False, got {answer!r}")
        if answer:
            return _result(rules, q.level, q, position)
    return _result(rules, SELF_CARE, None, rules.total)


def triage(rules: ProtocolRules, answers: dict[int, bool]) -> TriageResult:
    """Evaluate a complete set of answers. Raises if an answer is still needed."""
    step = evaluate(rules, answers)
    if isinstance(step, NextQuestion):
        raise ValueError(f"no answer yet for question {step.question.order}: {step.question.text}")
    return step


def _result(rules: ProtocolRules, level: str, q: Question | None, asked: int) -> TriageResult:
    return TriageResult(
        level=level,
        severity_rank=SEVERITY[level],
        triggered_by=q,
        advice=rules.advice[level],
        questions_asked=asked,
    )


__all__ = [
    "Question", "ProtocolRules", "NextQuestion", "TriageResult", "ProtocolError",
    "rules_from_dict", "rules_from_db", "evaluate", "triage", "SELF_CARE",
]
