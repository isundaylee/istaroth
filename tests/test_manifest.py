"""Tests for manifest utilities."""

import pathlib

import pytest

from istaroth.text import manifest, types


def _item(id: int, filename: str) -> types.TextMetadata:
    return types.TextMetadata(
        category=types.TextCategory.AGD_TALK_GROUP,
        title=f"Talk Group {id}",
        id=id,
        relative_path=f"{types.TextCategory.AGD_TALK_GROUP.value}/{filename}",
    )


def test_write_manifest_rejects_duplicate_category_id(
    tmp_path: pathlib.Path,
) -> None:
    with pytest.raises(ValueError, match=r"Duplicate manifest \(category, id\)"):
        manifest.write_manifest(
            tmp_path,
            [_item(2001, "2001_ActivityGroup.txt"), _item(2001, "2001_NpcGroup.txt")],
            name="agd",
        )
    assert not (tmp_path / "manifest").exists()

    path = manifest.write_manifest(
        tmp_path,
        [_item(2001, "2001_ActivityGroup.txt"), _item(2002, "2002_NpcGroup.txt")],
        name="agd",
    )
    assert manifest.load_manifest_dir(tmp_path) == (
        _item(2001, "2001_ActivityGroup.txt"),
        _item(2002, "2002_NpcGroup.txt"),
    )
    assert path.is_file()
