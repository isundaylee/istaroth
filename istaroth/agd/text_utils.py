from istaroth.agd import localization


def should_skip_text(text: str, language: localization.Language) -> bool:
    """Skip test items only for CHS language."""
    if language != localization.Language.CHS:
        return False
    lower_title = text.lower()
    return (
        lower_title.startswith(("test", "(test", "（test"))
        or "$hidden" in lower_title
        or "$unreleased" in lower_title
    )
