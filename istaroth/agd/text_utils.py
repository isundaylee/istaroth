from istaroth.agd import localization

# Dev placeholders that some readables carry instead of real text, matched exactly
# (case-insensitively). The same junk appears per language: CHS 测试/暂无/暂缺 and
# their ENG equivalents Test/None/N/A, plus the language-neutral ？？？. Matched
# whole-string so genuinely short readables (e.g. "放假一天！", "我的宝物") are not
# dropped.
_READABLE_PLACEHOLDER_CONTENTS = frozenset(
    {"测试", "暂无", "暂缺", "？？？", "test", "none", "n/a"}
)


def should_skip_text(text: str, language: localization.Language) -> bool:
    """Skip test items only for CHS language."""
    if language != localization.Language.CHS:
        return False
    lower_text = text.lower()
    return (
        lower_text.startswith(("test", "(test", "（test"))
        or "$hidden" in lower_text
        or "$unreleased" in lower_text
    )


def should_skip_readable_content(content: str, language: localization.Language) -> bool:
    """Whether a readable's content is empty or a dev placeholder (nothing to render)."""
    stripped = content.strip()
    return (
        not stripped
        or stripped.casefold() in _READABLE_PLACEHOLDER_CONTENTS
        or should_skip_text(stripped, language)
    )
