"""Tests for AGD rendering functionality."""

import textwrap

from istaroth.agd import localization, rendering, types


def test_render_readable_basic() -> None:
    """Test basic readable rendering functionality."""
    content = "This is some readable content.\nWith multiple lines."
    metadata = types.ReadableMetadata(localization_id=0, title="Test Book Title")

    rendered = rendering.render_readable(content, metadata)

    assert rendered.text_metadata.relative_path == "agd_readable/0_Test_Book_Title.txt"
    assert (
        rendered.content
        == "# Test Book Title\n\nThis is some readable content.\nWith multiple lines."
    )
    assert rendered.text_metadata.id == 0


def test_render_readable_special_characters() -> None:
    """Test readable rendering with special characters in title."""
    content = "Content here."
    metadata = types.ReadableMetadata(localization_id=0, title="神霄折戟录·第六卷")

    rendered = rendering.render_readable(content, metadata)

    assert rendered.text_metadata.relative_path == "agd_readable/0_神霄折戟录第六卷.txt"
    assert rendered.content == "# 神霄折戟录·第六卷\n\nContent here."
    assert rendered.text_metadata.id == 0


def test_render_readable_whitespace() -> None:
    """Test readable rendering with excessive whitespace in title."""
    content = "Some content."
    metadata = types.ReadableMetadata(
        localization_id=0, title="  Title   With   Spaces  "
    )

    rendered = rendering.render_readable(content, metadata)

    assert (
        rendered.text_metadata.relative_path == "agd_readable/0_Title_With_Spaces.txt"
    )
    assert rendered.content == "#   Title   With   Spaces  \n\nSome content."
    assert rendered.text_metadata.id == 0


def test_render_weapon_multi_page_with_description() -> None:
    """A multi-page weapon story renders as one document under the weapon name."""
    weapon_info = types.WeaponInfo(
        weapon_id="11431",
        name="息燧之笛",
        description="造型奇特的玉石长刀。",
        story_pages=["第一页内容。", "第二页内容。"],
    )

    rendered = rendering.render_weapon(weapon_info)

    assert rendered.text_metadata.relative_path == "agd_weapon/11431_息燧之笛.txt"
    assert rendered.text_metadata.id == 11431
    assert rendered.content == (
        "# 息燧之笛\n\n造型奇特的玉石长刀。\n\n第一页内容。\n\n---\n\n第二页内容。"
    )


def test_render_weapon_single_page_no_description() -> None:
    """A weapon without a description omits the description block."""
    weapon_info = types.WeaponInfo(
        weapon_id="11101",
        name="无锋剑",
        description="",
        story_pages=["少年人的梦想。"],
    )

    rendered = rendering.render_weapon(weapon_info)

    assert rendered.text_metadata.relative_path == "agd_weapon/11101_无锋剑.txt"
    assert rendered.content == "# 无锋剑\n\n少年人的梦想。"


def test_render_achievement_section() -> None:
    """An achievement section renders as one categorized text document."""
    rendered = rendering.render_achievement_section(
        types.AchievementSectionInfo(
            section_id=46,
            section_name="枫丹·白露澈明的泉舞·其之三",
            achievements=[
                types.AchievementInfo(
                    achievement_id=80299,
                    name="水仙十字题解",
                    description="何物徒留名字？",
                )
            ],
        )
    )

    assert (
        rendered.text_metadata.relative_path
        == "agd_achievement/46_枫丹白露澈明的泉舞其之三.txt"
    )
    assert rendered.text_metadata.id == 46
    assert rendered.text_metadata.title == "枫丹·白露澈明的泉舞·其之三"
    assert rendered.content == (
        "# 枫丹·白露澈明的泉舞·其之三\n\n## 水仙十字题解\n\n何物徒留名字？"
    )


def test_render_talk_basic() -> None:
    """Test basic talk rendering functionality."""
    talk_texts = [
        types.TalkText(
            role="派蒙",
            message="这里看起来很神秘呢！",
            next_dialog_ids=[2],
            dialog_id=1,
        ),
        types.TalkText(
            role="旅行者", message="我们小心一点。", next_dialog_ids=[3], dialog_id=2
        ),
        types.TalkText(
            role="神秘声音", message="欢迎来到这里...", next_dialog_ids=[], dialog_id=3
        ),
    ]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info,
        talk_id=12345,
        language=localization.Language.CHS,
        talk_file_path="BinOutput/Talk/Quest/12345.json",
    )

    assert (
        rendered.text_metadata.relative_path == "agd_talk/12345_这里看起来很神秘呢.txt"
    )
    expected_content = (
        "# Talk Dialog\n\n"
        "派蒙: 这里看起来很神秘呢！\n"
        "旅行者: 我们小心一点。\n"
        "神秘声音: 欢迎来到这里..."
    )
    assert rendered.content == expected_content
    assert rendered.text_metadata.id == 12345


