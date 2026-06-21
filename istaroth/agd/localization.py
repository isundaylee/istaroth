"""Localization utilities for AGD content."""

from enum import Enum

from istaroth.agd import processed_types


class Language(Enum):
    """Supported languages for AGD content."""

    CHS = "CHS"
    ENG = "ENG"


# Living-beings archive groups. The in-game archive labels are not linked to the
# codex ``type``/``subType`` enums in any data table, so the bilingual display
# names are mapped here. Missing on purpose raises so a new codex group surfaces.
_CREATURE_TYPE_LABELS: dict[str, dict[Language, str]] = {
    "CODEX_MONSTER": {Language.CHS: "魔物", Language.ENG: "Monsters"},
    "CODEX_ANIMAL": {Language.CHS: "野生生物", Language.ENG: "Wildlife"},
}
_CREATURE_SUBTYPE_LABELS: dict[str, dict[Language, str]] = {
    "CODEX_SUBTYPE_ELEMENTAL": {
        Language.CHS: "元素生命",
        Language.ENG: "Elemental Lifeforms",
    },
    "CODEX_SUBTYPE_HILICHURL": {Language.CHS: "丘丘部族", Language.ENG: "Hilichurls"},
    "CODEX_SUBTYPE_ABYSS": {Language.CHS: "深渊", Language.ENG: "The Abyss"},
    "CODEX_SUBTYPE_FATUI": {Language.CHS: "愚人众", Language.ENG: "Fatui"},
    "CODEX_SUBTYPE_AUTOMATRON": {Language.CHS: "自律机关", Language.ENG: "Automatons"},
    "CODEX_SUBTYPE_HUMAN": {Language.CHS: "人类势力", Language.ENG: "Human Factions"},
    "CODEX_SUBTYPE_BEAST": {Language.CHS: "异种魔兽", Language.ENG: "Mystical Beasts"},
    "CODEX_SUBTYPE_BOSS": {Language.CHS: "首领", Language.ENG: "Bosses"},
    "CODEX_SUBTYPE_ANIMAL": {Language.CHS: "走兽", Language.ENG: "Beasts"},
    "CODEX_SUBTYPE_AVIARY": {Language.CHS: "飞禽", Language.ENG: "Avian Kind"},
    "CODEX_SUBTYPE_FISH": {Language.CHS: "鱼类", Language.ENG: "Fish"},
    "CODEX_SUBTYPE_CRITTER": {Language.CHS: "小型生物", Language.ENG: "Critters"},
}


def get_creature_type_label(codex_type: str, *, language: Language) -> str:
    """Localized display name for a codex ``type`` (raises on an unknown type)."""
    return _CREATURE_TYPE_LABELS[codex_type][language]


def get_creature_subtype_label(codex_subtype: str, *, language: Language) -> str:
    """Localized display name for a codex ``subType`` (raises on an unknown subtype)."""
    return _CREATURE_SUBTYPE_LABELS[codex_subtype][language]


def get_localized_role_names(language: Language) -> processed_types.LocalizedRoleNames:
    """Get localized role names based on language."""
    role_names = {
        Language.CHS: processed_types.LocalizedRoleNames(
            player="旅行者",
            mate_avatar="旅行者血亲",
            black_screen="黑屏文本",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
        Language.ENG: processed_types.LocalizedRoleNames(
            player="Traveler",
            mate_avatar="Traveler's Sibling",
            black_screen="Black Screen Text",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
    }
    return role_names[language]
