"""Tests for AGD processing functionality."""

import os
from unittest import mock

import pytest

from istaroth.agd import (
    agd_types,
    issues,
    localization,
    renderable_types,
    repo,
    talk_parsing,
)
from istaroth.agd.renderables import (
    _talk,
    achievement,
    book,
    character,
    creature,
    quest,
    readable,
    subtitle,
)


def test_book100_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Book100.txt."""
    expected_title = "神霄折戟录·第六卷"

    metadata = readable.get_readable_metadata("Book100.txt", data_repo=data_repo)

    assert metadata.title == expected_title


def test_weapon11101_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Weapon11101.txt."""
    expected_title = "无锋剑"

    metadata = readable.get_readable_metadata("Weapon11101.txt", data_repo=data_repo)

    assert metadata.title == expected_title


def test_furina_constellations(data_repo: repo.DataRepo) -> None:
    """Furina has 6 constellations including the C5 example name."""
    if data_repo.language is not localization.Language.CHS:
        pytest.skip("Constellation name assertion is CHS-specific")

    story_info = character.get_character_story_info(10000089, data_repo=data_repo)

    assert len(story_info.constellations) == 6
    assert all(c.element is None for c in story_info.constellations)
    assert any("秘密藏心间，无人知我名。" in c.name for c in story_info.constellations)


def test_traveler_constellations_grouped_by_element(data_repo: repo.DataRepo) -> None:
    """The Traveler's per-element constellations come tagged with their element."""
    story_info = character.get_character_story_info(10000005, data_repo=data_repo)

    # Multiple released elements, 6 constellations each, all element-tagged.
    assert story_info.constellations
    assert len(story_info.constellations) % 6 == 0
    assert all(c.element is not None for c in story_info.constellations)
    assert len({c.element for c in story_info.constellations}) >= 2


def test_talk_7407811_info(data_repo: repo.DataRepo) -> None:
    """Test retrieving talk info for 7407811.json."""
    talk_path = "BinOutput/Talk/Quest/7407811.json"

    talk_info = _talk.get_talk_info(talk_path, data_repo=data_repo)

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
    talk_info = _talk.get_talk_info(
        "BinOutput/Talk/Gadget/6864003.json", data_repo=data_repo
    )

    roles = [text.role for text in talk_info.text]

    assert None in roles
    assert all(role is None or "TALK_ROLE_NONE" not in role for role in roles)


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        # Cutscene binding via videoName / subtitleId.
        (
            "Cs_Inazuma_LQ1204205_IntoTheVoid_Boy_CHS",
            "熠熠生辉之樱 (Cs_Inazuma_LQ1204205_IntoTheVoid_Boy)",
        ),
        # Shared no-variant subtitle, matched through the localization path.
        ("Cs_MDAQ019_DragonInCity_CHS", "龙灾 (Cs_MDAQ019_DragonInCity)"),
        # No id token in the stem: only resolvable through its cutscene binding.
        ("Ambor_Readings_CHS", "风之翼随风而起 (Ambor_Readings)"),
        # No cutscene file in AGD: quest id token decoded from the filename.
        ("Cs_NK_AQ603605_Boss_Boy_CHS", "虚空劫灰往世书 (Cs_NK_AQ603605_Boss_Boy)"),
        # System video with no owning quest: bare stem.
        ("Title_CHS", "Title"),
    ],
)
def test_subtitle_title(data_repo: repo.DataRepo, stem: str, expected: str) -> None:
    """Subtitle titles resolve to the owning quest's name (issue #74)."""
    if data_repo.language is not localization.Language.CHS:
        pytest.skip("Title assertions are CHS-specific")

    assert (
        subtitle.build_subtitle_title(f"Subtitle/CHS/{stem}.srt", data_repo=data_repo)
        == expected
    )


def test_subtitle_title_resolution_coverage(data_repo: repo.DataRepo) -> None:
    """Nearly all subtitles resolve a quest title; guards against a future AGD
    build silently breaking the cutscene scan (e.g. newly obfuscated keys)."""
    unresolved = []
    for name in data_repo.list_subtitle_names():
        if not name.endswith(".srt"):
            continue
        path = f"Subtitle/{data_repo.language_short}/{name}"
        title = subtitle.build_subtitle_title(path, data_repo=data_repo)
        if " (" not in title:
            unresolved.append(name)

    assert len(unresolved) <= 12, unresolved


