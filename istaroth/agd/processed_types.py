"""Hierarchy types consumed by corpus readers."""

from __future__ import annotations

from typing import Any

import attrs


@attrs.define
class HierarchyNode:
    """One group or leaf in a browsable document hierarchy."""

    key: str
    title: str | None
    children: list[HierarchyNode] | None
    file_id: int | None
    toc_eligible: bool

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
        return cls(nodes=[HierarchyNode.from_dict(node) for node in data["nodes"]])
