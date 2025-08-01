"""Localization utilities for AGD content."""

from enum import Enum

from istaroth.agd import types


class Language(Enum):
    """Supported languages for AGD content."""

    CHS = "CHS"
    ENG = "ENG"


def get_localized_role_names(language: Language) -> types.LocalizedRoleNames:
    """Get localized role names based on language."""
    role_names = {
        Language.CHS: types.LocalizedRoleNames(
            player="旅行者",
            black_screen="黑屏文本",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
        Language.ENG: types.LocalizedRoleNames(
            player="Traveler",
            black_screen="Black Screen Text",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
    }
    return role_names[language]