def test_talk_role_name_hash_ignores_fallback_text() -> None:
    """Fallback TextMap recovers messages, not stale role-name hashes."""
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.language = localization.Language.ENG
    data_repo.load_talk_data.return_value = {
        "dialogList": [
            {
                "id": 1,
                "talkContentTextMapHash": 100,
                "talkRoleNameTextMapHash": 200,
                "talkRole": {"type": "TALK_ROLE_PLAYER"},
            }
        ]
    }
    data_repo.build_text_map_tracker.return_value = repo.TextMapTracker(
        {"100": "Hello"},
        localization.Language.ENG,
        {"200": "Stale role"},
        pronoun_hashes={},
    )
    data_repo.build_npc_id_to_name_mapping.return_value = {}
    data_repo.build_dialog_id_to_role_name_hash_mapping.return_value = {}

    talk_info = _talk.get_talk_info("BinOutput/Talk/Quest/1.json", data_repo=data_repo)

    assert talk_info.text[0].role == "Traveler"
    assert talk_info.text[0].message == "Hello"


def test_talk_untranslated_chs_test_placeholder_is_skipped_not_missing() -> None:
    """A hash untranslated in ENG but a CHS ``(test)`` placeholder is dropped, not MISSING_TEXT."""
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.language = localization.Language.ENG
    data_repo.load_talk_data.return_value = {
        "dialogList": [
            {
                "id": 1,
                "talkContentTextMapHash": 100,
                "talkRole": {"type": "TALK_ROLE_NONE"},
            }
        ]
    }
    data_repo.build_text_map_tracker.return_value = repo.TextMapTracker(
        {}, localization.Language.ENG, pronoun_hashes={}
    )
    data_repo.build_source_text_map_tracker.return_value = repo.TextMapTracker(
        {"100": "(test)台词文本"}, localization.Language.CHS, pronoun_hashes={}
    )
    data_repo.build_npc_id_to_name_mapping.return_value = {}
    data_repo.build_dialog_id_to_role_name_hash_mapping.return_value = {}

    tracker = issues.IssueTracker(item_type="Talks", item_key="1")
    with tracker.apply():
        talk_info = _talk.get_talk_info(
            "BinOutput/Talk/Quest/1.json", data_repo=data_repo
        )

    assert talk_info.text[0].skip
    assert tracker.issues == []


def test_quest_74078_info(data_repo: repo.DataRepo) -> None:
    """Test retrieving quest info for 74078.json."""
    quest_id = 74078

    quest_info = quest.get_quest_info(quest_id, data_repo=data_repo)
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


def test_fallback_text_map_does_not_break_talk_collision_resolution(
    data_repo: repo.DataRepo,
) -> None:
    """Fallback hash collisions dedupe by resolved text."""
    for quest_id in [11020, 75079]:
        quest_info = quest.get_quest_info(quest_id, data_repo=data_repo)

        assert quest_info is not None
        assert quest_info.steps


def test_achievement_section_46_info(data_repo: repo.DataRepo) -> None:
    """Achievement sections include their localized achievement text."""
    section = achievement.get_achievement_section_info(46, data_repo=data_repo)

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
    data_repo.build_text_map_tracker.return_value = repo.TextMapTracker(
        {
            "100": "Section",
            "102": "Visible",
            "202": "Visible description",
            "103": "Hidden",
            "203": "Hidden description",
        },
        localization.Language.ENG,
        pronoun_hashes={},
    )

    section = achievement.get_achievement_section_info(9, data_repo=data_repo)

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
    data_repo.build_text_map_tracker.return_value = repo.TextMapTracker(
        {"100": "Section", "102": "Achievement"},
        localization.Language.ENG,
        pronoun_hashes={},
    )

    with pytest.raises(ValueError, match="Missing description for achievement 2"):
        achievement.get_achievement_section_info(9, data_repo=data_repo)


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
    quest_info = quest.get_quest_info(10008, data_repo=data_repo)
    assert quest_info is not None

    assert quest_info.associated_free_talks
    for talk_info in quest_info.associated_free_talks:
        assert len(talk_info.text) > 0
        for talk_text in talk_info.text:
            assert talk_text.role is None or talk_text.role.strip()
            assert talk_text.message.strip()


def _book_material(
    material_id: int, suit_id: int
) -> agd_types.MaterialExcelConfigDataItem:
    """A minimal book material entry carrying just the fields grouping reads."""
    return {
        "id": material_id,
        "setID": suit_id,
        "nameTextMapHash": 0,
        "descTextMapHash": 0,
        "materialType": "MATERIAL_QUEST",
    }


