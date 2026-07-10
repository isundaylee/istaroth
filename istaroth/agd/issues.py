"""Collection of non-fatal parsing issues (data gaps) surfaced during a run.

Per-item parsing stays strict for unexpected data, but some conditions are
non-fatal data gaps handled inline by emitting a placeholder (e.g. a
``COMPLETE_TALK`` pointing at an absent talk). Each such site calls ``record``,
which appends to the currently-active ``IssueTracker`` so the gaps can be
aggregated and reported instead of being buried in the output.

A caller collects per scope by creating a fresh ``IssueTracker`` (stamped with the
owning item's identity) and entering its ``apply`` context, which installs it as
the active tracker for the duration. The active tracker lives in a
``ContextVar``, so concurrent threads/tasks each see only their own tracker.
``record`` builds a fully-stamped
``ParsingIssue`` from that identity; outside any active context it is a no-op, so
ad hoc callers (CLI render, web backend) record nothing.
"""

import contextlib
import contextvars
import enum
from typing import ClassVar, Iterator

import attrs


class IssueType(enum.Enum):
    """Category of a non-fatal parsing gap.

    Reported by member name (``.name``); the values only need to be distinct, so
    ``auto()`` is used rather than hand-written strings.
    """

    MISSING_TALK = enum.auto()
    MISSING_DIALOG = enum.auto()
    MISSING_TEXT = enum.auto()
    UNKNOWN_ROLE = enum.auto()
    MISSING_QUEST_TITLE = enum.auto()
    MISSING_STORY_CONTENT = enum.auto()
    MISSING_MATERIAL_NAME = enum.auto()
    MISSING_MATERIAL_DESC = enum.auto()
    MISSING_READABLE_TITLE = enum.auto()


@attrs.define
class ParsingIssue:
    """A single recorded non-fatal parsing gap, stamped with its owning item."""

    issue_type: IssueType
    item_type: str
    item_key: str
    detail: str


class IssueTracker:
    """Accumulator of non-fatal parsing gaps for a single item's scope.

    Stamped with the owning item's ``item_type``/``item_key`` so ``record`` can
    produce fully-formed :class:`ParsingIssue`s without the caller re-stamping.
    """

    _active: ClassVar[contextvars.ContextVar["IssueTracker | None"]] = (
        contextvars.ContextVar("istaroth_agd_issues_active_tracker", default=None)
    )

    def __init__(self, *, item_type: str, item_key: str) -> None:
        self._item_type = item_type
        self._item_key = item_key
        self.issues: list[ParsingIssue] = []

    @contextlib.contextmanager
    def apply(self) -> Iterator["IssueTracker"]:
        """Install this tracker as the active one for the duration of the block."""
        token = IssueTracker._active.set(self)
        try:
            yield self
        finally:
            IssueTracker._active.reset(token)

    def record(self, issue_type: IssueType, detail: str) -> None:
        """Append a gap stamped with this tracker's owning item identity."""
        self.issues.append(
            ParsingIssue(
                issue_type=issue_type,
                item_type=self._item_type,
                item_key=self._item_key,
                detail=detail,
            )
        )


def record(issue_type: IssueType, detail: str) -> None:
    """Record a non-fatal gap into the active tracker, or no-op if none active."""
    if (active := IssueTracker._active.get()) is not None:
        active.record(issue_type, detail)
