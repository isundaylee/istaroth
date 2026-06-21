"""Canonical hierarchy navigation logic.

Port of the frontend's findLeafPath, flattenLeaves, and TOC-building helpers
(``frontend/src/utils/hierarchy.ts``, ``frontend/src/LibraryFileViewer.tsx``)
so that MCP tools and future backend callers share one implementation.
"""

from __future__ import annotations

import attrs

from istaroth.agd import processed_types


@attrs.define
class TocSection:
    """One section of a table of contents.

    ``title`` is ``None`` when the section groups direct children of the TOC
    root (the flat/untitled case).
    """

    title: processed_types.HierarchyNode | None
    leaves: list[processed_types.HierarchyNode]


@attrs.define
class Toc:
    """A computed table of contents for a file's narrative container."""

    root: processed_types.HierarchyNode
    sections: list[TocSection]


def find_leaf_path(
    nodes: list[processed_types.HierarchyNode], file_id: int
) -> list[processed_types.HierarchyNode] | None:
    """Return the chain from a root down to (and including) the leaf with ``file_id``.

    Returns ``None`` when no leaf carries the given id.
    """
    for node in nodes:
        if node.file_id == file_id:
            return [node]
        if node.children is not None:
            sub = find_leaf_path(node.children, file_id)
            if sub is not None:
                return [node, *sub]
    return None


def flatten_leaves(
    nodes: list[processed_types.HierarchyNode],
) -> list[processed_types.HierarchyNode]:
    """All leaf nodes under *nodes*, in depth-first order."""
    leaves: list[processed_types.HierarchyNode] = []

    def _walk(node: processed_types.HierarchyNode) -> None:
        if node.children is None:
            if node.file_id is not None:
                leaves.append(node)
            return
        for child in node.children:
            _walk(child)

    for node in nodes:
        _walk(node)
    return leaves


def compute_toc(path: list[processed_types.HierarchyNode]) -> Toc | None:
    """Compute the table of contents for a file from its leaf path.

    The TOC is rooted at the section node (the ancestor just below the top-level
    type/character node).  Only sections that mark themselves ``toc_eligible``
    get a TOC; synthetic buckets of unrelated files (e.g. the *standalone* group)
    opt out.

    Returns ``None`` when the file has no hierarchy placement or its section is
    not TOC-eligible.
    """
    ancestors = path[:-1]

    toc_candidate: processed_types.HierarchyNode | None
    if len(ancestors) >= 2:
        toc_candidate = ancestors[1]
    elif len(ancestors) == 1:
        toc_candidate = ancestors[0]
    else:
        toc_candidate = None

    toc_root = (
        toc_candidate
        if (toc_candidate is not None and toc_candidate.toc_eligible)
        else None
    )
    if toc_root is None or toc_root.children is None:
        return None

    sections: list[TocSection] = []
    if any(child.children is not None for child in toc_root.children):
        for group in toc_root.children:
            sections.append(TocSection(title=group, leaves=flatten_leaves([group])))
    else:
        sections.append(TocSection(title=None, leaves=list(toc_root.children)))

    return Toc(root=toc_root, sections=sections)
