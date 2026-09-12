"""Unit tests for the deterministic eligibility engine and operators."""

from app.models.enums import MatchLevel
from app.rules import apply_operator, evaluate_program

RULES = [
    {"field": "pmt_score", "operator": "lte", "value": 32, "label": "PMT <= 32", "required": True},
    {"field": "has_cnic", "operator": "is_true", "label": "Has CNIC", "required": True},
    {"field": "gender", "operator": "eq", "value": "female", "label": "Woman", "required": True},
]


def test_operators_numeric_and_membership():
    assert apply_operator("lte", 32, 32) is True
    assert apply_operator("lt", 33, 32) is False
    assert apply_operator("gte", 60, 60) is True
    assert apply_operator("in", "Punjab", ["Punjab", "Sindh"]) is True
    assert apply_operator("not_in", "KP", ["Punjab", "Sindh"]) is True
    assert apply_operator("between", 5, [1, 10]) is True
    assert apply_operator("is_true", True) is True
    assert apply_operator("is_false", False) is True
    assert apply_operator("contains", ["a", "b"], "a") is True


def test_all_required_matched_is_eligible():
    facts = {"pmt_score": 20, "has_cnic": True, "gender": "female"}
    result = evaluate_program(facts, RULES)
    assert result.match_level == MatchLevel.ELIGIBLE
    assert result.score == 1.0
    assert len(result.matched_conditions) == 3
    assert result.failed_conditions == []
    assert result.missing_conditions == []


def test_failed_required_condition_is_not_eligible():
    facts = {"pmt_score": 45, "has_cnic": True, "gender": "female"}
    result = evaluate_program(facts, RULES)
    assert result.match_level == MatchLevel.NOT_ELIGIBLE
    assert len(result.failed_conditions) == 1
    assert result.failed_conditions[0]["field"] == "pmt_score"


def test_missing_required_condition_needs_info():
    facts = {"has_cnic": True, "gender": "female"}  # pmt_score unknown
    result = evaluate_program(facts, RULES)
    assert result.match_level == MatchLevel.NEEDS_INFO
    assert len(result.missing_conditions) == 1
    assert result.missing_conditions[0]["field"] == "pmt_score"


def test_optional_condition_downgrades_to_likely():
    rules = [
        {"field": "pmt_score", "operator": "lte", "value": 32, "label": "PMT", "required": True},
        {"field": "has_bank_account", "operator": "is_true", "label": "Bank", "required": False},
    ]
    facts = {"pmt_score": 10}  # required matched, optional unknown
    result = evaluate_program(facts, rules)
    assert result.match_level == MatchLevel.LIKELY_ELIGIBLE


def test_failed_required_beats_missing():
    facts = {"pmt_score": 99}  # fails required; other required missing
    result = evaluate_program(facts, RULES)
    assert result.match_level == MatchLevel.NOT_ELIGIBLE


def test_empty_rules_needs_info():
    result = evaluate_program({"anything": 1}, [])
    assert result.match_level == MatchLevel.NEEDS_INFO
    assert result.score == 0.0


def test_malformed_value_becomes_missing_not_crash():
    rules = [{"field": "age", "operator": "gte", "value": 60, "label": "Age", "required": True}]
    facts = {"age": "not-a-number"}
    result = evaluate_program(facts, rules)
    # Un-evaluable -> treated as missing (needs human review), never a crash.
    assert result.match_level == MatchLevel.NEEDS_INFO
    assert result.missing_conditions[0]["detail"] is not None


def test_engine_is_deterministic():
    facts = {"pmt_score": 20, "has_cnic": True, "gender": "female"}
    first = evaluate_program(facts, RULES).to_dict()
    second = evaluate_program(facts, RULES).to_dict()
    assert first == second
