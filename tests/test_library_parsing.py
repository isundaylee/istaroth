"""Test library filename parsing functionality."""

import pytest

from istaroth.services.backend.utils import parse_filename


@pytest.mark.parametrize(
    "filename,expected_category,expected_name,expected_id",
    [
        # With ID
        (
            "artifact_set_乐团的晨光_15003.txt",
            "artifact_sets",
            "乐团的晨光",
            15003,
        ),
        (
            "talk_group_NpcGroup_9306.txt",
            "talk_groups",
            "NpcGroup",
            9306,
        ),
        (
            "talk_gadget_哈哈我的演技还不错吧是不是很有魄力_6801000.txt",
            "talks",
            "gadget_哈哈我的演技还不错吧是不是很有魄力",
            6801000,
        ),
        ("quest_some_quest_name_12345.txt", "quest", "some_quest_name", 12345),
        (
            "character_story_CharacterName_10001.txt",
            "character_stories",
            "CharacterName",
            10001,
        ),
        (
            "material_type_MaterialName_20001.txt",
            "material_types",
            "MaterialName",
            20001,
        ),
        (
            "subtitle_SubtitleName_30001.txt",
            "subtitles",
            "SubtitleName",
            30001,
        ),
        # Empty name with ID
        ("readable__200571.txt", "readable", "", 200571),
        # Without ID
        ("readable_some_text.txt", "readable", "some_text", None),
        ("voiceline_卡维.txt", "voicelines", "卡维", None),
        # Non-integer after underscore (treated as part of name)
        ("readable_some_text_abc.txt", "readable", "some_text_abc", None),
    ],
)
def test_parse_filename_valid(
    filename: str,
    expected_category: str,
    expected_name: str,
    expected_id: int | None,
) -> None:
    """Test parsing valid filenames."""
    result = parse_filename(filename)
    assert result.category == expected_category
    assert result.name == expected_name
    assert result.id == expected_id
    assert result.filename == filename


@pytest.mark.parametrize(
    "filename,expected_error",
    [
        ("artifact_set_name_123", "Invalid filename format"),
        (
            "wrong_prefix_name_123.txt",
            "Unknown category prefix",
        ),
        ("unknown_category_some_name_456.txt", "Unknown category prefix"),
    ],
)
def test_parse_filename_invalid(filename: str, expected_error: str) -> None:
    """Test parsing invalid filenames raises appropriate errors."""
    with pytest.raises(ValueError, match=expected_error):
        parse_filename(filename)
