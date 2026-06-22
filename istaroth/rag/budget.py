"""Adaptive retrieval breadth/depth budget allocation via query-intent classification."""

import enum
import math

_K_MAX = 30
_CC_MAX = 10
_CC_MIN = 1


class QueryIntent(str, enum.Enum):
    VARIETY = "variety"
    BALANCED = "balanced"
    CONTEXT = "context"


_INTENT_MAP: dict[str, QueryIntent] = {v.value: v for v in QueryIntent}


def parse_intent(text: str) -> QueryIntent | None:
    return _INTENT_MAP.get(text.strip().lower())


def allocate(budget: int, intent: QueryIntent) -> tuple[int, int]:
    if intent is QueryIntent.VARIETY:
        cc = _CC_MIN
    elif intent is QueryIntent.CONTEXT:
        cc = min(_CC_MAX, max(2, round(math.sqrt(2 * budget + 1) - 1)))
    else:
        cc = max(1, round((math.sqrt(2 * budget + 1) - 1) / 2))
    k = max(1, min(_K_MAX, round(budget / (2 * cc + 1))))
    return k, cc
