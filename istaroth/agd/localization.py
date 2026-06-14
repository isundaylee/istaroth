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
            mate_avatar="旅行者血亲",
            black_screen="黑屏文本",
            narration="旁白",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
        Language.ENG: types.LocalizedRoleNames(
            player="Traveler",
            mate_avatar="Traveler's Sibling",
            black_screen="Black Screen Text",
            narration="Narration",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
    }
    return role_names[language]
