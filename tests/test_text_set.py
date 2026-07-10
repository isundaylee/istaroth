"""Tests for TextSet library hierarchy assembly."""

import pathlib

from istaroth import json_utils
from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.text import manifest, types


def _item(
    category: types.TextCategory,
    id: int,
    title: str,
    *,
    min_version: str | None = "1.4",
    max_version: str | None = "1.4",
) -> types.TextMetadata:
    return types.TextMetadata(
        category=category,
        title=title,
        id=id,
        relative_path=f"{category.value}/{id}_{title}.txt",
        min_version=min_version,
        max_version=max_version,
    )


def test_library_hierarchies(tmp_path: pathlib.Path) -> None:
    manifest.write_manifest(
        tmp_path,
        [
            _item(types.TextCategory.AGD_READABLE, 20, "Scroll", max_version="4.2"),
            _item(types.TextCategory.AGD_READABLE, 10, "Tablet", max_version="4.10"),
            _item(types.TextCategory.AGD_READABLE, 30, "Codex", max_version="4.2"),
            _item(types.TextCategory.AGD_ACHIEVEMENT, 1, "Trophy"),
            _item(types.TextCategory.AGD_QUEST, 100, "Old Act", max_version="1.4"),
            _item(types.TextCategory.AGD_QUEST, 101, "New Act", max_version="5.0"),
            _item(types.TextCategory.AGD_QUEST, 102, "Mid Act", max_version="3.1"),
            _item(
                types.TextCategory.TPS_SHISHU,
                2,
                "Late",
                min_version=None,
                max_version=None,
            ),
            _item(
                types.TextCategory.TPS_SHISHU,
                1,
                "Early",
                min_version=None,
                max_version=None,
            ),
        ],
        name="agd",
    )

    def _leaf(id: int, title: str, version: str | None = None) -> dict:
        node = {
            "key": f"q{id}",
            "title": title,
            "children": None,
            "file_id": id,
            "toc_eligible": True,
        }
        # Input prebaked nodes carry no version; expected outputs are annotated.
        return node | {"max_version": version} if version is not None else node

    def _chapter(key: str, *leaves: dict, version: str | None = None) -> dict:
        node = {
            "key": key,
            "title": key,
            "children": list(leaves),
            "file_id": None,
            "toc_eligible": False,
        }
        return node | {"max_version": version} if version is not None else node

    quest_tree = {
        "nodes": [
            _chapter("chapter1", _leaf(100, "Old Act"), _leaf(101, "New Act")),
            _chapter("chapter2", _leaf(102, "Mid Act")),
        ]
    }
    hierarchy_path = tmp_path / "metadata" / "agd" / "hierarchy.json"
    hierarchy_path.parent.mkdir(parents=True)
    hierarchy_path.write_bytes(json_utils.dumps({"agd_quest": quest_tree}))

    text_set_obj = text_set.TextSet(
        text_path=tmp_path, language=localization.Language.CHS
    )
    hierarchies = text_set_obj.get_library_hierarchies()

    # Curated display order (unlisted agd_achievement trails despite sorting
    # first alphabetically); flat category synthesized as depth-1 leaves sorted
    # newest max_version first (compared numerically, so 4.10 > 4.2), ties
    # broken by id.
    assert list(hierarchies) == [
        "agd_quest",
        "agd_readable",
        "agd_achievement",
        "tps_shishu",
    ]
    # Pre-baked tree keeps its structure but sorts every sibling level by the
    # newest subtree max_version: chapter1 leads via its 5.0 leaf (despite also
    # holding the oldest one), and its leaves reorder newest-first. Every node
    # is annotated with its subtree max_version.
    assert hierarchies["agd_quest"] == {
        "nodes": [
            _chapter(
                "chapter1",
                _leaf(101, "New Act", version="5.0"),
                _leaf(100, "Old Act", version="1.4"),
                version="5.0",
            ),
            _chapter("chapter2", _leaf(102, "Mid Act", version="3.1"), version="3.1"),
        ]
    }
    assert hierarchies["agd_readable"] == {
        "nodes": [
            {
                "key": "q10",
                "title": "Tablet",
                "children": None,
                "file_id": 10,
                "toc_eligible": False,
                "max_version": "4.10",
            },
            {
                "key": "q20",
                "title": "Scroll",
                "children": None,
                "file_id": 20,
                "toc_eligible": False,
                "max_version": "4.2",
            },
            {
                "key": "q30",
                "title": "Codex",
                "children": None,
                "file_id": 30,
                "toc_eligible": False,
                "max_version": "4.2",
            },
        ]
    }
    # Versionless (non-AGD) items fall back to id order and carry no version.
    assert [n["file_id"] for n in hierarchies["tps_shishu"]["nodes"]] == [1, 2]
    assert [n["max_version"] for n in hierarchies["tps_shishu"]["nodes"]] == [
        None,
        None,
    ]
    assert text_set_obj.latest_version == "5.0"
    assert text_set_obj.library_hierarchies_content_hash
