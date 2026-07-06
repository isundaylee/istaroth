"""Adaptive retrieval breadth/depth budget allocation via query-intent classification."""

import enum
import math

import attrs

_CC_MAX = 10


class QueryIntent(str, enum.Enum):
    VARIETY = "variety"
    BALANCED = "balanced"
    CONTEXT = "context"
    # Flat single-chunk enumeration (e.g. library search); never emitted by the
    # question-preprocessing classifier.
    LOOKUP = "lookup"


_INTENT_MAP: dict[str, QueryIntent] = {v.value: v for v in QueryIntent}


def parse_intent(text: str) -> QueryIntent | None:
    return _INTENT_MAP.get(text.strip().lower())


@attrs.frozen
class Tier:
    """A slice of the chunk budget spent at a fixed ±window expansion."""

    chunks: int
    window: int


@attrs.frozen
class Schedule:
    """Ordered depth tiers consumed as retrieval walks the reranked list."""

    tiers: tuple[Tier, ...]

    @property
    def total_chunks(self) -> int:
        return sum(t.chunks for t in self.tiers)

    @property
    def nominal_files(self) -> int:
        """Distinct files selected if every hit consumes its full window.

        An estimate for sizing candidate fetch depth, not a hard cap: windows
        clipped at file boundaries or overlapping earlier hits consume fewer
        chunks, so the actual file count can run higher (bounded by budget).
        """
        return sum(math.ceil(t.chunks / (2 * t.window + 1)) for t in self.tiers)

    def window_at(self, consumed: int) -> int:
        """Window size for a hit landing after `consumed` chunks are spent."""
        boundary = 0
        for tier in self.tiers:
            boundary += tier.chunks
            if consumed < boundary:
                return tier.window
        raise ValueError(f"Chunk budget exhausted at {consumed} chunks")


def allocate(budget: int, intent: QueryIntent) -> Schedule:
    """Shape a context budget (total chunks) into a depth schedule per intent."""
    if budget < 1:
        raise ValueError(f"Budget must be positive, got {budget}")
    tiers: tuple[Tier, ...]
    match intent:
        case QueryIntent.LOOKUP:
            tiers = (Tier(chunks=budget, window=0),)
        case QueryIntent.VARIETY:
            # Half the budget on ±1 windows for top hits, half on a
            # single-chunk breadth tail.
            deep = budget // 2
            tiers = (
                Tier(chunks=deep, window=1),
                Tier(chunks=budget - deep, window=0),
            )
        case QueryIntent.BALANCED:
            cc = max(1, round((math.sqrt(2 * budget + 1) - 1) / 2))
            tiers = (Tier(chunks=budget, window=cc),)
        case QueryIntent.CONTEXT:
            cc = min(_CC_MAX, max(2, round(math.sqrt(2 * budget + 1) - 1)))
            tiers = (Tier(chunks=budget, window=cc),)
    return Schedule(tiers=tuple(t for t in tiers if t.chunks > 0))
