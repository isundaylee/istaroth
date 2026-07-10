"""Tests for scope-local access tracking."""

import concurrent.futures
import threading

from istaroth.agd import tracking


def test_concurrent_scopes_record_independently() -> None:
    """Scopes on concurrent threads sharing one tracker don't see each other's accesses."""
    tracker = tracking.DictTracker({key: f"item {key}" for key in range(20)})
    barrier = threading.Barrier(2)

    def run_item(item: int) -> set[int]:
        with tracking.TrackingScope(
            {tracking.TrackerKind.TALK: tracker}, item_type="test", item_key=str(item)
        ) as scope:
            assert tracker.get(item) is not None
            # Hold both scopes open simultaneously so a shared accessed set
            # (the pre-scope-local design) would mix the two items' ids.
            barrier.wait()
            assert tracker.get(item + 10) is not None
        return scope.accessed_ids[tracking.TrackerKind.TALK]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(run_item, [1, 2])
    assert first == {1, 11}
    assert second == {2, 12}


def test_scope_ignores_unobserved_tracker() -> None:
    """Accesses through a tracker the scope doesn't observe are dropped."""
    observed = tracking.DictTracker({1: "a"})
    unobserved = tracking.DictTracker({2: "b"})

    with tracking.TrackingScope(
        {tracking.TrackerKind.TALK: observed}, item_type="test", item_key="test"
    ) as scope:
        assert observed.get(1) == "a"
        assert unobserved.get(2) == "b"
    assert scope.accessed_ids == {tracking.TrackerKind.TALK: {1}}
