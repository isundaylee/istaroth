"""Localization utilities for AGD content."""

from enum import Enum

from istaroth.agd import processed_types
from istaroth.text import types as text_types


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


_QUEST_TYPE_LABELS: dict[str, dict[Language, str]] = {
    "AQ": {Language.CHS: "魔神任务", Language.ENG: "Archon Quests"},
    "LQ": {Language.CHS: "传说任务", Language.ENG: "Story Quests"},
    "WQ": {Language.CHS: "世界任务", Language.ENG: "World Quests"},
    "EQ": {Language.CHS: "活动任务", Language.ENG: "Event Quests"},
    "IQ": {Language.CHS: "每日委托", Language.ENG: "Daily Commissions"},
}
_STANDALONE_QUEST_LABEL: dict[Language, str] = {
    Language.CHS: "独立任务",
    Language.ENG: "Standalone Quests",
}
_CATEGORY_LABELS: dict[text_types.TextCategory, dict[Language, str]] = {
    text_types.TextCategory.AGD_QUEST: {Language.CHS: "任务", Language.ENG: "Quests"},
    text_types.TextCategory.AGD_COOP: {
        Language.CHS: "邀约事件",
        Language.ENG: "Hangout Events",
    },
    text_types.TextCategory.AGD_READABLE: {
        Language.CHS: "可读文本",
        Language.ENG: "Readables",
    },
    text_types.TextCategory.AGD_BOOK: {Language.CHS: "书籍", Language.ENG: "Books"},
    text_types.TextCategory.AGD_WEAPON: {Language.CHS: "武器", Language.ENG: "Weapons"},
    text_types.TextCategory.AGD_WINGS: {Language.CHS: "风之翼", Language.ENG: "Wings"},
    text_types.TextCategory.AGD_COSTUME: {
        Language.CHS: "服装",
        Language.ENG: "Costumes",
    },
    text_types.TextCategory.AGD_CHARACTER_STORY: {
        Language.CHS: "角色故事",
        Language.ENG: "Character Stories",
    },
    text_types.TextCategory.AGD_SUBTITLE: {
        Language.CHS: "字幕",
        Language.ENG: "Subtitles",
    },
    text_types.TextCategory.AGD_MATERIAL_TYPE: {
        Language.CHS: "材料类型",
        Language.ENG: "Material Types",
    },
    text_types.TextCategory.AGD_ACHIEVEMENT: {
        Language.CHS: "成就",
        Language.ENG: "Achievements",
    },
    text_types.TextCategory.AGD_VOICELINE: {
        Language.CHS: "语音台词",
        Language.ENG: "Voicelines",
    },
    text_types.TextCategory.AGD_TALK_GROUP: {
        Language.CHS: "对话组",
        Language.ENG: "Talk Groups",
    },
    text_types.TextCategory.AGD_TALK: {Language.CHS: "对话", Language.ENG: "Talks"},
    text_types.TextCategory.AGD_ARTIFACT_SET: {
        Language.CHS: "圣遗物套装",
        Language.ENG: "Artifact Sets",
    },
    text_types.TextCategory.AGD_CREATURE: {
        Language.CHS: "生物志",
        Language.ENG: "Living Beings",
    },
    text_types.TextCategory.TPS_SHISHU: {
        Language.CHS: "诗漱原神世界观手册",
        Language.ENG: "Shishu Lore Manual",
    },
}


def get_quest_type_label(quest_type: str, *, language: Language) -> str:
    return _QUEST_TYPE_LABELS[quest_type][language]


def get_standalone_quest_label(*, language: Language) -> str:
    return _STANDALONE_QUEST_LABEL[language]


def get_category_label(category: text_types.TextCategory, *, language: Language) -> str:
    return _CATEGORY_LABELS[category][language]


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
