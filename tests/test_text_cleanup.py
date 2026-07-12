"""Test text cleanup functionality."""

import pytest

from istaroth import text_cleanup
from istaroth.agd import localization


@pytest.mark.parametrize(
    "language,text,expected",
    [
        # {NICKNAME} replacement per language.
        (
            localization.Language.ENG,
            "Hello {NICKNAME}, how are you?",
            "Hello Traveler, how are you?",
        ),
        (localization.Language.CHS, "你好{NICKNAME}，你好吗？", "你好旅行者，你好吗？"),
        # {M#option1}{F#option2} keeps the male-player branch in any language.
        (
            localization.Language.ENG,
            "The {M#brother}{F#sister} is here.",
            "The brother is here.",
        ),
        (localization.Language.CHS, "{M#哥哥}{F#姐姐}来了。", "哥哥来了。"),
    ],
)
def test_nickname_and_gender_markers(language, text, expected):
    assert text_cleanup.clean_text_markers(text, language) == expected


_PRONOUNS = {"INFO_MALE_PRONOUN_HE": "He", "INFO_FEMALE_PRONOUN_SISTER": "Sister"}


def test_sexpro_renders_first_branch():
    """{...#SEXPRO[male|female]} renders the first (male-player) branch's text."""
    text = "The Traveler says {PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_HE|INFO_FEMALE_PRONOUN_SHE]} is here."
    result = text_cleanup.resolve_sexpro(text, _PRONOUNS.__getitem__)
    assert result == "The Traveler says He is here."


def test_sexpro_uses_first_branch_regardless_of_token_gender_prefix():
    """The positional first token wins even when its prefix looks female."""
    text = "Find your {PLAYERAVATAR#SEXPRO[INFO_FEMALE_PRONOUN_SISTER|INFO_MALE_PRONOUN_BROTHER]}."
    result = text_cleanup.resolve_sexpro(text, _PRONOUNS.__getitem__)
    assert result == "Find your Sister."


def test_sexpro_mateavatar_variant():
    """The sibling {MATEAVATAR#SEXPRO[...]} variant is handled like PLAYERAVATAR."""
    text = "I am looking for my {MATEAVATAR#SEXPRO[INFO_FEMALE_PRONOUN_SISTER|INFO_MALE_PRONOUN_BROTHER]}."
    result = text_cleanup.resolve_sexpro(text, _PRONOUNS.__getitem__)
    assert result == "I am looking for my Sister."


def test_sexpro_unmapped_token_raises():
    """An unmapped SEXPRO token surfaces instead of leaking raw syntax."""
    text = "{PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_NOPE|INFO_FEMALE_PRONOUN_NOPE]}"
    with pytest.raises(KeyError):
        text_cleanup.resolve_sexpro(text, _PRONOUNS.__getitem__)


def test_color_markup_replacement():
    """Test <color=#RRGGBBAA>content</color> replacement."""
    text = "This is <color=#FF0000FF>red text</color> in the game."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "This is *red text* in the game."


def test_color_markup_short_hex():
    """Test <color=#RRGGBB> (6-digit, no alpha) replacement."""
    text = "This is <color=#37FFFF>cyan text</color> in the game."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "This is *cyan text* in the game."


def test_italic_markup_replacement():
    """Test <i>content</i> replacement, case-insensitively."""
    text = "This is <i>italic</i> and <I>also italic</I>."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "This is *italic* and *also italic*."


def test_italic_nested_in_color():
    """<i> nested inside <color> resolves fully rather than leaking raw tags."""
    text = "<color=#37FFFFFF><I>emphasized</I></color>"
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "**emphasized**"


def test_center_and_right_stripped():
    """<center>/<right> structural wrappers are stripped, content kept."""
    text = "<center>Centered line</center>\n<right>Signed</right>"
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Centered line\nSigned"


def test_center_spans_multiple_lines():
    """<center> can wrap multiple paragraphs, not just a single line."""
    text = "<center>Line one\n\nLine two</center>"
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Line one\n\nLine two"


def test_image_placeholder_dropped():
    """Standalone <image name=.../> lines are removed entirely."""
    text = "Before.\n<image name=UI_Example />\nAfter."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Before.\nAfter."


def test_combined_markers():
    """Test all markers together."""
    text = (
        "Hello {NICKNAME}, the {M#king}{F#queen} says <color=#FFD700FF>welcome</color>!"
    )
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Hello Traveler, the king says *welcome*!"


def test_newline_normalization():
    """Test \\n to \n conversion."""
    text = "Line 1\\nLine 2\\nLine 3"
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Line 1\nLine 2\nLine 3"


def test_realname_speaker_label():
    """#{REALNAME[...]}: speaker prefix resolves to the character name."""
    text = "#{REALNAME[ID(1)|HOSTONLY(true)]}: The text after the colon."
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Wanderer: The text after the colon."


def test_realname_speaker_label_chinese():
    """#{REALNAME[...]}: speaker prefix resolves in Chinese."""
    text = "#{REALNAME[ID(1)|HOSTONLY(true)]}: 在经历那么多次徒劳之后，你应该明白吧？"
    result = text_cleanup.clean_text_markers(text, localization.Language.CHS)
    assert result == "流浪者: 在经历那么多次徒劳之后，你应该明白吧？"


def test_realname_inline():
    """#{REALNAME[...]} inline resolves to the character name."""
    text = "#{REALNAME[ID(2)|SHOWHOST(true)]}摆出了进攻的架势！"
    result = text_cleanup.clean_text_markers(text, localization.Language.CHS)
    assert result == "小龙摆出了进攻的架势！"


def test_realname_standalone():
    """Bare #{REALNAME[...]} used as a speaker name resolves to the name."""
    text = "#{REALNAME[ID(2)|SHOWHOST(true)]}"
    result = text_cleanup.clean_text_markers(text, localization.Language.ENG)
    assert result == "Little One"


def test_realname_unmapped_id_raises():
    """An unmapped ID(n) raises so future additions don't silently leak."""
    text = "#{REALNAME[ID(99)|HOSTONLY(true)]}: something"
    with pytest.raises(KeyError):
        text_cleanup.clean_text_markers(text, localization.Language.ENG)
