from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar

import langsmith as ls

T = TypeVar("T")
P = ParamSpec("P")

if TYPE_CHECKING:
    from istaroth.rag.types import ScoredDocument


def traceable(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to make a function traceable in LangSmith."""

    def decorator(f: Callable[P, T]) -> Callable[P, T]:
        @ls.traceable(name=name)
        @functools.wraps(f)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            """Wrapped function to apply traceable decorator."""
            return f(*args, **kwargs)

        return wrapped

    return decorator


def log_scored_docs(name: str, scored_documents: list[ScoredDocument]) -> None:
    with ls.trace(name, "retriever") as rt:
        rt.end(
            outputs={"documents": [sd.to_langsmith_output() for sd in scored_documents]}
        )
