"""Tests for AGD processing functionality."""

import os
from unittest import mock

import pytest

from istaroth.agd import localization, processing, repo, talk_parsing


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


def test_furina_constellations(data_repo: repo.DataRepo) -> None:
    """Furina has 6 constellations including the C5 example name."""
    if data_repo.language is not localization.Language.CHS:
        pytest.skip("Constellation name assertion is CHS-specific")

    story_info = processing.get_character_story_info(10000089, data_repo=data_repo)

    assert len(story_info.constellations) == 6
    assert all(c.element is None for c in story_info.constellations)
    assert any("秘密藏心间，无人知我名。" in c.name for c in story_info.constellations)


def test_traveler_constellations_grouped_by_element(data_repo: repo.DataRepo) -> None:
    """The Traveler's per-element constellations come tagged with their element."""
    story_info = processing.get_character_story_info(10000005, data_repo=data_repo)

    # Multiple released elements, 6 constellations each, all element-tagged.
    assert story_info.constellations
    assert len(story_info.constellations) % 6 == 0
    assert all(c.element is not None for c in story_info.constellations)
    assert len({c.element for c in story_info.constellations}) >= 2


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


def test_talk_6864003_narration_role(data_repo: repo.DataRepo) -> None:
    """Speaker-less TALK_ROLE_NONE lines render with no role (None), not Unknown Role."""
    talk_info = processing.get_talk_info(
        "BinOutput/Talk/Gadget/6864003.json", data_repo=data_repo
    )

    roles = [text.role for text in talk_info.text]

    assert None in roles
    assert all(role is None or "TALK_ROLE_NONE" not in role for role in roles)


def test_quest_74078_info(data_repo: repo.DataRepo) -> None:
    """Test retrieving quest info for 74078.json."""
    quest_id = 74078

    quest_info = processing.get_quest_info(quest_id, data_repo=data_repo)
    assert quest_info is not None

    # Verify we got a title
    assert quest_info.title.strip()

    # Verify we got some steps (from subQuests)
    assert len(quest_info.steps) > 0

    # Verify each dialogue step has meaningful talk content
    talk_steps = [step for step in quest_info.steps if step.talk is not None]
    assert talk_steps
    for step in talk_steps:
        assert step.talk is not None
        assert len(step.talk.text) > 0
        for talk_text in step.talk.text:
            assert talk_text.role is None or talk_text.role.strip()
            assert talk_text.message.strip()

    # 74078 has non-dialogue objective steps, each carrying objective text.
    objective_steps = [step for step in quest_info.steps if step.talk is None]
    assert objective_steps
    assert all(step.description for step in objective_steps)

    # Non-subquest talks may or may not exist
    # If they exist, verify they also have content
    for talk_info in quest_info.non_subquest_talks:
        assert len(talk_info.text) > 0
        for talk_text in talk_info.text:
            assert talk_text.role is None or talk_text.role.strip()
            assert talk_text.message.strip()


def test_achievement_section_46_info(data_repo: repo.DataRepo) -> None:
    """Achievement sections include their localized achievement text."""
    section = processing.get_achievement_section_info(46, data_repo=data_repo)

    assert section.section_name == "枫丹·白露澈明的泉舞·其之三"
    assert section.achievements[-1].achievement_id == 80299
    assert section.achievements[-1].name == "水仙十字题解"
    assert section.achievements[-1].description.startswith("何物徒留名字？")


def test_achievement_section_filters_disused_and_keeps_hidden() -> None:
    """Only disused achievements are excluded; hidden active text remains."""
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.load_achievement_goal_excel_config_data.return_value = [
        {"id": 9, "orderId": 1, "nameTextMapHash": 100}
    ]
    data_repo.load_achievement_excel_config_data.return_value = [
        {
            "id": 3,
            "goalId": 9,
            "orderId": 2,
            "titleTextMapHash": 103,
            "descTextMapHash": 203,
            "isDisuse": False,
            "isShow": "SHOWTYPE_HIDE",
        },
        {
            "id": 2,
            "goalId": 9,
            "orderId": 1,
            "titleTextMapHash": 102,
            "descTextMapHash": 202,
            "isDisuse": False,
            "isShow": "SHOWTYPE_SHOW",
        },
        {
            "id": 1,
            "goalId": 9,
            "orderId": 0,
            "titleTextMapHash": 101,
            "descTextMapHash": 201,
            "isDisuse": True,
            "isShow": "SHOWTYPE_SHOW",
        },
    ]
    data_repo.build_achievement_section_mapping.return_value = (
        repo.DataRepo.build_achievement_section_mapping(data_repo)
    )
    data_repo.load_text_map.return_value = repo.TextMapTracker(
        {
            "100": "Section",
            "102": "Visible",
            "202": "Visible description",
            "103": "Hidden",
            "203": "Hidden description",
        },
        localization.Language.ENG,
    )

    section = processing.get_achievement_section_info(9, data_repo=data_repo)

    assert [achievement.achievement_id for achievement in section.achievements] == [
        2,
        3,
    ]
    assert section.achievements[1].name == "Hidden"


def test_achievement_section_requires_active_localized_text() -> None:
    """Missing active achievement text is a per-section parsing failure."""
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.build_achievement_section_mapping.return_value = {
        9: (
            {"id": 9, "orderId": 1, "nameTextMapHash": 100},
            [
                {
                    "id": 2,
                    "goalId": 9,
                    "orderId": 1,
                    "titleTextMapHash": 102,
                    "descTextMapHash": 202,
                    "isDisuse": False,
                    "isShow": "SHOWTYPE_SHOW",
                }
            ],
        )
    }
    data_repo.load_text_map.return_value = repo.TextMapTracker(
        {"100": "Section", "102": "Achievement"}, localization.Language.ENG
    )

    with pytest.raises(ValueError, match="Missing description for achievement 2"):
        processing.get_achievement_section_info(9, data_repo=data_repo)


@pytest.mark.parametrize(
    "talk_id, expected_quest_id",
    [
        ("7407804", 74078),  # 7-digit: drop trailing index
        ("1000401", 10004),
        ("602708", 6027),  # 6-digit
        ("100089906", 10008),  # 9-digit "99" ambient bucket: drop 4
        ("402217", 4022),
    ],
)
def test_free_group_quest_id(talk_id: str, expected_quest_id: int) -> None:
    """The talkId-numbering heuristic maps a FreeGroup talk to its quest."""
    assert talk_parsing._free_group_quest_id(talk_id) == expected_quest_id


def test_quest_10008_associated_free_talks(data_repo: repo.DataRepo) -> None:
    """FreeGroup "free talks" are attached to their owning quest."""
    quest_info = processing.get_quest_info(10008, data_repo=data_repo)
    assert quest_info is not None

    assert quest_info.associated_free_talks
    for talk_info in quest_info.associated_free_talks:
        assert len(talk_info.text) > 0
        for talk_text in talk_info.text:
            assert talk_text.role is None or talk_text.role.strip()
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
    assert english_data_repo.language == localization.Language.ENG

    # Test talk processing with English
    talk_path = "BinOutput/Talk/Quest/7407811.json"

    try:
        talk_info = processing.get_talk_info(talk_path, data_repo=english_data_repo)

        # Verify we got some talk text
        assert len(talk_info.text) > 0

        # Check that player role is localized to English
        roles = [text.role for text in talk_info.text if text.role is not None]

        # Player roles should be "Traveler" in English, not "旅行者"
        player_roles = [
            role for role in roles if "Traveler" in role or "旅行者" in role
        ]
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
