"""Tests for the adaptive budget allocation module."""

import pytest

from istaroth.rag import budget


def test_parse_variety() -> None:
    assert budget.parse_intent("variety") is budget.QueryIntent.VARIETY


def test_parse_balanced() -> None:
    assert budget.parse_intent("balanced") is budget.QueryIntent.BALANCED


def test_parse_context() -> None:
    assert budget.parse_intent("context") is budget.QueryIntent.CONTEXT


def test_parse_case_insensitive() -> None:
    assert budget.parse_intent("VARIETY") is budget.QueryIntent.VARIETY
    assert budget.parse_intent("Balanced") is budget.QueryIntent.BALANCED
    assert budget.parse_intent("CONTEXT") is budget.QueryIntent.CONTEXT


def test_parse_unknown_returns_none() -> None:
    assert budget.parse_intent("unknown") is None
    assert budget.parse_intent("") is None
    assert budget.parse_intent("deep") is None


def test_parse_whitespace_handling() -> None:
    assert budget.parse_intent("  variety  ") is budget.QueryIntent.VARIETY
    assert budget.parse_intent("\tbalanced\n") is budget.QueryIntent.BALANCED


@pytest.mark.parametrize(
    ("b", "intent", "expected_k", "expected_cc"),
    [
        (110, budget.QueryIntent.VARIETY, 30, 1),
        (35, budget.QueryIntent.VARIETY, 12, 1),
        (12, budget.QueryIntent.VARIETY, 4, 1),
        (110, budget.QueryIntent.BALANCED, 7, 7),
        (35, budget.QueryIntent.BALANCED, 4, 4),
        (12, budget.QueryIntent.BALANCED, 2, 2),
        (110, budget.QueryIntent.CONTEXT, 5, 10),
        (35, budget.QueryIntent.CONTEXT, 2, 7),
        (12, budget.QueryIntent.CONTEXT, 1, 4),
        (400, budget.QueryIntent.VARIETY, 30, 1),
        (400, budget.QueryIntent.CONTEXT, 19, 10),
        (3, budget.QueryIntent.VARIETY, 1, 1),
        (3, budget.QueryIntent.BALANCED, 1, 1),
        (3, budget.QueryIntent.CONTEXT, 1, 2),
    ],
)
def test_allocations(
    b: int, intent: budget.QueryIntent, expected_k: int, expected_cc: int
) -> None:
    k, cc = budget.allocate(b, intent)
    assert (k, cc) == (expected_k, expected_cc)
