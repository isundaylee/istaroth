"""Thread-safe caching primitives."""

import concurrent.futures
import functools
import threading
from typing import Any, Callable, Iterable, ParamSpec, TypeVar, cast

_K = TypeVar("_K")
_P = ParamSpec("_P")
_R = TypeVar("_R")


def warm_concurrently(fn: Callable[[_K], Any], keys: Iterable[_K]) -> None:
    """Warm a cached single-key loader over many keys in a thread pool.

    Purely a performance pass in front of a serial loop over the same keys:
    failures are swallowed here because failed computations are not cached, so
    the serial loop retries them and surfaces the exception at its
    deterministic point.
    """

    def _warm_one(key: _K) -> None:
        try:
            fn(key)
        except Exception:
            pass

    with concurrent.futures.ThreadPoolExecutor() as pool:
        list(pool.map(_warm_one, keys))


def threadsafe_cache(fn: Callable[_P, _R]) -> Callable[_P, _R]:
    """Unbounded cache with exactly-once-per-key computation under threads.

    Unlike ``functools.lru_cache`` on the free-threaded build -- where
    concurrent misses on the same key can compute the value twice and hand
    different callers different objects -- losers of the insertion race block
    until the one winning computation finishes and then share its result
    object. Different keys compute fully concurrently. Failures are not
    cached: waiters see the winner's exception, and later callers retry.
    Same-key recursion deadlocks rather than infinitely recursing.
    """
    results: dict[Any, _R] = {}
    pending: dict[Any, concurrent.futures.Future[_R]] = {}
    lock = threading.Lock()
    missing = object()

    @functools.wraps(fn)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        key = (args, frozenset(kwargs.items())) if kwargs else args
        # Lock-free hit path: per-key dict reads are thread-safe on the
        # free-threaded build, and a key never changes value once present.
        if (value := results.get(key, missing)) is not missing:
            return cast(_R, value)
        with lock:
            if (value := results.get(key, missing)) is not missing:
                return cast(_R, value)
            if (future := pending.get(key)) is not None:
                computing = False
            else:
                future = pending[key] = concurrent.futures.Future()
                computing = True
        if not computing:
            return future.result()
        try:
            value = fn(*args, **kwargs)
        except BaseException as e:
            with lock:
                del pending[key]
            future.set_exception(e)
            raise
        results[key] = cast(_R, value)
        with lock:
            del pending[key]
        future.set_result(cast(_R, value))
        return cast(_R, value)

    return wrapper
