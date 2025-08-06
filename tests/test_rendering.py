"""Tests for AGD rendering functionality."""

from istaroth.agd import localization, rendering, types


def test_render_readable_basic() -> None:
    """Test basic readable rendering functionality."""
    content = "This is some readable content.\nWith multiple lines."
    metadata = types.ReadableMetadata(localization_id=0, title="Test Book Title")

    rendered = rendering.render_readable(content, metadata)

    assert rendered.filename == "readable_Test_Book_Title.txt"
    assert (
        rendered.content
        == "# Test Book Title\n\nThis is some readable content.\nWith multiple lines."
    )


def test_render_readable_special_characters() -> None:
    """Test readable rendering with special characters in title."""
    content = "Content here."
    metadata = types.ReadableMetadata(localization_id=0, title="神霄折戟录·第六卷")

    rendered = rendering.render_readable(content, metadata)

    assert rendered.filename == "readable_神霄折戟录第六卷.txt"
    assert rendered.content == "# 神霄折戟录·第六卷\n\nContent here."


def test_render_readable_whitespace() -> None:
    """Test readable rendering with excessive whitespace in title."""
    content = "Some content."
    metadata = types.ReadableMetadata(
        localization_id=0, title="  Title   With   Spaces  "
    )

    rendered = rendering.render_readable(content, metadata)

    assert rendered.filename == "readable_Title_With_Spaces.txt"
    assert rendered.content == "#   Title   With   Spaces  \n\nSome content."


def test_render_talk_basic() -> None:
    """Test basic talk rendering functionality."""
    talk_texts = [
        types.TalkText(role="派蒙", message="这里看起来很神秘呢！"),
        types.TalkText(role="旅行者", message="我们小心一点。"),
        types.TalkText(role="神秘声音", message="欢迎来到这里..."),
    ]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info, talk_id="12345", language=localization.Language.CHS
    )

    assert rendered.filename == "talk_这里看起来很神秘呢_12345.txt"
    expected_content = (
        "# Talk Dialog\n\n" "派蒙: 这里看起来很神秘呢！\n" "旅行者: 我们小心一点。\n" "神秘声音: 欢迎来到这里..."
    )
    assert rendered.content == expected_content


def test_render_talk_long_message() -> None:
    """Test talk rendering with long first message."""
    long_message = "这是一个非常长的消息，超过了五十个字符的限制，应该被截断以创建合适的文件名。"
    talk_texts = [types.TalkText(role="NPC", message=long_message)]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info, talk_id="67890", language=localization.Language.CHS
    )

    # Should be truncated to 50 characters
    assert rendered.filename == "talk_这是一个非常长的消息超过了五十个字符的限制应该被截断以创建合适的文件名_67890.txt"
    assert "这是一个非常长的消息，超过了五十个字符的限制，应该被截断以创建合适的文件名。" in rendered.content


def test_render_talk_empty() -> None:
    """Test talk rendering with empty talk."""
    talk_info = types.TalkInfo(text=[])

    rendered = rendering.render_talk(
        talk_info, talk_id="99999", language=localization.Language.CHS
    )

    assert rendered.filename == "talk_empty_99999.txt"
    assert rendered.content == "# Talk Dialog\n"


def test_render_talk_special_characters() -> None:
    """Test talk rendering with special characters in message."""
    talk_texts = [types.TalkText(role="角色", message="「这是引号」—还有破折号！")]
    talk_info = types.TalkInfo(text=talk_texts)

    rendered = rendering.render_talk(
        talk_info, talk_id="11111", language=localization.Language.CHS
    )

    assert rendered.filename == "talk_这是引号还有破折号_11111.txt"
    assert "角色: 「这是引号」—还有破折号！" in rendered.content
