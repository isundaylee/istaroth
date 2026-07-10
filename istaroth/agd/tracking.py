"""Per-item access tracking: id trackers, their unified scope, and aggregate stats.

A single :class:`TrackingScope` wraps everything collected while processing one
renderable item: which ids each tracked resource touched (keyed by
:class:`TrackerKind`) and the non-fatal :class:`issues.ParsingIssue`s recorded
inline. The accessed-id sets live on the scope itself: entering the scope
installs it in a ``contextvars.ContextVar`` (and installs the active
``IssueTracker``), and each tracker access records into the installed scope.
Trackers themselves are read-only lookup data, so concurrent items -- each in
its own thread or process with its own scope -- never see each other's
accesses. :class:`TrackerStats` aggregates the per-item scopes across a whole
run.

Adding a new tracked resource is two edits: a :class:`TrackerKind` member and a
line in ``DataRepo.build_scope_trackers`` -- everything else keys off the enum.
"""

import contextlib
import contextvars
import enum
from typing import Any, Generic, TypeVar

import attrs

from istaroth.agd import issues

_K = TypeVar("_K")
_V = TypeVar("_V")


class TrackerKind(enum.Enum):
    """A per-item tracked resource; the value is its key in the unused-stats JSON."""

    TEXT_MAP = "text_map"
    TALK = "talk_ids"
    READABLES = "readables"

    @property
    def json_key(self) -> str:
        """The resource's key in the unused-stats JSON."""
        return self.value

    @property
    def label(self) -> str:
        """The resource's human-readable label in console output."""
        return {
            TrackerKind.TEXT_MAP: "Text map",
            TrackerKind.TALK: "Talk IDs",
            TrackerKind.READABLES: "Readables",
        }[self]


_active_scope: contextvars.ContextVar["TrackingScope | None"] = contextvars.ContextVar(
    "active_tracking_scope", default=None
)


class IdTracker(Generic[_K]):
    """Base class for tracking which IDs have been accessed.

    Generic over the id type ``_K``: readable filenames are ``str``, while
    text-map hashes, talk, and material ids are ``int`` (their wire type).

    The tracker itself is read-only lookup data (safe to share across
    concurrent items); accesses are recorded into the :class:`TrackingScope`
    active in the current context, or dropped when none is (e.g. ad hoc CLI
    render, web backend).
    """

    def __init__(self, all_ids: set[_K]) -> None:
        self._all_ids = all_ids

    def _track_access(self, key: _K) -> None:
        """Track that an ID has been accessed."""
        if (scope := _active_scope.get()) is not None:
            scope._record_access(self, key)

    def get_all_ids(self) -> set[_K]:
        return self._all_ids.copy()

    def has(self, key: _K) -> bool:
        """Whether key is a known ID, without tracking access."""
        return key in self._all_ids

    def get_unused_ids(self, accessed_ids: set[_K]) -> set[_K]:
        """Return set of unused IDs given a run's accessed IDs."""
        return self._all_ids - accessed_ids

    def get_total_count(self) -> int:
        """Return total count of all IDs."""
        return len(self._all_ids)

    def format_unused_stats(self, accessed_ids: set[_K]) -> str:
        """Format unused statistics as 'unused / total (percentage%)'."""
        unused_count = len(self.get_unused_ids(accessed_ids))
        total_count = self.get_total_count()
        percentage = (unused_count / total_count * 100) if total_count > 0 else 0.0
        return f"{unused_count} / {total_count} ({percentage:.1f}%)"


class DictTracker(IdTracker[_K], Generic[_K, _V]):
    """Access-tracking wrapper over an id-keyed mapping of items."""

    def __init__(self, items: dict[_K, _V]) -> None:
        self._items = items
        super().__init__(set(items))

    def get(self, key: _K) -> _V | None:
        """Get item by ID and track access."""
        if (item := self._items.get(key)) is not None:
            self._track_access(key)
        return item

    def get_untracked(self, key: _K) -> _V | None:
        """Get item by ID without recording access."""
        return self._items.get(key)

    def get_all(self) -> list[_V]:
        """Get all items without tracking (for discovery purposes)."""
        return list(self._items.values())


class TrackingScope:
    """Collects access + issue side-data for a single item's processing.

    Enter the scope around ``renderable_type.process(...)``; while entered it is
    the context's active scope, so tracker accesses record into
    :attr:`accessed_ids` (accesses through trackers it doesn't observe are
    dropped). Read :attr:`accessed_ids` and :attr:`issues` after the block.
    """

    def __init__(
        self,
        trackers: dict[TrackerKind, IdTracker[Any]],
        *,
        item_type: str,
        item_key: str,
    ) -> None:
        self._kind_by_tracker = {tracker: kind for kind, tracker in trackers.items()}
        self._issue_tracker = issues.IssueTracker(
            item_type=item_type, item_key=item_key
        )
        self._stack = contextlib.ExitStack()
        self._entered = False
        self._scope_token: contextvars.Token["TrackingScope | None"] | None = None
        self.accessed_ids: dict[TrackerKind, set[Any]] = {
            kind: set() for kind in trackers
        }

    def __enter__(self) -> "TrackingScope":
        # A second entry would keep accumulating into the first entry's sets and
        # confuse the item attribution. Enter each scope once.
        if self._entered:
            raise RuntimeError("TrackingScope is not reentrant")
        self._entered = True
        self._scope_token = _active_scope.set(self)
        self._stack.enter_context(self._issue_tracker.apply())
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._stack.close()
        assert self._scope_token is not None
        _active_scope.reset(self._scope_token)

    def _record_access(self, tracker: IdTracker[Any], key: Any) -> None:
        """Record an id access from one of the observed trackers."""
        if (kind := self._kind_by_tracker.get(tracker)) is not None:
            self.accessed_ids[kind].add(key)

    @property
    def issues(self) -> list[issues.ParsingIssue]:
        """Non-fatal parsing issues recorded during the scope, stamped with the item."""
        return self._issue_tracker.issues


@attrs.define
class TrackerStats:
    """Accessed ids per tracked resource, aggregated across items in a run."""

    accessed: dict[TrackerKind, set[Any]]

    @classmethod
    def empty(cls) -> "TrackerStats":
        """A stats object with an empty accessed set for every tracker kind."""
        return cls({kind: set() for kind in TrackerKind})

    def update(self, other: "TrackerStats") -> None:
        """Merge another stats object's accessed ids into this one."""
        for kind, ids in other.accessed.items():
            self.accessed.setdefault(kind, set()).update(ids)

    def to_dict(self, trackers: dict[TrackerKind, IdTracker[Any]]) -> dict[str, Any]:
        """Serialize unused/total counts and unused ids, keyed by tracker JSON key."""
        unused = {
            kind: tracker.get_unused_ids(self.accessed[kind])
            for kind, tracker in trackers.items()
        }
        return {
            "stats": {
                kind.json_key: {
                    "unused": len(unused[kind]),
                    "total": tracker.get_total_count(),
                }
                for kind, tracker in trackers.items()
            },
            "unused_ids": {kind.json_key: sorted(unused[kind]) for kind in trackers},
        }
