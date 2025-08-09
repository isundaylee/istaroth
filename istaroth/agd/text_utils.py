from istaroth.agd import localization


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
