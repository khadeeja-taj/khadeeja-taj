"""The deterministic eligibility engine.

Contract (from the brief):
    Input : structured UserSituation facts + a Program's eligibility_rules
    Output: matched_conditions, failed_conditions, missing_conditions,
            match_level + score

Core principle: the LLM may EXTRACT facts, but this Python code DECIDES whether
each published condition is matched, failed, or still unknown. No thresholds are
ever invented at runtime — they come only from the program's rule data.

Condition shape (one entry in Program.eligibility_rules)::

    {
        "field": "pmt_score",          # key looked up in the user's facts
        "operator": "lte",            # see app/rules/operators.py
        "value": 32,                   # threshold from the published policy
        "label": "PMT poverty score is 32 or below",  # human explanation
        "required": true               # optional, defaults to true
    }
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.enums import MatchLevel
from app.rules.operators import apply_operator


@dataclass
class EvaluatedCondition:
    """One condition after evaluation, kept for transparency to the user."""

    field: str
    operator: str
    value: Any
    label: str
    required: bool
    status: str  # "matched" | "failed" | "missing"
    actual: Any = None  # the person's value (None when missing)
    detail: str | None = None  # e.g. an error explanation

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    """Aggregate outcome for one program."""

    match_level: MatchLevel
    score: float
    matched_conditions: list[dict] = field(default_factory=list)
    failed_conditions: list[dict] = field(default_factory=list)
    missing_conditions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "match_level": self.match_level.value,
            "score": self.score,
            "matched_conditions": self.matched_conditions,
            "failed_conditions": self.failed_conditions,
            "missing_conditions": self.missing_conditions,
        }


def _fact_is_present(facts: dict, key: str) -> bool:
    return key in facts and facts[key] is not None


def _evaluate_condition(
    facts: dict, condition: dict
) -> EvaluatedCondition:
    field_name = condition["field"]
    operator = condition["operator"]
    value = condition.get("value")
    label = condition.get("label", f"{field_name} {operator} {value}")
    required = bool(condition.get("required", True))

    # Unknown fact -> the condition is "missing", never a silent failure.
    if not _fact_is_present(facts, field_name):
        return EvaluatedCondition(
            field=field_name,
            operator=operator,
            value=value,
            label=label,
            required=required,
            status="missing",
            actual=None,
        )

    actual = facts[field_name]
    try:
        ok = apply_operator(operator, actual, value)
    except (KeyError, ValueError, TypeError) as exc:
        # A malformed rule/value never crashes matching; it becomes "missing"
        # so a human can review rather than the person getting a false result.
        return EvaluatedCondition(
            field=field_name,
            operator=operator,
            value=value,
            label=label,
            required=required,
            status="missing",
            actual=actual,
            detail=f"could not evaluate: {exc}",
        )

    return EvaluatedCondition(
        field=field_name,
        operator=operator,
        value=value,
        label=label,
        required=required,
        status="matched" if ok else "failed",
        actual=actual,
    )


def _decide_level(evaluated: list[EvaluatedCondition]) -> MatchLevel:
    """Turn per-condition outcomes into an overall match level.

    Required conditions govern eligibility; optional conditions only soften a
    clean "eligible" to "likely".
    """
    if not evaluated:
        # No published conditions -> we cannot deny; needs human/info.
        return MatchLevel.NEEDS_INFO

    required = [c for c in evaluated if c.required]
    optional = [c for c in evaluated if not c.required]

    # A hard fail on any required condition rules the program out.
    if any(c.status == "failed" for c in required):
        return MatchLevel.NOT_ELIGIBLE

    # Any required fact still unknown -> we need more info before deciding.
    if any(c.status == "missing" for c in required):
        return MatchLevel.NEEDS_INFO

    # All required conditions matched here.
    optional_unclean = any(c.status != "matched" for c in optional)
    if optional_unclean:
        return MatchLevel.LIKELY_ELIGIBLE
    return MatchLevel.ELIGIBLE


def evaluate_program(
    user_facts: dict[str, Any], eligibility_rules: list[dict]
) -> MatchResult:
    """Evaluate one person's facts against one program's published rules.

    This function is pure and deterministic: same inputs -> same output.
    """
    user_facts = user_facts or {}
    eligibility_rules = eligibility_rules or []

    evaluated = [_evaluate_condition(user_facts, cond) for cond in eligibility_rules]

    matched = [c.to_dict() for c in evaluated if c.status == "matched"]
    failed = [c.to_dict() for c in evaluated if c.status == "failed"]
    missing = [c.to_dict() for c in evaluated if c.status == "missing"]

    total = len(evaluated)
    score = round(len(matched) / total, 3) if total else 0.0

    return MatchResult(
        match_level=_decide_level(evaluated),
        score=score,
        matched_conditions=matched,
        failed_conditions=failed,
        missing_conditions=missing,
    )
