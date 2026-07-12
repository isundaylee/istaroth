"""Hierarchy types consumed by corpus readers.

Deserializes the ``hierarchy/*.json`` files written by the Rust regen
(``HierarchyNode``/``Hierarchy`` in ``rust/istaroth-agd-regen/src/hierarchy.rs``);
the frontend's ``frontend/src/utils/hierarchy.ts`` mirrors them too. Parity
with the Rust side is pinned byte-exactly by the contract tests
(``tests/test_schema_contract.py`` and
``rust/istaroth-agd-regen/tests/contract.rs``, sharing
``tests/fixtures/rust_agd_regen_contract/``).
"""

from __future__ import annotations

from typing import Any

import attrs


@attrs.define
class HierarchyNode:
    """One node in a browsable document hierarchy.

    A node is either a group (``children`` set) or a leaf (``file_id`` set, a
    viewable file). ``title`` is the resolved display label; it is ``None`` only
    in transit before resolution (every persisted node carries a valid title).
    """

    key: str
    """URL-safe identifier, unique among siblings."""
    title: str | None
    children: list[HierarchyNode] | None
    file_id: int | None
    toc_eligible: bool
    """Whether, when this group is a viewed file's section root, its children form
    a coherent table of contents. False for leaves and for synthetic buckets that
    merely collect unrelated files (e.g. the "standalone" group)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "children": (
                None
                if self.children is None
                else [child.to_dict() for child in self.children]
            ),
            "file_id": self.file_id,
            "toc_eligible": self.toc_eligible,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HierarchyNode:
        if set(data) != _NODE_KEYS:
            raise ValueError(
                f"Hierarchy node keys {sorted(data)} != {sorted(_NODE_KEYS)}"
            )
        return cls(
            key=data["key"],
            title=data["title"],
            children=(
                None
                if data["children"] is None
                else [cls.from_dict(child) for child in data["children"]]
            ),
            file_id=data["file_id"],
            toc_eligible=data["toc_eligible"],
        )


@attrs.define
class Hierarchy:
    """The browsable document hierarchy of one category."""

    nodes: list[HierarchyNode]

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [node.to_dict() for node in self.nodes]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hierarchy:
        if set(data) != {"nodes"}:
            raise ValueError(f"Hierarchy keys {sorted(data)} != ['nodes']")
        return cls(nodes=[HierarchyNode.from_dict(node) for node in data["nodes"]])


_NODE_KEYS = frozenset(field.name for field in attrs.fields(HierarchyNode))
