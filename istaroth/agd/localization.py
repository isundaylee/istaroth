"""Localization utilities for AGD content."""

from istaroth.agd import types


def get_localized_role_names(language: str) -> types.LocalizedRoleNames:
    """Get localized role names based on language."""
    role_names = {
        "CHS": types.LocalizedRoleNames(
            player="旅行者",
            black_screen="黑屏文本",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
        "ENG": types.LocalizedRoleNames(
            player="Traveler",
            black_screen="Black Screen Text",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
    }
    # Default to English for unsupported languages
    return role_names.get(language, role_names["ENG"])
