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


_PRONOUNS = {"INFO_MALE_PRONOUN_HE": "He", "INFO_FEMALE_PRONOUN_SISTER": "Sister"}


def test_sexpro_renders_first_branch_via_pronoun_map():
    """{...#SEXPRO[male|female]} renders the first (male-player) branch's mapped text."""
    text = "The Traveler says {PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_HE|INFO_FEMALE_PRONOUN_SHE]} is here."
    assert (
        text_cleanup.clean_text_markers(
            text, localization.Language.ENG, pronoun_map=_PRONOUNS
        )
        == "The Traveler says He is here."
    )


def test_sexpro_uses_first_branch_regardless_of_token_gender_prefix():
    """The positional first token wins even when its prefix looks female."""
    text = "Find your {PLAYERAVATAR#SEXPRO[INFO_FEMALE_PRONOUN_SISTER|INFO_MALE_PRONOUN_BROTHER]}."
    assert (
        text_cleanup.clean_text_markers(
            text, localization.Language.ENG, pronoun_map=_PRONOUNS
        )
        == "Find your Sister."
    )


def test_sexpro_mateavatar_variant():
    """The sibling {MATEAVATAR#SEXPRO[...]} variant is handled like PLAYERAVATAR."""
    text = "I am looking for my {MATEAVATAR#SEXPRO[INFO_FEMALE_PRONOUN_SISTER|INFO_MALE_PRONOUN_BROTHER]}."
    assert (
        text_cleanup.clean_text_markers(
            text, localization.Language.ENG, pronoun_map=_PRONOUNS
        )
        == "I am looking for my Sister."
    )


def test_sexpro_unmapped_token_raises():
    """An unmapped SEXPRO token surfaces instead of leaking raw syntax."""
    text = "{PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_NOPE|INFO_FEMALE_PRONOUN_NOPE]}"
    with pytest.raises(KeyError):
        text_cleanup.clean_text_markers(
            text, localization.Language.ENG, pronoun_map=_PRONOUNS
        )


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
