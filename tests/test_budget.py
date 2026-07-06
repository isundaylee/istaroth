"""Tests for the adaptive budget allocation module."""

import pytest

from istaroth.rag import budget


def test_parse_variety() -> None:
    assert budget.parse_intent("variety") is budget.QueryIntent.VARIETY


def test_parse_balanced() -> None:
    assert budget.parse_intent("balanced") is budget.QueryIntent.BALANCED


def test_parse_context() -> None:
    assert budget.parse_intent("context") is budget.QueryIntent.CONTEXT


def test_parse_lookup() -> None:
    assert budget.parse_intent("lookup") is budget.QueryIntent.LOOKUP


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
    ("b", "intent", "expected_tiers"),
    [
        (110, budget.QueryIntent.VARIETY, ((55, 1), (55, 0))),
        (35, budget.QueryIntent.VARIETY, ((17, 1), (18, 0))),
        (12, budget.QueryIntent.VARIETY, ((6, 1), (6, 0))),
        (110, budget.QueryIntent.BALANCED, ((110, 7),)),
        (35, budget.QueryIntent.BALANCED, ((35, 4),)),
        (12, budget.QueryIntent.BALANCED, ((12, 2),)),
        (110, budget.QueryIntent.CONTEXT, ((110, 10),)),
        (35, budget.QueryIntent.CONTEXT, ((35, 7),)),
        (12, budget.QueryIntent.CONTEXT, ((12, 4),)),
        (110, budget.QueryIntent.LOOKUP, ((110, 0),)),
        (15, budget.QueryIntent.LOOKUP, ((15, 0),)),
        (3, budget.QueryIntent.VARIETY, ((1, 1), (2, 0))),
        (3, budget.QueryIntent.BALANCED, ((3, 1),)),
        (3, budget.QueryIntent.CONTEXT, ((3, 2),)),
        # A one-chunk variety budget has no room for a deep tier.
        (1, budget.QueryIntent.VARIETY, ((1, 0),)),
    ],
)
def test_allocations(
    b: int, intent: budget.QueryIntent, expected_tiers: tuple[tuple[int, int], ...]
) -> None:
    schedule = budget.allocate(b, intent)
    assert tuple((t.chunks, t.window) for t in schedule.tiers) == expected_tiers
    assert schedule.total_chunks == b


def test_allocate_rejects_non_positive_budget() -> None:
    with pytest.raises(ValueError):
        budget.allocate(0, budget.QueryIntent.BALANCED)


def test_schedule_window_at() -> None:
    schedule = budget.allocate(110, budget.QueryIntent.VARIETY)
    assert schedule.window_at(0) == 1
    assert schedule.window_at(54) == 1
    assert schedule.window_at(55) == 0
    assert schedule.window_at(109) == 0
    with pytest.raises(ValueError):
        schedule.window_at(110)


def test_schedule_nominal_hits() -> None:
    assert budget.allocate(110, budget.QueryIntent.VARIETY).nominal_hits == 74
    assert budget.allocate(110, budget.QueryIntent.LOOKUP).nominal_hits == 110
    assert budget.allocate(110, budget.QueryIntent.BALANCED).nominal_hits == 8
