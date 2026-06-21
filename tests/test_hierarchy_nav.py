"""Tests for hierarchy navigation helpers."""

from __future__ import annotations

from istaroth.agd import hierarchy_nav, processed_types

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


def _empty_group(key: str) -> processed_types.HierarchyNode:
    return processed_types.HierarchyNode(
        key=key,
        title=None,
        title_key=None,
        children=[],
        file_id=None,
        toc_eligible=True,
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

# Empty group
_EMPTY_TREE = [_empty_group("empty")]

# Mixed tree with invisible node (file_id = None, children = None)
_INVISIBLE_TREE = [
    processed_types.HierarchyNode(
        key="invisible",
        title=None,
        title_key=None,
        children=None,
        file_id=None,
        toc_eligible=False,
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

    def test_returns_none_for_missing_id(self) -> None:
        assert hierarchy_nav.find_leaf_path(_QUEST_TREE, 999) is None

    def test_finds_direct_leaf(self) -> None:
        path = hierarchy_nav.find_leaf_path(_FLAT_COOP_TREE, 400)
        assert path is not None
        assert [n.key for n in path] == ["a10000002", "q30"]

    def test_finds_leaf_in_standalone_bucket(self) -> None:
        path = hierarchy_nav.find_leaf_path(_STANDALONE_TREE, 200)
        assert path is not None
        assert [n.key for n in path] == ["WQ", "standalone", "q10"]

    def test_returns_none_for_empty_tree(self) -> None:
        assert hierarchy_nav.find_leaf_path([], 1) is None

    def test_returns_none_for_empty_group(self) -> None:
        assert hierarchy_nav.find_leaf_path(_EMPTY_TREE, 1) is None

    def test_returns_none_for_invisible_node(self) -> None:
        assert hierarchy_nav.find_leaf_path(_INVISIBLE_TREE, 1) is None


# ── flatten_leaves ───────────────────────────────────────────────────────


class TestFlattenLeaves:
    def test_flattens_nested_tree(self) -> None:
        leaves = hierarchy_nav.flatten_leaves(_QUEST_TREE)
        assert [leaf.file_id for leaf in leaves] == [100, 101, 102, 103]

    def test_flattens_flat_coop(self) -> None:
        leaves = hierarchy_nav.flatten_leaves(_FLAT_COOP_TREE)
        assert [leaf.file_id for leaf in leaves] == [400, 401]

    def test_returns_empty_for_empty_list(self) -> None:
        assert hierarchy_nav.flatten_leaves([]) == []

    def test_returns_empty_for_empty_group(self) -> None:
        assert hierarchy_nav.flatten_leaves(_EMPTY_TREE) == []

    def test_ignores_invisible_node(self) -> None:
        assert hierarchy_nav.flatten_leaves(_INVISIBLE_TREE) == []


# ── compute_toc ──────────────────────────────────────────────────────────


class TestComputeToc:
    def test_quest_hierarchy_series_sections(self) -> None:
        """Quest tree: path = [WQ, s10152, c10156, q4].
        toc_eligible ancestors[1] = s10152 (series) → TOC with chapter sections.
        """
        path = hierarchy_nav.find_leaf_path(_QUEST_TREE, 103)
        assert path is not None
        toc = hierarchy_nav.compute_toc(path)
        assert toc is not None
        assert toc.root.key == "s10152"
        assert len(toc.sections) == 2
        # Sections are grouped by chapter
        assert (
            toc.sections[0].title is not None and toc.sections[0].title.key == "c10155"
        )
        assert [l.file_id for l in toc.sections[0].leaves] == [100, 101, 102]
        assert (
            toc.sections[1].title is not None and toc.sections[1].title.key == "c10156"
        )
        assert [l.file_id for l in toc.sections[1].leaves] == [103]

    def test_standalone_not_toc_eligible(self) -> None:
        """Standalone bucket: toc_eligible=False, so no TOC."""
        path = hierarchy_nav.find_leaf_path(_STANDALONE_TREE, 200)
        assert path is not None
        assert hierarchy_nav.compute_toc(path) is None

    def test_flat_coop_direct_children(self) -> None:
        """Flat coop: path = [a10000002, q30].
        ancestors = [a10000002] (length 1) → toc_candidate = ancestors[0]
        a10000002 is toc_eligible, children are leaves → one untitled section.
        """
        path = hierarchy_nav.find_leaf_path(_FLAT_COOP_TREE, 400)
        assert path is not None
        toc = hierarchy_nav.compute_toc(path)
        assert toc is not None
        assert toc.root.key == "a10000002"
        assert len(toc.sections) == 1
        assert toc.sections[0].title is None
        assert [l.file_id for l in toc.sections[0].leaves] == [400, 401]

    def test_direct_leaf_no_toc(self) -> None:
        """Path length 1 → no ancestors → no TOC."""
        leaf = _leaf("q1", 100, "Solo")
        path = [leaf]
        assert hierarchy_nav.compute_toc(path) is None

    def test_coop_with_chapters(self) -> None:
        """Coop tree: path = [a10000001, c50001, q20].
        ancestors = [a10000001, c50001] (length 2) → toc_candidate = ancestors[1] = c50001.
        """
        path = hierarchy_nav.find_leaf_path(_COOP_TREE, 300)
        assert path is not None
        toc = hierarchy_nav.compute_toc(path)
        assert toc is not None
        assert toc.root.key == "c50001"
        assert len(toc.sections) == 1
        assert toc.sections[0].title is None
        assert [l.file_id for l in toc.sections[0].leaves] == [300, 301]


# ── from_dict roundtrip ──────────────────────────────────────────────────


class TestFromDict:
    def test_hierarchy_node_roundtrip(self) -> None:
        original = _group(
            "parent",
            children=[
                _leaf("leaf", 42, "Answer"),
            ],
            title="Parent",
        )
        data = original.to_dict()
        restored = processed_types.HierarchyNode.from_dict(data)
        assert restored.key == "parent"
        assert restored.title == "Parent"
        assert restored.children is not None
        assert len(restored.children) == 1
        assert restored.children[0].file_id == 42

    def test_hierarchy_roundtrip(self) -> None:
        original = processed_types.Hierarchy(nodes=_QUEST_TREE)
        data = original.to_dict()
        restored = processed_types.Hierarchy.from_dict(data)
        assert len(restored.nodes) == 1
        assert restored.nodes[0].key == "WQ"

    def test_from_dict_optional_fields(self) -> None:
        """Minimal node: no title, no children, no file_id."""
        data = {"key": "empty", "toc_eligible": True}
        node = processed_types.HierarchyNode.from_dict(data)
        assert node.key == "empty"
        assert node.title is None
        assert node.title_key is None
        assert node.children is None
        assert node.file_id is None
        assert node.toc_eligible is True

    def test_from_dict_none_children(self) -> None:
        data = {"key": "leaf", "file_id": 1, "toc_eligible": False, "children": None}
        node = processed_types.HierarchyNode.from_dict(data)
        assert node.children is None
        assert node.file_id == 1
