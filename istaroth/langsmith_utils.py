import functools
from typing import Callable, ParamSpec, TypeVar

import langsmith
from torch import Type

T = TypeVar("T")
P = ParamSpec("P")


def traceable(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to make a function traceable in LangSmith."""

    def decorator(f: Callable[P, T]) -> Callable[P, T]:
        @langsmith.traceable(name=name)
        @functools.wraps(f)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            """Wrapped function to apply traceable decorator."""
            return f(*args, **kwargs)

        return wrapped

    return decorator
