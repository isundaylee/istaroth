"""Tests for AGD rendering functionality."""

import textwrap
from typing import Iterable

import pytest

from istaroth.agd import first_seen, localization, processed_types
from istaroth.agd.renderables import (
    _talk,
    achievement,
    book,
    character,
    creature,
    quest,
    readable,
    talk_group,
    weapon,
)
from istaroth.text import types as text_types


class _StubFirstSeenIndex(first_seen.FirstSeenIndex):
    """Resolves every source id to a fixed version for rendering tests."""

    def resolve(self, source_ids: Iterable[first_seen.SourceId]) -> tuple[str, str]:
        return ("1.0", "1.0")


_FAKE_FIRST_SEEN_INDEX = _StubFirstSeenIndex(versions={})


def test_render_readable_basic() -> None:
    """Test basic readable rendering functionality."""
    content = "This is some readable content.\nWith multiple lines."
    metadata = processed_types.ReadableMetadata(
        localization_id=0, title="Test Book Title"
    )

    rendered = readable.render_readable_like(
        content,
        metadata,
        "Test_EN.txt",
        category=text_types.TextCategory.AGD_READABLE,
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )

    assert rendered.text_metadata.relative_path == "agd_readable/0_Test_Book_Title.txt"
    assert (
        rendered.content
        == "# Test Book Title\n\nThis is some readable content.\nWith multiple lines."
    )
    assert rendered.text_metadata.id == 0


def test_render_readable_special_characters() -> None:
    """Test readable rendering with special characters in title."""
    content = "Content here."
    metadata = processed_types.ReadableMetadata(
        localization_id=0, title="神霄折戟录·第六卷"
    )

    rendered = readable.render_readable_like(
        content,
        metadata,
        "Book999.txt",
        category=text_types.TextCategory.AGD_READABLE,
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )

    assert rendered.text_metadata.relative_path == "agd_readable/0_神霄折戟录第六卷.txt"
    assert rendered.content == "# 神霄折戟录·第六卷\n\nContent here."
    assert rendered.text_metadata.id == 0


def test_render_readable_whitespace() -> None:
    """Test readable rendering with excessive whitespace in title."""
    content = "Some content."
    metadata = processed_types.ReadableMetadata(
        localization_id=0, title="  Title   With   Spaces  "
    )

    rendered = readable.render_readable_like(
        content,
        metadata,
        "Book998.txt",
        category=text_types.TextCategory.AGD_READABLE,
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )

    assert (
        rendered.text_metadata.relative_path == "agd_readable/0_Title_With_Spaces.txt"
    )
    assert rendered.content == "#   Title   With   Spaces  \n\nSome content."
    assert rendered.text_metadata.id == 0


def test_render_weapon_multi_page_with_description() -> None:
    """A multi-page weapon story renders as one document under the weapon name."""
    weapon_info = processed_types.WeaponInfo(
        weapon_id="11431",
        name="息燧之笛",
        description="造型奇特的玉石长刀。",
        story_pages=["第一页内容。", "第二页内容。"],
    )

    rendered = weapon.render_weapon(
        weapon_info, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    )

    assert rendered.text_metadata.relative_path == "agd_weapon/11431_息燧之笛.txt"
    assert rendered.text_metadata.id == 11431
    assert rendered.content == (
        "# 息燧之笛\n\n造型奇特的玉石长刀。\n\n第一页内容。\n\n---\n\n第二页内容。"
    )


def test_render_weapon_single_page_no_description() -> None:
    """A weapon without a description omits the description block."""
    weapon_info = processed_types.WeaponInfo(
        weapon_id="11101",
        name="无锋剑",
        description="",
        story_pages=["少年人的梦想。"],
    )

    rendered = weapon.render_weapon(
        weapon_info, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    )

    assert rendered.text_metadata.relative_path == "agd_weapon/11101_无锋剑.txt"
    assert rendered.content == "# 无锋剑\n\n少年人的梦想。"


