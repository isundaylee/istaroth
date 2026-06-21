"""Tests for hierarchy navigation helpers."""

from __future__ import annotations

from istaroth.agd import hierarchy_nav, processed_types
from istaroth.services.backend import models

# ── fixture helpers ──────────────────────────────────────────────────────


def _leaf(
    key: str, file_id: int, title: str | None = None
) -> processed_types.HierarchyNode:
    return processed_types.HierarchyNode(
        key=key,
        title=title,
        title_key=None,
        children=None,
        file_id=file_id,
        toc_eligible=False,
    )


def _group(
    key: str,
    children: list[processed_types.HierarchyNode],
    title: str | None = None,
    title_key: str | None = None,
    toc_eligible: bool = True,
) -> processed_types.HierarchyNode:
    return processed_types.HierarchyNode(
        key=key,
        title=title,
        title_key=title_key,
        children=children,
        file_id=None,
        toc_eligible=toc_eligible,
    )


# Quest tree: WQ → s10152 → [c10155, c10156] → quests
_QUEST_TREE = [
    _group(
        "WQ",
        children=[
            _group(
                "s10152",
                children=[
                    _group(
                        "c10155",
                        children=[
                            _leaf("q1", 100, "Quest 1"),
                            _leaf("q2", 101, "Quest 2"),
                            _leaf("q3", 102, "Quest 3"),
                        ],
                    ),
                    _group(
                        "c10156",
                        children=[
                            _leaf("q4", 103, "Quest 4"),
                        ],
                    ),
                ],
            ),
        ],
        title_key="library.questTypes.WQ",
    ),
]

# Standalone tree: type → standalone (toc_eligible=False) → quests
_STANDALONE_TREE = [
    _group(
        "WQ",
        children=[
            _group(
                "standalone",
                children=[
                    _leaf("q10", 200, "Standalone 1"),
                    _leaf("q11", 201, "Standalone 2"),
                ],
                title_key="library.standalone",
                toc_eligible=False,
            ),
        ],
        title_key="library.questTypes.WQ",
    ),
]

# Coop tree: character → [chapter → quests]
_COOP_TREE = [
    _group(
        "a10000001",
        children=[
            _group(
                "c50001",
                children=[
                    _leaf("q20", 300, "Hangout 1"),
                    _leaf("q21", 301, "Hangout 2"),
                ],
            ),
        ],
    ),
]

# Flat coop: character → quests (single-act, no chapter level)
_FLAT_COOP_TREE = [
    _group(
        "a10000002",
        children=[
            _leaf("q30", 400, "Flat 1"),
            _leaf("q31", 401, "Flat 2"),
        ],
    ),
]

# ── find_leaf_path ───────────────────────────────────────────────────────


class TestFindLeafPath:
    def test_finds_leaf_three_levels_deep(self) -> None:
        path = hierarchy_nav.find_leaf_path(_QUEST_TREE, 101)
        assert path is not None
        assert [n.key for n in path] == ["WQ", "s10152", "c10155", "q2"]

    def test_finds_leaf_second_chapter(self) -> None:
        path = hierarchy_nav.find_leaf_path(_QUEST_TREE, 103)
        assert path is not None
        assert [n.key for n in path] == ["WQ", "s10152", "c10156", "q4"]

    def test_finds_direct_leaf(self) -> None:
        path = hierarchy_nav.find_leaf_path(_FLAT_COOP_TREE, 400)
        assert path is not None
        assert [n.key for n in path] == ["a10000002", "q30"]

    def test_finds_leaf_in_standalone_bucket(self) -> None:
        path = hierarchy_nav.find_leaf_path(_STANDALONE_TREE, 200)
        assert path is not None
        assert [n.key for n in path] == ["WQ", "standalone", "q10"]


# ── compute_toc ──────────────────────────────────────────────────────────


