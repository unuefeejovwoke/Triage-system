"""Tests for the protocol safety rules (Section 3.5.5). No database needed."""
import copy

import pytest

from app.protocols import ProtocolError, load_all, validate

GOOD = {
    "name": "Test", "version": "1.0", "population": "adult", "source_guidance": "test",
    "questions": [
        {"order": 1, "text": "Danger sign?", "disposition": "emergency"},
        {"order": 2, "text": "Needs same-day care?", "disposition": "urgent"},
        {"order": 3, "text": "Needs a clinic visit?", "disposition": "routine"},
    ],
    "advice": {"emergency": ["a"], "urgent": ["b"], "routine": ["c"], "self_care": ["d"]},
}


def bad(**changes):
    data = copy.deepcopy(GOOD)
    for path, value in changes.items():
        if path == "q2_disposition":
            data["questions"][1]["disposition"] = value
        elif path == "q1_disposition":
            data["questions"][0]["disposition"] = value
        elif path == "orders":
            for q, o in zip(data["questions"], value):
                q["order"] = o
        elif path == "drop_advice":
            del data["advice"][value]
    return data


def test_all_protocol_files_are_valid():
    protocols = load_all()
    assert len(protocols) == 10
    for p in protocols:
        assert 7 <= len(p["questions"]) <= 12


def test_good_protocol_passes():
    validate(GOOD)


def test_less_serious_question_before_serious_one_is_rejected():
    data = copy.deepcopy(GOOD)
    data["questions"][0]["disposition"] = "urgent"
    data["questions"][1]["disposition"] = "emergency"
    with pytest.raises(ProtocolError, match="comes after a less serious question"):
        validate(data)


def test_question_pointing_to_self_care_is_rejected():
    with pytest.raises(ProtocolError, match="self_care"):
        validate(bad(q2_disposition="self_care"))


def test_gaps_in_question_order_are_rejected():
    with pytest.raises(ProtocolError, match="no gaps"):
        validate(bad(orders=[1, 2, 4]))


def test_missing_self_care_advice_is_rejected():
    with pytest.raises(ProtocolError, match="self_care"):
        validate(bad(drop_advice="self_care"))


def test_missing_advice_for_used_level_is_rejected():
    with pytest.raises(ProtocolError, match="urgent"):
        validate(bad(drop_advice="urgent"))


def test_unknown_disposition_is_rejected():
    with pytest.raises(ProtocolError, match="unknown disposition"):
        validate(bad(q1_disposition="critical"))


def test_every_protocol_asks_emergency_questions_first():
    for p in load_all():
        assert p["questions"][0]["disposition"] == "emergency", p["name"]
