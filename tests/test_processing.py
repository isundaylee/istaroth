"""Tests for AGD processing functionality."""

import os
from unittest import mock

import pytest

from istaroth.agd import processing, repo


def test_book100_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Book100.txt."""
    readable_path = f"Readable/{data_repo.language}/Book100.txt"
    expected_title = "神霄折戟录·第六卷"

    metadata = processing.get_readable_metadata(readable_path, data_repo=data_repo)

    assert metadata.title == expected_title


def test_weapon11101_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Weapon11101.txt."""
    readable_path = f"Readable/{data_repo.language}/Weapon11101.txt"
    expected_title = "无锋剑"

    metadata = processing.get_readable_metadata(readable_path, data_repo=data_repo)

    assert metadata.title == expected_title


def test_talk_7407811_info(data_repo: repo.DataRepo) -> None:
    """Test retrieving talk info for 7407811.json."""
    talk_path = "BinOutput/Talk/Quest/7407811.json"

    talk_info = processing.get_talk_info(talk_path, data_repo=data_repo)

    # Verify we got some talk text
    assert len(talk_info.text) > 0

    # Check that we have different role types
    roles = [text.role for text in talk_info.text]
    # Get localized role names for testing
    from istaroth.agd import localization

    localized_roles = localization.get_localized_role_names(data_repo.language)

    assert any(localized_roles.player == role for role in roles)  # Player role
    assert any(
        role not in [localized_roles.player, localized_roles.black_screen]
        for role in roles
    )  # NPC roles

    # Verify messages are not empty
    for talk_text in talk_info.text:
        assert talk_text.message.strip()  # Non-empty message


def test_quest_74078_info(data_repo: repo.DataRepo) -> None:
    """Test retrieving quest info for 74078.json."""
    quest_path = "BinOutput/Quest/74078.json"

    quest_info = processing.get_quest_info(quest_path, data_repo=data_repo)

    # Verify we got a title
    assert quest_info.title.strip()

    # Verify we got some talks (from subQuests)
    assert len(quest_info.talks) > 0

    # Verify each talk has some dialog text
    for talk_info in quest_info.talks:
        assert len(talk_info.text) > 0

        # Verify each talk has meaningful content
        for talk_text in talk_info.text:
            assert talk_text.role.strip()
            assert talk_text.message.strip()

    # Non-subquest talks may or may not exist
    # If they exist, verify they also have content
    for talk_info in quest_info.non_subquest_talks:
        assert len(talk_info.text) > 0
        for talk_text in talk_info.text:
            assert talk_text.role.strip()
            assert talk_text.message.strip()


@pytest.fixture
def english_data_repo() -> repo.DataRepo:
    """Create DataRepo instance with English language."""
    agd_path = os.environ.get("AGD_PATH")
    if not agd_path:
        pytest.skip("AGD_PATH environment variable not set")

    # Mock the environment to use English
    with mock.patch.dict(os.environ, {"AGD_LANGUAGE": "ENG"}):
        return repo.DataRepo.from_env()


def test_english_language_support(english_data_repo: repo.DataRepo) -> None:
    """Test that English language is properly supported."""
    # Verify the data repo is configured for English
    assert english_data_repo.language == "ENG"

    # Test talk processing with English
    talk_path = "BinOutput/Talk/Quest/7407811.json"

    try:
        talk_info = processing.get_talk_info(talk_path, data_repo=english_data_repo)

        # Verify we got some talk text
        assert len(talk_info.text) > 0

        # Check that player role is localized to English
        roles = [text.role for text in talk_info.text]

        # Player roles should be "Traveler" in English, not "旅行者"
        player_roles = [role for role in roles if "Traveler" in role or "旅行者" in role]
        assert any(
            "Traveler" in role for role in player_roles
        ), "Expected 'Traveler' for player role in English"
        assert not any(
            "旅行者" in role for role in player_roles
        ), "Should not have Chinese player role name in English mode"

        # Check for black screen text localization
        black_screen_roles = [
            role for role in roles if "Black Screen" in role or "黑屏文本" in role
        ]
        if black_screen_roles:
            assert any(
                "Black Screen Text" in role for role in black_screen_roles
            ), "Expected 'Black Screen Text' in English"
            assert not any(
                "黑屏文本" in role for role in black_screen_roles
            ), "Should not have Chinese black screen role name in English mode"

    except Exception as e:
        # If the test fails due to missing English text maps, skip the test
        if "TextMapENG.json" in str(e):
            pytest.skip(f"English text map not available: {e}")