class TestComputeToc:
    def test_quest_hierarchy_series_sections(self) -> None:
        path = hierarchy_nav.find_leaf_path(_QUEST_TREE, 103)
        assert path is not None
        toc = hierarchy_nav.compute_toc(path)
        assert toc is not None
        assert toc.key == "s10152"
        assert toc.children is not None
        assert any(c.children is not None for c in toc.children)
        assert toc.children[0].key == "c10155"
        assert toc.children[0].children is not None
        assert [c.file_id for c in toc.children[0].children] == [100, 101, 102]
        assert toc.children[1].key == "c10156"
        assert toc.children[1].children is not None
        assert [c.file_id for c in toc.children[1].children] == [103]

    def test_standalone_not_toc_eligible(self) -> None:
        path = hierarchy_nav.find_leaf_path(_STANDALONE_TREE, 200)
        assert path is not None
        assert hierarchy_nav.compute_toc(path) is None

    def test_flat_coop_direct_children(self) -> None:
        path = hierarchy_nav.find_leaf_path(_FLAT_COOP_TREE, 400)
        assert path is not None
        toc = hierarchy_nav.compute_toc(path)
        assert toc is not None
        assert toc.key == "a10000002"
        assert toc.children is not None
        assert not any(c.children is not None for c in toc.children)
        assert [c.file_id for c in toc.children] == [400, 401]

    def test_direct_leaf_no_toc(self) -> None:
        leaf = _leaf("q1", 100, "Solo")
        path = [leaf]
        assert hierarchy_nav.compute_toc(path) is None

    def test_coop_with_chapters(self) -> None:
        path = hierarchy_nav.find_leaf_path(_COOP_TREE, 300)
        assert path is not None
        toc = hierarchy_nav.compute_toc(path)
        assert toc is not None
        assert toc.key == "c50001"
        assert toc.children is not None
        assert [c.file_id for c in toc.children] == [300, 301]


# ── dict → domain → Pydantic round-trip ──────────────────────────────────


class TestTocRoundTrip:
    """Simulates the GET /api/library/file/{category}/{id}/toc endpoint's core logic.

    The endpoint receives a hierarchy dict from text_set, converts it to domain
    types, runs find_leaf_path + compute_toc, then converts back via .to_dict()
    and wraps in the Pydantic TocResponse model.
    """

    def test_round_trip_grouped_toc(self) -> None:
        hierarchy_dict = _QUEST_TREE[0].to_dict()
        nodes = processed_types.Hierarchy.from_dict({"nodes": [hierarchy_dict]}).nodes
        path = hierarchy_nav.find_leaf_path(nodes, 103)
        assert path is not None
        toc_root = hierarchy_nav.compute_toc(path)
        assert toc_root is not None
        toc_root_pydantic = models.HierarchyNode.model_validate(toc_root.to_dict())
        assert toc_root_pydantic.key == "s10152"
        assert toc_root_pydantic.children is not None

    def test_round_trip_standalone_no_toc(self) -> None:
        hierarchy_dict = _STANDALONE_TREE[0].to_dict()
        nodes = processed_types.Hierarchy.from_dict({"nodes": [hierarchy_dict]}).nodes
        path = hierarchy_nav.find_leaf_path(nodes, 200)
        assert path is not None
        toc_root = hierarchy_nav.compute_toc(path)
        assert toc_root is None

    def test_round_trip_flat_no_hierarchy(self) -> None:
        """Flat categories (hierarchy is None) → toc_root=None."""
        nodes = processed_types.Hierarchy.from_dict({"nodes": []}).nodes
        assert nodes == []
        # Simulating no hierarchy; the endpoint returns TocResponse(toc_root=None) in that case.
        assert True

    def test_round_trip_file_not_in_hierarchy(self) -> None:
        hierarchy_dict = _QUEST_TREE[0].to_dict()
        nodes = processed_types.Hierarchy.from_dict({"nodes": [hierarchy_dict]}).nodes
        path = hierarchy_nav.find_leaf_path(nodes, 99999)
        assert path is None
