"""Test text cleanup functionality."""

import pytest

from istaroth import text_cleanup
from istaroth.agd import localization


def test_nickname_replacement_english():
    """Test {NICKNAME} replacement in English."""
    text = "Hello {NICKNAME}, how are you?"
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Hello Traveler, how are you?"


def test_nickname_replacement_chinese():
    """Test {NICKNAME} replacement in Chinese."""
    text = "你好{NICKNAME}，你好吗？"
    result = text_cleanup.clean_text_markers(text, localization.Language.CHS)
    assert result == "你好旅行者，你好吗？"


def test_gender_selection():
    """Test {M#option1}{F#option2} replacement."""
    text = "The {M#brother}{F#sister} is here."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "The brother is here."


def test_gender_selection_chinese():
    """Test {M#option1}{F#option2} replacement in Chinese."""
    text = "{M#哥哥}{F#姐姐}来了。"
    result = text_cleanup.clean_text_markers(text, localization.Language.CHS)
    assert result == "哥哥来了。"


def test_color_markup_replacement():
    """Test <color=#RRGGBBAA>content</color> replacement."""
    text = "This is <color=#FF0000FF>red text</color> in the game."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "This is *red text* in the game."


def test_color_markup_multiple():
    """Test multiple color markups in one text."""
    text = "See <color=#FF0000FF>red</color> and <color=#00FF00FF>green</color> colors."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "See *red* and *green* colors."


def test_combined_markers():
    """Test all markers together."""
    text = (
        "Hello {NICKNAME}, the {M#king}{F#queen} says <color=#FFD700FF>welcome</color>!"
    )
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Hello Traveler, the king says *welcome*!"


def test_empty_text():
    """Test empty text handling."""
    result = text_cleanup.clean_text_markers("", localization.Language.ENG)
    assert result == ""


def test_none_text():
    """Test None text handling."""
    result = text_cleanup.clean_text_markers(None, localization.Language.ENG)
    assert result is None


def test_no_markers():
    """Test text with no markers."""
    text = "This is normal text with no special markers."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == text


def test_newline_normalization():
    """Test \\n to \n conversion."""
    text = "Line 1\\nLine 2\\nLine 3"
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Line 1\nLine 2\nLine 3"
