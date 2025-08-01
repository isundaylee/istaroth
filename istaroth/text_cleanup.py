"""Text cleanup utilities for processing game text markers."""

import re

from istaroth.agd import localization


def clean_text_markers(text: str, language: localization.Language) -> str:
    """Clean game text markers and normalize newlines."""
    if not text:
        return text

    # Get localized names for nickname replacement
    localized_names = localization.get_localized_role_names(language)

    # Replace escape sequences
    text = text.replace("\\n", "\n")

    # Replace {NICKNAME} with appropriate traveler name
    text = re.sub(r"\{NICKNAME\}", localized_names.player, text)

    # Replace {M#option1}{F#option2} with M option
    text = re.sub(r"\{M#([^}]+)\}\{F#[^}]+\}", r"\1", text)

    # Replace <color=#RRGGBBAA>content</color> with markdown emphasis
    text = re.sub(r"<color=#[0-9A-Fa-f]{8}>([^<]*)</color>", r"*\1*", text)

    return text