def _book_series_mock_repo() -> mock.Mock:
    """Mock DataRepo wired with the configs build_book_series_mapping reads."""
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.load_book_suit_excel_config_data.return_value = {
        7: {"id": 7, "suitNameTextMapHash": 700},
        8: {"id": 8, "suitNameTextMapHash": 800},
    }
    data_repo.build_material_tracker.return_value = repo.MaterialTracker(
        [
            _book_material(101, 7),
            _book_material(102, 7),
            _book_material(103, 8),  # single-volume suit -> not a series
            _book_material(104, 0),  # codex book with no suit -> standalone
            _book_material(105, 7),  # disused volume -> excluded
        ]
    )
    data_repo.load_document_excel_config_data.return_value = {
        material_id: {
            "id": material_id,
            "titleTextMapHash": material_id,
            "questIDList": [material_id],
            "questContentLocalizedId": [],
        }
        for material_id in (101, 102, 103, 104, 105)
    }
    data_repo.build_localization_id_to_readable_filename_mapping.return_value = {
        material_id: f"Book{material_id}_EN.txt"
        for material_id in (101, 102, 103, 104, 105)
    }
    data_repo.load_books_codex_excel_config_data.return_value = [
        {"id": 1, "materialId": 102, "sortOrder": 20, "isDisuse": False},
        {"id": 2, "materialId": 101, "sortOrder": 10, "isDisuse": False},
        {"id": 3, "materialId": 103, "sortOrder": 30, "isDisuse": False},
        {"id": 4, "materialId": 104, "sortOrder": 40, "isDisuse": False},
        {"id": 5, "materialId": 105, "sortOrder": 5, "isDisuse": True},
    ]
    return data_repo


def test_build_book_series_mapping_groups_and_orders() -> None:
    """Only multi-volume suits group, ordered by sortOrder; disused/suitless skip."""
    data_repo = _book_series_mock_repo()

    mapping = repo.DataRepo.build_book_series_mapping(data_repo)

    # Suit 7 keeps its two active volumes ordered by sortOrder (101 before 102);
    # the disused volume 105 is dropped. Suit 8 is single-volume and suit-less
    # book 104 are both excluded from series grouping.
    assert mapping == {7: ["Book101_EN.txt", "Book102_EN.txt"]}


def test_get_book_series_info_assembles_volumes() -> None:
    """A series resolves its name and volumes (titles + bodies) in reading order."""
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.language = localization.Language.ENG
    data_repo.language_short = "EN"
    data_repo.build_book_series_mapping.return_value = {
        7: ["Book101_EN.txt", "Book102_EN.txt"]
    }
    data_repo.load_book_suit_excel_config_data.return_value = {
        7: {"id": 7, "suitNameTextMapHash": 700}
    }
    data_repo.build_text_map_tracker.return_value = repo.TextMapTracker(
        {"700": "My Series", "101": "Volume One", "102": "Volume Two"},
        localization.Language.ENG,
        pronoun_hashes={},
    )
    data_repo.build_readable_stem_to_localization_id_mapping.return_value = {
        "Book101_EN": 101,
        "Book102_EN": 102,
    }
    data_repo.build_localization_id_to_title_hash_mapping.return_value = {
        101: 101,
        102: 102,
    }
    readables = mock.Mock()
    readables.get_content.side_effect = lambda filename: {
        "Book101_EN.txt": "First body.",
        "Book102_EN.txt": "Second body.",
    }[filename]
    data_repo.build_readables_tracker.return_value = readables

    series = book.get_book_series_info(7, data_repo=data_repo)

    assert series is not None
    assert series.suit_id == 7
    assert series.series_name == "My Series"
    assert [(volume.title, volume.content) for volume in series.volumes] == [
        ("Volume One", "First body."),
        ("Volume Two", "Second body."),
    ]