def test_render_talk_long_message() -> None:
    """Test talk rendering with long first message."""
    long_message = (
        "这是一个非常长的消息，超过了五十个字符的限制，应该被截断以创建合适的文件名。"
    )
    talk_texts = [
        types.TalkText(
            role="NPC", message=long_message, next_dialog_ids=[], dialog_id=1
        )
    ]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info,
        talk_id=67890,
        language=localization.Language.CHS,
        talk_file_path="BinOutput/Talk/NPC/67890.json",
    )

    assert (
        rendered.text_metadata.relative_path
        == "agd_talk/67890_这是一个非常长的消息超过了五十个字符的限制应该被截断以创建合适的文件名.txt"
    )
    assert (
        "这是一个非常长的消息，超过了五十个字符的限制，应该被截断以创建合适的文件名。"
        in rendered.content
    )
    assert rendered.text_metadata.id == 67890


def test_render_talk_empty() -> None:
    """Test talk rendering with empty talk."""
    talk_info = types.TalkInfo(text=[])

    rendered = rendering.render_talk(
        talk_info,
        talk_id=99999,
        language=localization.Language.CHS,
        talk_file_path="BinOutput/Talk/99999.json",
    )

    assert rendered.text_metadata.relative_path == "agd_talk/99999_empty.txt"
    assert rendered.content == "# Talk Dialog\n"
    assert rendered.text_metadata.id == 99999


def test_render_talk_special_characters() -> None:
    """Test talk rendering with special characters in message."""
    talk_texts = [
        types.TalkText(
            role="角色",
            message="「这是引号」—还有破折号！",
            next_dialog_ids=[],
            dialog_id=1,
        )
    ]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info,
        talk_id=11111,
        language=localization.Language.CHS,
        talk_file_path="BinOutput/Talk/Dialogue/11111.json",
    )

    assert (
        rendered.text_metadata.relative_path == "agd_talk/11111_这是引号还有破折号.txt"
    )
    assert "角色: 「这是引号」—还有破折号！" in rendered.content
    assert rendered.text_metadata.id == 11111


def test_render_talk_branching_convergence() -> None:
    """Test talk rendering with branching and convergence."""
    # Structure:
    # Line 1 -> branches to Option 1 and Option 2
    # Option 1 -> Line 2a -> Line 3a -> converges to Line 4
    # Option 2 -> Line 2b -> Line 3b -> converges to Line 4
    # Line 4 -> end
    talk_texts = [
        types.TalkText(
            role="NPC", message="Line 1", next_dialog_ids=[2, 5], dialog_id=1
        ),
        types.TalkText(
            role="Player", message="Line 2a", next_dialog_ids=[3], dialog_id=2
        ),
        types.TalkText(role="NPC", message="Line 3a", next_dialog_ids=[4], dialog_id=3),
        types.TalkText(role="NPC", message="Line 4", next_dialog_ids=[], dialog_id=4),
        types.TalkText(
            role="Player", message="Line 2b", next_dialog_ids=[6], dialog_id=5
        ),
        types.TalkText(role="NPC", message="Line 3b", next_dialog_ids=[4], dialog_id=6),
    ]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info,
        talk_id=99999,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/99999.json",
    )

    expected_content = textwrap.dedent(
        """
        # Talk Dialog

        NPC: Line 1

        Option 1:

        > Player: Line 2a
        > NPC: Line 3a

        Option 2:

        > Player: Line 2b
        > NPC: Line 3b

        NPC: Line 4
    """
    ).strip()
    assert rendered.content == expected_content


