"""Localization utilities used by text readers."""

from enum import Enum

from istaroth.text import types as text_types


class Language(Enum):
    """Supported corpus languages."""

    CHS = "CHS"
    ENG = "ENG"


_CATEGORY_LABELS: dict[text_types.TextCategory, dict[Language, str]] = {
    text_types.TextCategory.AGD_QUEST: {Language.CHS: "任务", Language.ENG: "Quests"},
    text_types.TextCategory.AGD_HANGOUT: {
        Language.CHS: "邀约事件",
        Language.ENG: "Hangout Events",
    },
    text_types.TextCategory.AGD_ANECDOTE: {
        Language.CHS: "轶闻",
        Language.ENG: "Anecdotes",
    },
    text_types.TextCategory.AGD_BLOSSOM: {
        Language.CHS: "矿物富集点",
        Language.ENG: "Rich Ore Reserves",
    },
    text_types.TextCategory.AGD_ACTIVITY: {
        Language.CHS: "活动",
        Language.ENG: "Events",
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


def get_category_label(category: text_types.TextCategory, *, language: Language) -> str:
    return _CATEGORY_LABELS[category][language]