def test_render_achievement_section() -> None:
    """An achievement section renders as one categorized text document."""
    rendered = achievement.render_achievement_section(
        processed_types.AchievementSectionInfo(
            section_id=46,
            section_name="枫丹·白露澈明的泉舞·其之三",
            achievements=[
                processed_types.AchievementInfo(
                    achievement_id=80299,
                    name="水仙十字题解",
                    description="何物徒留名字？",
                )
            ],
        ),
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
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
        processed_types.TalkText(
            role="派蒙",
            message="这里看起来很神秘呢！",
            next_dialog_ids=[2],
            dialog_id=1,
            skip=False,
        ),
        processed_types.TalkText(
            role="旅行者",
            message="我们小心一点。",
            next_dialog_ids=[3],
            dialog_id=2,
            skip=False,
        ),
        processed_types.TalkText(
            role="神秘声音",
            message="欢迎来到这里...",
            next_dialog_ids=[],
            dialog_id=3,
            skip=False,
        ),
    ]
    talk_info = processed_types.TalkInfo(text=talk_texts)

    rendered = _talk.render_talk(
        talk_info,
        talk_id=12345,
        language=localization.Language.CHS,
        talk_file_path="BinOutput/Talk/Quest/12345.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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


def test_render_talk_all_skipped_returns_none() -> None:
    """A talk whose every line is dev/test-skipped emits no file at all."""
    talk_info = processed_types.TalkInfo(
        text=[
            processed_types.TalkText(
                role=None,
                message="test台词文本",
                next_dialog_ids=[],
                dialog_id=1,
                skip=True,
            ),
            processed_types.TalkText(
                role="(test)旅人兰那罗",
                message="(test)好汉不吃眼前亏，我先去东南方向的洞里躲一躲",
                next_dialog_ids=[],
                dialog_id=2,
                skip=False,
            ),
        ]
    )
    assert (
        _talk.render_talk(
            talk_info,
            talk_id=6863205,
            language=localization.Language.CHS,
            talk_file_path="BinOutput/Talk/Gadget/6863205.json",
            first_seen_index=_FAKE_FIRST_SEEN_INDEX,
        )
        is None
    )


def test_render_talk_long_message() -> None:
    """Test talk rendering with long first message."""
    long_message = (
        "这是一个非常长的消息，超过了五十个字符的限制，应该被截断以创建合适的文件名。"
    )
    talk_texts = [
        processed_types.TalkText(
            role="NPC",
            message=long_message,
            next_dialog_ids=[],
            dialog_id=1,
            skip=False,
        )
    ]
    talk_info = processed_types.TalkInfo(text=talk_texts)

    rendered = _talk.render_talk(
        talk_info,
        talk_id=67890,
        language=localization.Language.CHS,
        talk_file_path="BinOutput/Talk/NPC/67890.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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
    talk_info = processed_types.TalkInfo(text=[])

    assert (
        _talk.render_talk(
            talk_info,
            talk_id=99999,
            language=localization.Language.CHS,
            talk_file_path="BinOutput/Talk/99999.json",
            first_seen_index=_FAKE_FIRST_SEEN_INDEX,
        )
        is None
    )


def test_render_talk_special_characters() -> None:
    """Test talk rendering with special characters in message."""
    talk_texts = [
        processed_types.TalkText(
            role="角色",
            message="「这是引号」—还有破折号！",
            next_dialog_ids=[],
            dialog_id=1,
            skip=False,
        )
    ]
    talk_info = processed_types.TalkInfo(text=talk_texts)

    rendered = _talk.render_talk(
        talk_info,
        talk_id=11111,
        language=localization.Language.CHS,
        talk_file_path="BinOutput/Talk/Dialogue/11111.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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
        processed_types.TalkText(
            role="NPC",
            message="Line 1",
            next_dialog_ids=[2, 5],
            dialog_id=1,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Line 2a",
            next_dialog_ids=[3],
            dialog_id=2,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Line 3a",
            next_dialog_ids=[4],
            dialog_id=3,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Line 4",
            next_dialog_ids=[],
            dialog_id=4,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Line 2b",
            next_dialog_ids=[6],
            dialog_id=5,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Line 3b",
            next_dialog_ids=[4],
            dialog_id=6,
            skip=False,
        ),
    ]
    talk_info = processed_types.TalkInfo(text=talk_texts)

    rendered = _talk.render_talk(
        talk_info,
        talk_id=99999,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/99999.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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
        processed_types.TalkText(
            role="NPC",
            message="Line 1",
            next_dialog_ids=[2, 3],
            dialog_id=1,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Line 2",
            next_dialog_ids=[4, 5],
            dialog_id=2,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Line 3",
            next_dialog_ids=[6],
            dialog_id=3,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Line 4",
            next_dialog_ids=[6],
            dialog_id=4,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Line 5",
            next_dialog_ids=[6],
            dialog_id=5,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Line 6",
            next_dialog_ids=[],
            dialog_id=6,
            skip=False,
        ),
    ]
    talk_info = processed_types.TalkInfo(text=talk_texts)

    rendered = _talk.render_talk(
        talk_info,
        talk_id=88888,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/88888.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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
        processed_types.TalkText(
            role="NPC",
            message="Start",
            next_dialog_ids=[2, 3],
            dialog_id=1,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Branch 1",
            next_dialog_ids=[7],
            dialog_id=2,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Branch 2",
            next_dialog_ids=[4, 5],
            dialog_id=3,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Branch 2a",
            next_dialog_ids=[6],
            dialog_id=4,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Branch 2b",
            next_dialog_ids=[6],
            dialog_id=5,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Convergence X",
            next_dialog_ids=[7],
            dialog_id=6,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Convergence Y",
            next_dialog_ids=[],
            dialog_id=7,
            skip=False,
        ),
    ]
    talk_info = processed_types.TalkInfo(text=talk_texts)

    rendered = _talk.render_talk(
        talk_info,
        talk_id=77777,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/77777.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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
        processed_types.TalkText(
            role="NPC",
            message="Menu",
            next_dialog_ids=[2, 4],
            dialog_id=1,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Short",
            next_dialog_ids=[6],
            dialog_id=2,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Long",
            next_dialog_ids=[5],
            dialog_id=4,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Long tail",
            next_dialog_ids=[6],
            dialog_id=5,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Converged",
            next_dialog_ids=[7, 8],
            dialog_id=6,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="After A",
            next_dialog_ids=[9],
            dialog_id=7,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="After B",
            next_dialog_ids=[9],
            dialog_id=8,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="End",
            next_dialog_ids=[],
            dialog_id=9,
            skip=False,
        ),
    ]

    rendered = _talk.render_talk(
        processed_types.TalkInfo(text=talk_texts),
        talk_id=66666,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/66666.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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
        processed_types.TalkText(
            role="NPC",
            message="Ask away",
            next_dialog_ids=[2, 4],
            dialog_id=1,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Topic A?",
            next_dialog_ids=[3],
            dialog_id=2,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Answer A",
            next_dialog_ids=[7],
            dialog_id=3,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Topic B?",
            next_dialog_ids=[5],
            dialog_id=4,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Answer B",
            next_dialog_ids=[8],
            dialog_id=5,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="Nothing",
            next_dialog_ids=[9],
            dialog_id=6,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="Goodbye",
            next_dialog_ids=[],
            dialog_id=9,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="More?",
            next_dialog_ids=[2, 4, 6],
            dialog_id=7,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="More?",
            next_dialog_ids=[2, 4, 6],
            dialog_id=8,
            skip=False,
        ),
    ]
    rendered = _talk.render_talk(
        processed_types.TalkInfo(text=talk_texts),
        talk_id=88888,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/88888.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

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
        processed_types.TalkText(
            role="NPC",
            message="M1",
            next_dialog_ids=[12, 13, 14],
            dialog_id=11,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="1-correct",
            next_dialog_ids=[15],
            dialog_id=12,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="1-wrongA",
            next_dialog_ids=[16],
            dialog_id=13,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="1-wrongB",
            next_dialog_ids=[16],
            dialog_id=14,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="right1",
            next_dialog_ids=[17],
            dialog_id=15,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="wrong1",
            next_dialog_ids=[12, 13, 14],
            dialog_id=16,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="mid17",
            next_dialog_ids=[18],
            dialog_id=17,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="mid18",
            next_dialog_ids=[22],
            dialog_id=18,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="M2",
            next_dialog_ids=[23, 24, 25],
            dialog_id=22,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="2-correct",
            next_dialog_ids=[26],
            dialog_id=23,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="2-wrongA",
            next_dialog_ids=[27],
            dialog_id=24,
            skip=False,
        ),
        processed_types.TalkText(
            role="Player",
            message="2-wrongB",
            next_dialog_ids=[27],
            dialog_id=25,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="right2",
            next_dialog_ids=[28],
            dialog_id=26,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="wrong2",
            next_dialog_ids=[23, 24, 25],
            dialog_id=27,
            skip=False,
        ),
        processed_types.TalkText(
            role="NPC",
            message="End",
            next_dialog_ids=[],
            dialog_id=28,
            skip=False,
        ),
    ]
    rendered = _talk.render_talk(
        processed_types.TalkInfo(text=talk_texts),
        talk_id=55555,
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/55555.json",
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )
    assert rendered is not None

    # Three options per menu, two menus -> six options; no spurious extras.
    assert rendered.content.count("Option ") == 6, rendered.content
    # Each wrong answer renders once; both correct continuations are present.
    for line in ("Player: 1-wrongA", "Player: 2-wrongA", "NPC: right1", "NPC: End"):
        assert rendered.content.count(line) == 1, rendered.content


def _quest_talk_step(
    order: int, message: str, *, is_lead_in: bool = False
) -> processed_types.QuestStep:
    return processed_types.QuestStep(
        order=order,
        is_lead_in=is_lead_in,
        description=None,
        talk=processed_types.TalkInfo(
            text=[
                processed_types.TalkText(
                    role="NPC",
                    message=message,
                    next_dialog_ids=[],
                    dialog_id=1,
                    skip=False,
                )
            ]
        ),
    )


def test_render_quest_numbers_variant_talks() -> None:
    """Multiple completing talks at one order get `(variant N)`; singletons don't."""
    quest_info = processed_types.QuestInfo(
        quest_id=73000,
        title="Test Quest",
        chapter_title=None,
        group_name=None,
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

    content = quest.render_quest(
        quest_info, localization.Language.ENG, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    ).content

    assert "## Talk 1 (variant 1)" in content
    assert "## Talk 1 (variant 2)" in content
    assert "## Talk 2\n" in content
    assert "(variant" not in content.split("## Talk 2")[1]
    assert "## Talk 3 (alternative/additional)" in content
    assert "## Talk 3\n" in content


@pytest.mark.parametrize(
    "titles,expected",
    [
        # CHS ·-separated ordinals
        (["山中好长日·序章 魔山", "山中好长日·第一章 天堂"], "山中好长日"),
        # Space-separated CHS ordinals
        (["森林书 第一章 林中奇遇", "森林书 第二章 梦中的苗圃"], "森林书"),
        # Roman numerals are prefix-closed (I/II); cut at the strong separator
        (
            ["Aranyaka: Part I Woodland Encounter", "Aranyaka: Part II Dream Nursery"],
            "Aranyaka",
        ),
        # Divergence right at the separator (with/without colon) needs no cut
        (
            [
                "Canticles of Harmony Prelude Petrichorror Dream",
                "Canticles of Harmony: Finale Requiem",
            ],
            "Canticles of Harmony",
        ),
        # No strong separator: cut back to the last non-alphanumeric character
        (
            ["欢夏！邪龙？童话国！第一页 A", "欢夏！邪龙？童话国！第二页 B"],
            "欢夏！邪龙？童话国！",
        ),
        # Hyphen works as a strong separator too
        (
            [
                "Fabulous Fungus Frenzy - Act I X",
                "Fabulous Fungus Frenzy - Act II Y",
            ],
            "Fabulous Fungus Frenzy",
        ),
        # Nothing in common
        (["夏活 夏活beta测试任务", "绘夏！烈日？度假村！其一 C"], None),
    ],
)
def test_common_prefix_name(titles: list[str], expected: str | None) -> None:
    assert quest._common_prefix_name(titles) == expected


def test_render_quest_group_line() -> None:
    """A quest with a group name renders it above the chapter line."""
    quest_info = processed_types.QuestInfo(
        quest_id=76095,
        title="Paradise",
        chapter_title="A Long Day in the Mountains: Chapter 1 Paradise",
        group_name="A Long Day in the Mountains",
        description=None,
        steps=[_quest_talk_step(1, "Hello")],
        non_subquest_talks=[],
        associated_free_talks=[],
    )

    content = quest.render_quest(
        quest_info, localization.Language.ENG, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    ).content

    assert content.index(
        "(Quest is part of group: A Long Day in the Mountains)"
    ) < content.index(
        "(Quest is part of chapter: A Long Day in the Mountains: Chapter 1 Paradise)"
    )


def test_render_character_story_constellations() -> None:
    """Constellations render as a flat name: description list, descriptions on one line."""
    story_info = processed_types.CharacterStoryInfo(
        character_name="Tester",
        stories=[
            processed_types.CharacterStory(title="Story 1", content="Once upon a time.")
        ],
        avatar_id=10000099,
        constellations=[
            processed_types.Constellation(
                name="First Star", description="Line one.\nLine two.", element=None
            ),
            processed_types.Constellation(
                name="Second Star", description="A single effect.", element=None
            ),
        ],
    )

    content = character.render_character_story(
        story_info, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    ).content

    assert "## Constellations\n" in content
    assert "First Star: Line one. Line two." in content
    assert "Second Star: A single effect." in content
    assert "###" not in content  # no element subsections for regular characters


def test_render_character_story_traveler_constellations_grouped() -> None:
    """Traveler constellations group under ### element subsections."""
    story_info = processed_types.CharacterStoryInfo(
        character_name="Traveler",
        stories=[],
        avatar_id=10000005,
        constellations=[
            processed_types.Constellation(
                name="Pyro One", description="P1", element="Pyro"
            ),
            processed_types.Constellation(
                name="Pyro Two", description="P2", element="Pyro"
            ),
            processed_types.Constellation(
                name="Hydro One", description="H1", element="Hydro"
            ),
        ],
    )

    content = character.render_character_story(
        story_info, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    ).content

    assert "### Pyro\n" in content
    assert "### Hydro\n" in content
    # Pyro group comes before Hydro group, and its members sit under its header.
    assert content.index("### Pyro") < content.index("Pyro One: P1")
    assert content.index("Pyro Two: P2") < content.index("### Hydro")
    assert "Hydro One: H1" in content


def test_render_creature_group_monster() -> None:
    """A monster group renders a group header plus each entry's names and description."""
    rendered = creature.render_creature_group(
        processed_types.CreatureGroupInfo(
            subtype="CODEX_SUBTYPE_AUTOMATRON",
            type_label="魔物",
            subtype_label="自律机关",
            creatures=[
                processed_types.CreatureInfo(
                    codex_id=24068801,
                    name="攻坚特化型机关",
                    special_name="谢尔比乌斯式机关",
                    title="攻坚特化型",
                    description="与「侦察记录型」一样，是最早设计制造的新式发条机关机械之一。",
                ),
                processed_types.CreatureInfo(
                    codex_id=20070101,
                    name="遗迹守卫",
                    special_name=None,
                    title=None,
                    description="古代文明的造物。",
                ),
            ],
        ),
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )

    assert (
        rendered.text_metadata.relative_path
        == "agd_creature/"
        + str(rendered.text_metadata.id)
        + "_CODEX_SUBTYPE_AUTOMATRON.txt"
    )
    assert rendered.text_metadata.title == "自律机关"
    assert rendered.content == (
        "# 自律机关 (魔物)\n\n"
        "## 攻坚特化型机关\n"
        "谢尔比乌斯式机关\n"
        "Also known as: 攻坚特化型\n\n"
        "与「侦察记录型」一样，是最早设计制造的新式发条机关机械之一。\n\n"
        "## 遗迹守卫\n\n"
        "古代文明的造物。"
    )


def test_render_creature_group_stable_id() -> None:
    """The group id/filename derive deterministically from the subType enum."""
    a = creature.render_creature_group(
        processed_types.CreatureGroupInfo(
            subtype="CODEX_SUBTYPE_FISH",
            type_label="野生生物",
            subtype_label="鱼类",
            creatures=[
                processed_types.CreatureInfo(
                    codex_id=28040101,
                    name="黑背鲈鱼",
                    special_name=None,
                    title=None,
                    description="常见的鱼类。",
                )
            ],
        ),
        first_seen_index=_FAKE_FIRST_SEEN_INDEX,
    )

    assert a.text_metadata.relative_path.endswith("_CODEX_SUBTYPE_FISH.txt")
    assert a.content == "# 鱼类 (野生生物)\n\n## 黑背鲈鱼\n\n常见的鱼类。"


def test_render_book_series_english() -> None:
    """A series renders one file with a per-volume English annotation line."""
    series_info = processed_types.BookSeriesInfo(
        suit_id=1019,
        series_name="A Drunkard's Tale",
        volumes=[
            processed_types.BookVolumeInfo(
                title="A Drunkard's Tale (I)", content="First.", filename="Book119.txt"
            ),
            processed_types.BookVolumeInfo(
                title="A Drunkard's Tale (II)",
                content="Second.",
                filename="Book120.txt",
            ),
        ],
    )

    rendered = book.render_book_series(
        series_info, localization.Language.ENG, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    )

    assert rendered.text_metadata.relative_path == "agd_book/1019_A_Drunkards_Tale.txt"
    assert rendered.text_metadata.id == 1019
    assert rendered.text_metadata.title == "A Drunkard's Tale"
    assert rendered.content == (
        "# A Drunkard's Tale\n\n"
        "## A Drunkard's Tale (I)\n\n"
        "*A Drunkard's Tale — Volume 1 of 2*\n\n"
        "First.\n\n"
        "## A Drunkard's Tale (II)\n\n"
        "*A Drunkard's Tale — Volume 2 of 2*\n\n"
        "Second."
    )


def test_render_book_series_chinese_annotation() -> None:
    """The per-volume annotation localizes for Chinese output."""
    series_info = processed_types.BookSeriesInfo(
        suit_id=3,
        series_name="维莉的忧郁",
        volumes=[
            processed_types.BookVolumeInfo(
                title="维莉的忧郁·一", content="正文。", filename="Book50.txt"
            )
        ],
    )

    rendered = book.render_book_series(
        series_info, localization.Language.CHS, first_seen_index=_FAKE_FIRST_SEEN_INDEX
    )

    assert "*维莉的忧郁·第 1 卷，共 1 卷*" in rendered.content


def _talk_group_info(
    *roles: str | None, skip_roles: frozenset[str]
) -> processed_types.TalkGroupInfo:
    """One-line-per-role TalkGroupInfo for speaker-name derivation tests."""
    texts = [
        processed_types.TalkText(
            role=role,
            message="msg",
            next_dialog_ids=[],
            dialog_id=i,
            skip=role in skip_roles,
        )
        for i, role in enumerate(roles)
    ]
    return processed_types.TalkGroupInfo(
        talks=[(processed_types.TalkInfo(text=texts), [])], talk_ids=[1]
    )


@pytest.mark.parametrize(
    "roles,skip_roles,expected",
    [
        # Generic-only speakers give no name.
        (("旅行者", "派蒙", "???", None), frozenset(), None),
        (("告示板",), frozenset(), "告示板"),
        # Most talkative first; more than three named speakers get an ellipsis.
        (("甲", "乙", "乙", "丙", "丁"), frozenset(), "乙 / 甲 / 丙 / ..."),
        # A generic-half composite counts as its specific half; a named-half
        # composite dedups with the plain name.
        (("旅行者 (观察花卉)",), frozenset(), "观察花卉"),
        (("遗迹的铭文 (铭文)", "遗迹的铭文"), frozenset(), "遗迹的铭文"),
        # Placeholder roles and skip-flagged (dev/test) lines are dropped.
        (("Unknown Role (TALK_ROLE_GADGET)",), frozenset(), None),
        (("[Missing Talk]",), frozenset(), None),
        (
            ("（test）阿圆 (阿圆)", "阿圆"),
            frozenset({"（test）阿圆 (阿圆)"}),
            "阿圆",
        ),
    ],
)
def test_derive_speaker_group_name(
    roles: tuple[str | None, ...], skip_roles: frozenset[str], expected: str | None
) -> None:
    assert (
        talk_group.derive_speaker_group_name(
            _talk_group_info(*roles, skip_roles=skip_roles), localization.Language.CHS
        )
        == expected
    )
