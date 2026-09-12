"""Deterministic eligibility rules engine."""

from app.rules.engine import MatchResult, evaluate_program
from app.rules.operators import OPERATORS, apply_operator

__all__ = ["MatchResult", "evaluate_program", "apply_operator", "OPERATORS"]
