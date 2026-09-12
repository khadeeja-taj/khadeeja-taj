"""Comparison operators available to eligibility conditions.

Each operator is a pure function ``(actual, expected) -> bool``. Keeping them
here (rather than inline in the engine) makes the set of allowed comparisons
explicit and unit-testable, and keeps thresholds in data, never in code.
"""

from collections.abc import Callable
from typing import Any


def _num(value: Any) -> float:
    """Coerce to float, raising a clear error for non-numeric input."""
    if isinstance(value, bool):
        # bool is a subclass of int; treat explicitly to avoid surprises.
        raise ValueError("boolean is not a numeric value")
    return float(value)


def _eq(actual: Any, expected: Any) -> bool:
    return actual == expected


def _ne(actual: Any, expected: Any) -> bool:
    return actual != expected


def _lt(actual: Any, expected: Any) -> bool:
    return _num(actual) < _num(expected)


def _lte(actual: Any, expected: Any) -> bool:
    return _num(actual) <= _num(expected)


def _gt(actual: Any, expected: Any) -> bool:
    return _num(actual) > _num(expected)


def _gte(actual: Any, expected: Any) -> bool:
    return _num(actual) >= _num(expected)


def _in(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, (list, tuple, set)):
        raise ValueError("operator 'in' expects a list value")
    return actual in expected


def _not_in(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, (list, tuple, set)):
        raise ValueError("operator 'not_in' expects a list value")
    return actual not in expected


def _contains(actual: Any, expected: Any) -> bool:
    """True if the person's value/collection contains the expected item."""
    if isinstance(actual, (list, tuple, set)):
        return expected in actual
    if isinstance(actual, str):
        return str(expected).lower() in actual.lower()
    return False


def _between(actual: Any, expected: Any) -> bool:
    """expected is a two-item [low, high]; inclusive on both ends."""
    if not isinstance(expected, (list, tuple)) or len(expected) != 2:
        raise ValueError("operator 'between' expects a [low, high] value")
    low, high = expected
    return _num(low) <= _num(actual) <= _num(high)


def _is_true(actual: Any, expected: Any = None) -> bool:
    return bool(actual) is True


def _is_false(actual: Any, expected: Any = None) -> bool:
    return bool(actual) is False


OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": _eq,
    "ne": _ne,
    "lt": _lt,
    "lte": _lte,
    "gt": _gt,
    "gte": _gte,
    "in": _in,
    "not_in": _not_in,
    "contains": _contains,
    "between": _between,
    "is_true": _is_true,
    "is_false": _is_false,
}


def apply_operator(operator: str, actual: Any, expected: Any = None) -> bool:
    """Evaluate a single comparison.

    Raises ``KeyError`` for an unknown operator and ``ValueError`` when the
    value types don't fit the operator (e.g. ``lt`` on a non-number).
    """
    if operator not in OPERATORS:
        raise KeyError(f"Unknown operator: {operator!r}")
    return OPERATORS[operator](actual, expected)
