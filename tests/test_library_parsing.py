"""Test library filename parsing functionality."""

import pytest

from istaroth.services.backend.routers import library


@pytest.mark.parametrize(
    "filename,category,expected_category,expected_name,expected_id",
    [
        # With ID
        (
            "artifact_set_乐团的晨光_15003.txt",
            "artifact_sets",
            "artifact_sets",
            "乐团的晨光",
            15003,
        ),
        (
            "talk_group_NpcGroup_9306.txt",
            "talk_groups",
            "talk_groups",
            "NpcGroup",
            9306,
        ),
        (
            "talk_gadget_哈哈我的演技还不错吧是不是很有魄力_6801000.txt",
            "talks",
            "talks",
            "gadget_哈哈我的演技还不错吧是不是很有魄力",
            6801000,
        ),
        ("quest_some_quest_name_12345.txt", "quest", "quest", "some_quest_name", 12345),
        (
            "character_story_CharacterName_10001.txt",
            "character_stories",
            "character_stories",
            "CharacterName",
            10001,
        ),
        (
            "material_type_MaterialName_20001.txt",
            "material_types",
            "material_types",
            "MaterialName",
            20001,
        ),
        (
            "subtitle_SubtitleName_30001.txt",
            "subtitles",
            "subtitles",
            "SubtitleName",
            30001,
        ),
        # Empty name with ID
        ("readable__200571.txt", "readable", "readable", "", 200571),
        # Without ID
        ("readable_some_text.txt", "readable", "readable", "some_text", None),
        ("voiceline_卡维.txt", "voicelines", "voicelines", "卡维", None),
        # Non-integer after underscore (treated as part of name)
        ("readable_some_text_abc.txt", "readable", "readable", "some_text_abc", None),
    ],
)
def test_parse_filename_valid(
    filename: str,
    category: str,
    expected_category: str,
    expected_name: str,
    expected_id: int | None,
) -> None:
    """Test parsing valid filenames."""
    result = library._parse_filename(filename, category)
    assert result.category == expected_category
    assert result.name == expected_name
    assert result.id == expected_id
    assert result.filename == filename


@pytest.mark.parametrize(
    "filename,category,expected_error",
    [
        ("artifact_set_name_123", "artifact_sets", "Invalid filename format"),
        (
            "wrong_prefix_name_123.txt",
            "artifact_sets",
            "Filename must start with category prefix",
        ),
        ("unknown_category_some_name_456.txt", "unknown_category", "Unknown category"),
    ],
)
def test_parse_filename_invalid(
    filename: str, category: str, expected_error: str
) -> None:
    """Test parsing invalid filenames raises appropriate errors."""
    with pytest.raises(ValueError, match=expected_error):
        library._parse_filename(filename, category)
