"""Tests for the evaluation tools."""
import pytest

from scripts.evaluate import endpoints, run_scenarios
from scripts.sus_score import rating, summarise, sus_score


def test_sus_scoring_matches_the_standard_formula():
    assert sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0
    assert sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0.0
    assert sus_score([3] * 10) == 50.0
    assert sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == 75.0


def test_sus_rejects_bad_answers():
    with pytest.raises(ValueError):
        sus_score([6] * 10)
    with pytest.raises(ValueError):
        sus_score([3] * 9)


def test_sus_ratings():
    assert rating(85) == "Excellent" and rating(70).startswith("Good") and rating(55).startswith("OK") and rating(40) == "Poor"


def test_sus_summary_from_csv(tmp_path):
    f = tmp_path / "r.csv"
    f.write_text("participant,role,years_experience,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,t1,t2,t3,t4,t5\n"
                 "P1,nurse,5,4,2,4,2,4,2,4,2,4,2,Y,Y,Y,N,Y\n"
                 "P2,nurse,8,5,1,5,1,5,1,5,1,5,1,Y,Y,Y,Y,Y\n")
    s = summarise(f)
    assert [v for _, v in s["scores"]] == [75.0, 100.0]
    assert s["tasks"]["T4"] == (1, 2)


def test_scenario_evaluation_has_no_under_triage():
    sc = run_scenarios()
    assert sc["n"] == 40 and sc["correct"] == 40 and sc["under"] == 0


def test_endpoint_count():
    assert endpoints() >= 20
