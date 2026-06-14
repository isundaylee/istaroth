"""Collection of non-fatal parsing issues (data gaps) surfaced during a run.

Per-item parsing stays strict for unexpected data, but some conditions are
non-fatal data gaps handled inline by emitting a placeholder (e.g. a
``COMPLETE_TALK`` pointing at an absent talk). Each such site calls ``record``,
which appends to the currently-active ``IssueTracker`` so the gaps can be
aggregated and reported instead of being buried in the output.

A caller collects per scope by creating a fresh ``IssueTracker`` and entering its
``apply`` context, which installs it as the active tracker for the duration.
``record`` outside any active context is a no-op, so ad hoc callers (CLI render,
web backend) record nothing.
"""

import contextlib
import enum
from typing import ClassVar, Iterator

import attrs


class IssueType(enum.Enum):
    """Category of a non-fatal parsing gap."""

    MISSING_TALK = "missing_talk"
    MISSING_DIALOG = "missing_dialog"
    MISSING_TEXT = "missing_text"
    UNKNOWN_ROLE = "unknown_role"
    MISSING_QUEST_TITLE = "missing_quest_title"
    MISSING_STORY_CONTENT = "missing_story_content"
    MISSING_MATERIAL_NAME = "missing_material_name"
    MISSING_MATERIAL_DESC = "missing_material_desc"
    MISSING_READABLE_TITLE = "missing_readable_title"


@attrs.define
class ParsingIssue:
    """A single recorded non-fatal parsing gap, stamped with its owning item."""

    issue_type: IssueType
    item_type: str
    item_key: str
    detail: str


class IssueTracker:
    """Accumulator of non-fatal parsing gaps for a single scope."""

    _active: ClassVar["IssueTracker | None"] = None

    def __init__(self) -> None:
        self.issues: list[tuple[IssueType, str]] = []

    @contextlib.contextmanager
    def apply(self) -> Iterator["IssueTracker"]:
        """Install this tracker as the active one for the duration of the block."""
        previous = IssueTracker._active
        IssueTracker._active = self
        try:
            yield self
        finally:
            IssueTracker._active = previous


def record(issue_type: IssueType, detail: str) -> None:
    """Record a non-fatal gap into the active tracker, or no-op if none active."""
    if IssueTracker._active is not None:
        IssueTracker._active.issues.append((issue_type, detail))
