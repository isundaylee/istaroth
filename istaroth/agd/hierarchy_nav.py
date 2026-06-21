"""Canonical hierarchy navigation logic.

Port of the frontend's findLeafPath, flattenLeaves, and TOC-building helpers
(``frontend/src/utils/hierarchy.ts``, ``frontend/src/LibraryFileViewer.tsx``)
so that MCP tools and future backend callers share one implementation.
"""

from __future__ import annotations

from istaroth.agd import processed_types


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


def compute_toc(
    path: list[processed_types.HierarchyNode],
) -> processed_types.HierarchyNode | None:
    """Return the TOC root node for a file's leaf path, or ``None``.

    The TOC is rooted at the ancestor just below the top-level type/character
    node (``ancestors[1]`` when depth ≥ 3, else ``ancestors[0]`` at depth 2).
    Only nodes that mark themselves ``toc_eligible`` get a TOC; synthetic
    buckets of unrelated files (e.g. the *standalone* group) opt out.

    The caller inspects ``root.children`` to determine the display:
    - If any child has ``children`` → grouped sections (each group node is a
      titled section with leaf children).
    - If all children are direct leaves → flat list (one untitled section).
    """
    ancestors = path[:-1]
    if len(ancestors) == 0:
        return None

    toc_candidate = ancestors[1] if len(ancestors) >= 2 else ancestors[0]
    if not toc_candidate.toc_eligible or toc_candidate.children is None:
        return None

    return toc_candidate
