"""Test text_utils skip helpers."""

import pytest

from istaroth.agd import localization, text_utils


@pytest.mark.parametrize(
    "content", ["？？？", " ？？？ ", "", "  ", "测试", "暂缺", "N/A"]
)
def test_should_skip_readable_content_placeholders(content):
    """Empty content and dev placeholders (incl. ？？？) are skipped in any language."""
    assert text_utils.should_skip_readable_content(content, localization.Language.CHS)
    assert text_utils.should_skip_readable_content(content, localization.Language.ENG)


@pytest.mark.parametrize(
    "content", ["放假一天！", "我的宝物", "？？", "Real book text."]
)
def test_should_skip_readable_content_keeps_real_text(content):
    """Genuine (even short) readables are not dropped."""
    assert not text_utils.should_skip_readable_content(
        content, localization.Language.CHS
    )


@pytest.mark.parametrize(
    "text,skip",
    [
        ("(test)一阶段结束$HIDDEN", True),
        ("夏活beta测试任务", True),
        ("山中好长日·第一章", False),
    ],
)
def test_should_skip_text_markers(text, skip):
    """Dev/test markers (incl. the 夏活 beta chapter) skip only in CHS."""
    assert text_utils.should_skip_text(text, localization.Language.CHS) == skip
    assert not text_utils.should_skip_text(text, localization.Language.ENG)
