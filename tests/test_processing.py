"""Tests for AGD processing functionality."""

from istorath.agd import processing, repo


def test_book100_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Book100.txt."""
    readable_path = "Readable/CHS/Book100.txt"
    expected_title = "神霄折戟录·第六卷"

    metadata = processing.get_readable_metadata(readable_path, data_repo=data_repo)

    assert metadata.title == expected_title


def test_weapon11101_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Weapon11101.txt."""
    readable_path = "Readable/CHS/Weapon11101.txt"
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
    assert any("旅行者" == role for role in roles)  # Player role
    assert any(role not in ["旅行者", "黑屏文本"] for role in roles)  # NPC roles

    # Verify messages are not empty
    for talk_text in talk_info.text:
        assert talk_text.message.strip()  # Non-empty message


def test_quest_74078_info(data_repo: repo.DataRepo) -> None:
    """Test retrieving quest info for 74078.json."""
    quest_path = "BinOutput/Quest/74078.json"

    quest_info = processing.get_quest_info(quest_path, data_repo=data_repo)

    # Verify we got a title
    assert quest_info.title.strip()

    # Verify we got some talks
    assert len(quest_info.talks) > 0

    # Verify each talk has some dialog text
    for talk_info in quest_info.talks:
        assert len(talk_info.text) > 0

        # Verify each talk has meaningful content
        for talk_text in talk_info.text:
            assert talk_text.role.strip()
            assert talk_text.message.strip()
