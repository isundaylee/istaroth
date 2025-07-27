"""Tests for AGD rendering functionality."""

from istorath.agd import rendering, types


def test_render_readable_basic() -> None:
    """Test basic readable rendering functionality."""
    content = "This is some readable content.\nWith multiple lines."
    metadata = types.ReadableMetadata(title="Test Book Title")

    rendered = rendering.render_readable(content, metadata)

    assert rendered.filename == "readable_Test_Book_Title.txt"
    assert (
        rendered.content
        == "# Test Book Title\n\nThis is some readable content.\nWith multiple lines."
    )


def test_render_readable_special_characters() -> None:
    """Test readable rendering with special characters in title."""
    content = "Content here."
    metadata = types.ReadableMetadata(title="神霄折戟录·第六卷")

    rendered = rendering.render_readable(content, metadata)

    assert rendered.filename == "readable_神霄折戟录第六卷.txt"
    assert rendered.content == "# 神霄折戟录·第六卷\n\nContent here."


def test_render_readable_whitespace() -> None:
    """Test readable rendering with excessive whitespace in title."""
    content = "Some content."
    metadata = types.ReadableMetadata(title="  Title   With   Spaces  ")

    rendered = rendering.render_readable(content, metadata)

    assert rendered.filename == "readable_Title_With_Spaces.txt"
    assert rendered.content == "#   Title   With   Spaces  \n\nSome content."
