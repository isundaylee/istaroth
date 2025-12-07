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
        talk_id="12345",
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
        talk_id="67890",
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
        talk_id="99999",
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
        talk_id="11111",
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
        talk_id="99999",
        language=localization.Language.ENG,
        talk_file_path="BinOutput/Talk/Quest/99999.json",
    )

    expected_content = textwrap.dedent(
        """
        # Talk Dialog

        NPC: Line 1
            Option 1:
                Player: Line 2a
                NPC: Line 3a
            Option 2:
                Player: Line 2b
                NPC: Line 3b
        NPC: Line 4
    """
    ).strip()
    assert rendered.content == expected_content
