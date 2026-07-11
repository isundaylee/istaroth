"""Tests for the exactly-once thread-safe cache."""

import threading

import pytest

from istaroth import caching


def test_contended_key_computes_exactly_once() -> None:
    calls = []
    barrier = threading.Barrier(8)
    entered = threading.Event()
    release = threading.Event()

    @caching.threadsafe_cache
    def compute(key: str) -> list[str]:
        calls.append(key)
        entered.set()
        # Hold the winning computation open so the other racers pile up on it.
        assert release.wait(timeout=5)
        return [key]

    results: list[list[str]] = []

    def racer() -> None:
        barrier.wait(timeout=5)
        results.append(compute("k"))

    threads = [threading.Thread(target=racer) for _ in range(8)]
    for t in threads:
        t.start()
    assert entered.wait(timeout=5)
    release.set()
    for t in threads:
        t.join(timeout=5)

    assert calls == ["k"]
    assert len(results) == 8 and all(r is results[0] for r in results)


def test_distinct_keys_compute_distinct_values() -> None:
    @caching.threadsafe_cache
    def compute(key: int) -> list[int]:
        return [key]

    assert compute(1) == [1]
    assert compute(2) == [2]
    assert compute(1) is compute(1)
    assert compute(1) is not compute(2)


def test_failure_is_not_cached_and_retried() -> None:
    calls = []

    @caching.threadsafe_cache
    def flaky(key: str) -> str:
        calls.append(key)
        if len(calls) == 1:
            raise ValueError("first call fails")
        return key

    with pytest.raises(ValueError, match="first call fails"):
        flaky("k")
    assert flaky("k") == "k"
    assert calls == ["k", "k"]


def test_kwargs_participate_in_key() -> None:
    calls = []

    @caching.threadsafe_cache
    def compute(*, key: int) -> int:
        calls.append(key)
        return key

    assert compute(key=1) == 1
    assert compute(key=2) == 2
    assert compute(key=1) == 1
    assert calls == [1, 2]
