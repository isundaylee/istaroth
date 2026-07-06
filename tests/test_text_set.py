"""Tests for TextSet library hierarchy assembly."""

import pathlib

import orjson

from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.text import manifest, types


def _item(category: types.TextCategory, id: int, title: str) -> types.TextMetadata:
    return types.TextMetadata(
        category=category,
        title=title,
        id=id,
        relative_path=f"{category.value}/{id}_{title}.txt",
        min_version="1.4",
        max_version="1.4",
    )


def test_library_hierarchies(tmp_path: pathlib.Path) -> None:
    manifest.write_manifest(
        tmp_path,
        [
            _item(types.TextCategory.AGD_READABLE, 20, "Scroll"),
            _item(types.TextCategory.AGD_READABLE, 10, "Tablet"),
            _item(types.TextCategory.AGD_ACHIEVEMENT, 1, "Trophy"),
            _item(types.TextCategory.AGD_QUEST, 100, "Placed Quest"),
        ],
        name="agd",
    )
    quest_tree = {
        "nodes": [
            {
                "key": "chapter1",
                "title": "Chapter 1",
                "children": [
                    {
                        "key": "q100",
                        "title": "Placed Quest",
                        "children": None,
                        "file_id": 100,
                        "toc_eligible": True,
                    }
                ],
                "file_id": None,
                "toc_eligible": False,
            }
        ]
    }
    hierarchy_path = tmp_path / "metadata" / "agd" / "hierarchy.json"
    hierarchy_path.parent.mkdir(parents=True)
    hierarchy_path.write_bytes(orjson.dumps({"agd_quest": quest_tree}))

    text_set_obj = text_set.TextSet(
        text_path=tmp_path, language=localization.Language.CHS
    )
    hierarchies = text_set_obj.get_library_hierarchies()

    # Curated display order (unlisted agd_achievement trails despite sorting
    # first alphabetically); pre-baked tree used as-is; flat category
    # synthesized as id-sorted depth-1 leaves.
    assert list(hierarchies) == ["agd_quest", "agd_readable", "agd_achievement"]
    assert hierarchies["agd_quest"] == quest_tree
    assert hierarchies["agd_readable"] == {
        "nodes": [
            {
                "key": "q10",
                "title": "Tablet",
                "children": None,
                "file_id": 10,
                "toc_eligible": False,
            },
            {
                "key": "q20",
                "title": "Scroll",
                "children": None,
                "file_id": 20,
                "toc_eligible": False,
            },
        ]
    }
    assert text_set_obj.library_hierarchies_content_hash