def test_render_talk_nested_branches() -> None:
    """Test talk rendering with nested branches."""
    # Structure:
    # Line 1 -> branches to Option 1 (Line 2) and Option 2 (Line 3)
    # Option 1 (Line 2) -> branches to Option 1a (Line 4) and Option 1b (Line 5)
    #   Option 1a (Line 4) -> Line 6 (convergence)
    #   Option 1b (Line 5) -> Line 6 (convergence)
    # Option 2 (Line 3) -> Line 6 (convergence)
    # Line 6 -> end
    talk_texts = [
        types.TalkText(
            role="NPC", message="Line 1", next_dialog_ids=[2, 3], dialog_id=1
        ),
        types.TalkText(
            role="Player", message="Line 2", next_dialog_ids=[4, 5], dialog_id=2
        ),
        types.TalkText(
            role="Player", message="Line 3", next_dialog_ids=[6], dialog_id=3
        ),
        types.TalkText(role="NPC", message="Line 4", next_dialog_ids=[6], dialog_id=4),
        types.TalkText(role="NPC", message="Line 5", next_dialog_ids=[6], dialog_id=5),
        types.TalkText(role="NPC", message="Line 6", next_dialog_ids=[], dialog_id=6),
    ]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info,
        talk_id=88888,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/88888.json",
    )

    expected_content = textwrap.dedent(
        """
        # Talk Dialog

        NPC: Line 1

        Option 1:

        > Player: Line 2
        > NPC: Line 4

        Option 2:

        > Player: Line 3

        Option 3:

        > Player: Line 2
        > NPC: Line 5

        NPC: Line 6
    """
    ).strip()
    assert rendered.content == expected_content


def test_render_talk_nested_branches_with_intermediate_convergence() -> None:
    """Test talk rendering with nested branches that converge at different levels."""
    # Structure:
    # Start -> branches to Option 1 (Branch 1) and Option 2 (Branch 2)
    # Branch 1 -> Convergence Y (end)
    # Branch 2 -> branches to Option 2a and Option 2b
    #   Option 2a -> Convergence X
    #   Option 2b -> Convergence X
    # Convergence X -> Convergence Y (end)
    # Convergence Y -> end
    talk_texts = [
        types.TalkText(
            role="NPC", message="Start", next_dialog_ids=[2, 3], dialog_id=1
        ),
        types.TalkText(
            role="Player", message="Branch 1", next_dialog_ids=[7], dialog_id=2
        ),
        types.TalkText(
            role="Player", message="Branch 2", next_dialog_ids=[4, 5], dialog_id=3
        ),
        types.TalkText(
            role="NPC", message="Branch 2a", next_dialog_ids=[6], dialog_id=4
        ),
        types.TalkText(
            role="NPC", message="Branch 2b", next_dialog_ids=[6], dialog_id=5
        ),
        types.TalkText(
            role="NPC", message="Convergence X", next_dialog_ids=[7], dialog_id=6
        ),
        types.TalkText(
            role="NPC", message="Convergence Y", next_dialog_ids=[], dialog_id=7
        ),
    ]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info,
        talk_id=77777,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/77777.json",
    )

    expected_content = textwrap.dedent(
        """
        # Talk Dialog

        NPC: Start

        Option 1:

        > Player: Branch 1

        Option 2:

        > Player: Branch 2
        > NPC: Branch 2a
        > NPC: Convergence X

        Option 3:

        > Player: Branch 2
        > NPC: Branch 2b
        > NPC: Convergence X

        NPC: Convergence Y
    """
    ).strip()
    assert rendered.content == expected_content


def test_render_talk_rebranching_convergence_no_duplicate_options() -> None:
    """A convergence node that itself re-branches must not duplicate options.

    Mirrors quest 76011 (issue #62): a 2-option choice converges at a node that
    has its own outgoing branch. The short option reaches the convergence node
    long before the long option; without pausing there it would walk through and
    split on the convergence node's out-edges, emitting copies of the short
    option that all share its pre-convergence prefix.
    """
    # 1 (menu) -> [2 (short option), 4 (long option)]
    # short: 2 -> 6 (convergence, reached in 1 step)
    # long:  4 -> 5 -> 6 (convergence, reached in 2 steps)
    # 6 (convergence) -> [7, 8] -> 9 (its own nested branch)
    talk_texts = [
        types.TalkText(role="NPC", message="Menu", next_dialog_ids=[2, 4], dialog_id=1),
        types.TalkText(
            role="Player", message="Short", next_dialog_ids=[6], dialog_id=2
        ),
        types.TalkText(role="Player", message="Long", next_dialog_ids=[5], dialog_id=4),
        types.TalkText(
            role="NPC", message="Long tail", next_dialog_ids=[6], dialog_id=5
        ),
        types.TalkText(
            role="NPC", message="Converged", next_dialog_ids=[7, 8], dialog_id=6
        ),
        types.TalkText(
            role="Player", message="After A", next_dialog_ids=[9], dialog_id=7
        ),
        types.TalkText(
            role="Player", message="After B", next_dialog_ids=[9], dialog_id=8
        ),
        types.TalkText(role="NPC", message="End", next_dialog_ids=[], dialog_id=9),
    ]

    rendered = rendering.render_talk(
        types.TalkInfo(text=talk_texts),
        talk_id=66666,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/66666.json",
    )

    # Exactly two options at the first choice, neither duplicated.
    assert rendered.content.count("Player: Short") == 1, rendered.content
    assert rendered.content.count("Player: Long") == 1, rendered.content
    # The convergence node's own branch still renders after the options.
    assert "NPC: Converged" in rendered.content
    for line in ("Player: After A", "Player: After B"):
        assert line in rendered.content, rendered.content