def test_get_book_series_info_filters_placeholder_volumes() -> None:
    """Placeholder/test volumes are dropped, mirroring standalone book filtering."""
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.language = localization.Language.ENG
    data_repo.language_short = "EN"
    data_repo.build_book_series_mapping.return_value = {
        7: ["Book101_EN.txt", "Book102_EN.txt"]
    }
    data_repo.load_book_suit_excel_config_data.return_value = {
        7: {"id": 7, "suitNameTextMapHash": 700}
    }
    data_repo.build_text_map_tracker.return_value = repo.TextMapTracker(
        {"700": "My Series", "102": "Volume Two"},
        localization.Language.ENG,
        pronoun_hashes={},
    )
    data_repo.build_readable_stem_to_localization_id_mapping.return_value = {
        "Book102_EN": 102
    }
    data_repo.build_localization_id_to_title_hash_mapping.return_value = {102: 102}
    readables = mock.Mock()
    readables.get_content.side_effect = lambda filename: {
        "Book101_EN.txt": "test",  # placeholder content -> filtered
        "Book102_EN.txt": "Second body.",
    }[filename]
    data_repo.build_readables_tracker.return_value = readables

    series = book.get_book_series_info(7, data_repo=data_repo)

    assert series is not None
    assert [volume.title for volume in series.volumes] == ["Volume Two"]


def test_drunkards_tale_series_grouped(data_repo: repo.DataRepo) -> None:
    """The four-volume 'A Drunkard's Tale' (suit 1019) groups its volumes in order."""
    series = book.get_book_series_info(1019, data_repo=data_repo)

    assert series is not None
    assert len(series.volumes) == 4
    if data_repo.language is localization.Language.CHS:
        assert series.series_name == "醉客轶事"
        assert [volume.title for volume in series.volumes] == [
            "醉客轶事·一",
            "醉客轶事·二",
            "醉客轶事·三",
            "醉客轶事·四",
        ]


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
        talk_info = _talk.get_talk_info(talk_path, data_repo=english_data_repo)

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


def test_creature_24068801_info(data_repo: repo.DataRepo) -> None:
    """The Fontaine Assault Specialist Mek resolves its names and description."""
    info = creature._get_creature_info(24068801, data_repo=data_repo)

    assert info.codex_id == 24068801
    assert info.name == "攻坚特化型机关"
    assert info.special_name == "谢尔比乌斯式机关"
    assert info.title == "攻坚特化型"
    assert info.description.startswith("与「侦察记录型」一样")


def test_creature_wildlife_info_has_no_monster_names(data_repo: repo.DataRepo) -> None:
    """Wildlife entries carry only a name; no special name or title."""
    info = creature._get_creature_info(28020101, data_repo=data_repo)

    assert info.special_name is None
    assert info.title is None
    assert info.name == "雪狐"


def test_creature_group_automatron_info(data_repo: repo.DataRepo) -> None:
    """The Automatron group is ordered by sortOrder and includes the mek."""
    group = creature.get_creature_group_info(
        "CODEX_SUBTYPE_AUTOMATRON", data_repo=data_repo
    )

    assert group.subtype == "CODEX_SUBTYPE_AUTOMATRON"
    assert 24068801 in {c.codex_id for c in group.creatures}
    codex = data_repo.load_animal_codex_excel_config_data()
    expected_order = sorted(
        (
            entry
            for entry in codex.values()
            if entry["subType"] == "CODEX_SUBTYPE_AUTOMATRON" and not entry["isDisuse"]
        ),
        key=lambda e: (e["sortOrder"], e["id"]),
    )
    assert [c.codex_id for c in group.creatures] == [e["id"] for e in expected_order]
    assert group.type_label == "魔物"
    assert group.subtype_label == "自律机关"


def test_creatures_discover_returns_subtype_groups(data_repo: repo.DataRepo) -> None:
    """Discovery enumerates the codex subType groups with non-disused entries."""
    codex = data_repo.load_animal_codex_excel_config_data()
    discovered = renderable_types.Creatures().discover(data_repo)

    assert discovered == sorted(
        {entry["subType"] for entry in codex.values() if not entry["isDisuse"]}
    )
    # Far fewer files than entries: a dozen-ish groups vs. hundreds of creatures.
    assert len(discovered) < 20 < len(codex)


def test_sexpro_resolves_from_pinned_build(
    data_repo: repo.DataRepo, english_data_repo: repo.DataRepo
) -> None:
    """SEXPRO tokens resolve to per-language text via the pinned old AGD build.

    6.x dropped these TextMap rows, so the TextMapTracker resolves the
    token's hash (from ManualTextMapConfigData) through its fallback TextMap.
    """
    placeholder = (
        "找{PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_HE|INFO_FEMALE_PRONOUN_SHE]}"
    )
    for repo_, expected in [(data_repo, "找他"), (english_data_repo, "找He")]:
        assert repo_.build_text_map_tracker().clean_text(placeholder) == expected