def test_render_talk_menu_hub_no_blowup() -> None:
    """An "ask about X" menu whose answers loop back renders each topic once.

    Mirrors the in-game shape (e.g. quest 6000): the initial menu offers only the
    topics; each answer tail re-presents a menu that adds an exit option. Without
    menu re-entry detection, enumerating every root-to-leaf path through the cyclic
    hub renders each topic answer once per ordering of the topics (combinatorial
    blow-up). Each unique line must appear exactly once, and the exit branch
    (reachable only from a re-presented menu) must still render.
    """
    # 1 (menu) -> [2 (topic A), 4 (topic B)]          (no exit yet)
    # topic A: 2 -> 3 (answer A) -> 7 (re-presented menu) -> [2, 4, 6]
    # topic B: 4 -> 5 (answer B) -> 8 (re-presented menu) -> [2, 4, 6]
    # exit:    6 -> 9 (goodbye)  -> end
    talk_texts = [
        types.TalkText(
            role="NPC", message="Ask away", next_dialog_ids=[2, 4], dialog_id=1
        ),
        types.TalkText(
            role="Player", message="Topic A?", next_dialog_ids=[3], dialog_id=2
        ),
        types.TalkText(
            role="NPC", message="Answer A", next_dialog_ids=[7], dialog_id=3
        ),
        types.TalkText(
            role="Player", message="Topic B?", next_dialog_ids=[5], dialog_id=4
        ),
        types.TalkText(
            role="NPC", message="Answer B", next_dialog_ids=[8], dialog_id=5
        ),
        types.TalkText(
            role="Player", message="Nothing", next_dialog_ids=[9], dialog_id=6
        ),
        types.TalkText(role="NPC", message="Goodbye", next_dialog_ids=[], dialog_id=9),
        types.TalkText(
            role="NPC", message="More?", next_dialog_ids=[2, 4, 6], dialog_id=7
        ),
        types.TalkText(
            role="NPC", message="More?", next_dialog_ids=[2, 4, 6], dialog_id=8
        ),
    ]
    rendered = rendering.render_talk(
        types.TalkInfo(text=talk_texts),
        talk_id=88888,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/88888.json",
    )

    # Each unique answer line appears exactly once (no permutation blow-up), and
    # the exit branch's content is still present.
    for line in ("NPC: Answer A", "NPC: Answer B", "NPC: Goodbye"):
        assert rendered.content.count(line) == 1, rendered.content


def test_render_talk_cascaded_correct_answer_menus_no_spurious_options() -> None:
    """Cascaded "wrong answers loop, right one continues" menus stay one-per-choice.

    Mirrors quest 11008's evidence menus: each wrong-answer tail re-offers exactly
    the seed options (a back-edge join whose out-edges are all already covered),
    and the correct answer runs on into the next such menu. The convergence-wait
    must not stall at those back-edge joins, or each menu spawns extra empty
    option branches (here 8 options / 4 empty instead of the correct 6 / 2).
    """
    # M1 (11) -> [12 correct, 13 wrong, 14 wrong]
    #   correct: 12 -> 15 -> 17 -> 18 -> M2 (22)
    #   wrong:   13 -> 16, 14 -> 16; 16 re-offers [12, 13, 14]
    # M2 (22) -> [23 correct, 24 wrong, 25 wrong]
    #   correct: 23 -> 26 -> 28 (end);  wrong: 24 -> 27, 25 -> 27; 27 re-offers
    talk_texts = [
        types.TalkText(
            role="NPC", message="M1", next_dialog_ids=[12, 13, 14], dialog_id=11
        ),
        types.TalkText(
            role="Player", message="1-correct", next_dialog_ids=[15], dialog_id=12
        ),
        types.TalkText(
            role="Player", message="1-wrongA", next_dialog_ids=[16], dialog_id=13
        ),
        types.TalkText(
            role="Player", message="1-wrongB", next_dialog_ids=[16], dialog_id=14
        ),
        types.TalkText(
            role="NPC", message="right1", next_dialog_ids=[17], dialog_id=15
        ),
        types.TalkText(
            role="NPC", message="wrong1", next_dialog_ids=[12, 13, 14], dialog_id=16
        ),
        types.TalkText(role="NPC", message="mid17", next_dialog_ids=[18], dialog_id=17),
        types.TalkText(role="NPC", message="mid18", next_dialog_ids=[22], dialog_id=18),
        types.TalkText(
            role="NPC", message="M2", next_dialog_ids=[23, 24, 25], dialog_id=22
        ),
        types.TalkText(
            role="Player", message="2-correct", next_dialog_ids=[26], dialog_id=23
        ),
        types.TalkText(
            role="Player", message="2-wrongA", next_dialog_ids=[27], dialog_id=24
        ),
        types.TalkText(
            role="Player", message="2-wrongB", next_dialog_ids=[27], dialog_id=25
        ),
        types.TalkText(
            role="NPC", message="right2", next_dialog_ids=[28], dialog_id=26
        ),
        types.TalkText(
            role="NPC", message="wrong2", next_dialog_ids=[23, 24, 25], dialog_id=27
        ),
        types.TalkText(role="NPC", message="End", next_dialog_ids=[], dialog_id=28),
    ]
    rendered = rendering.render_talk(
        types.TalkInfo(text=talk_texts),
        talk_id=55555,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/55555.json",
    )

    # Three options per menu, two menus -> six options; no spurious extras.
    assert rendered.content.count("Option ") == 6, rendered.content
    # Each wrong answer renders once; both correct continuations are present.
    for line in ("Player: 1-wrongA", "Player: 2-wrongA", "NPC: right1", "NPC: End"):
        assert rendered.content.count(line) == 1, rendered.content


def _quest_talk_step(
    order: int, message: str, *, is_lead_in: bool = False
) -> types.QuestStep:
    return types.QuestStep(
        order=order,
        is_lead_in=is_lead_in,
        description=None,
        talk=types.TalkInfo(
            text=[
                types.TalkText(
                    role="NPC", message=message, next_dialog_ids=[], dialog_id=1
                )
            ]
        ),
    )


def test_render_quest_numbers_variant_talks() -> None:
    """Multiple completing talks at one order get `(variant N)`; singletons don't."""
    quest = types.QuestInfo(
        quest_id=73000,
        title="Test Quest",
        chapter_title=None,
        description=None,
        steps=[
            _quest_talk_step(1, "First branch"),
            _quest_talk_step(1, "Second branch"),
            _quest_talk_step(2, "Lone talk"),
            _quest_talk_step(3, "Lead-in", is_lead_in=True),
            _quest_talk_step(3, "Completing"),
        ],
        non_subquest_talks=[],
        associated_free_talks=[],
    )

    content = rendering.render_quest(quest, localization.Language.ENG).content

    assert "## Talk 1 (variant 1)" in content
    assert "## Talk 1 (variant 2)" in content
    assert "## Talk 2\n" in content
    assert "(variant" not in content.split("## Talk 2")[1]
    assert "## Talk 3 (alternative/additional)" in content
    assert "## Talk 3\n" in content


def test_render_character_story_constellations() -> None:
    """Constellations render as a flat name: description list, descriptions on one line."""
    story_info = types.CharacterStoryInfo(
        character_name="Tester",
        stories=[types.CharacterStory(title="Story 1", content="Once upon a time.")],
        avatar_id=10000099,
        constellations=[
            types.Constellation(
                name="First Star", description="Line one.\nLine two.", element=None
            ),
            types.Constellation(
                name="Second Star", description="A single effect.", element=None
            ),
        ],
    )

    content = rendering.render_character_story(story_info).content

    assert "## Constellations\n" in content
    assert "First Star: Line one. Line two." in content
    assert "Second Star: A single effect." in content
    assert "###" not in content  # no element subsections for regular characters


def test_render_character_story_traveler_constellations_grouped() -> None:
    """Traveler constellations group under ### element subsections."""
    story_info = types.CharacterStoryInfo(
        character_name="Traveler",
        stories=[],
        avatar_id=10000005,
        constellations=[
            types.Constellation(name="Pyro One", description="P1", element="Pyro"),
            types.Constellation(name="Pyro Two", description="P2", element="Pyro"),
            types.Constellation(name="Hydro One", description="H1", element="Hydro"),
        ],
    )

    content = rendering.render_character_story(story_info).content

    assert "### Pyro\n" in content
    assert "### Hydro\n" in content
    # Pyro group comes before Hydro group, and its members sit under its header.
    assert content.index("### Pyro") < content.index("Pyro One: P1")
    assert content.index("Pyro Two: P2") < content.index("### Hydro")
    assert "Hydro One: H1" in content
