"""Type definitions for AnimeGameData (AGD) structures."""

from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

if TYPE_CHECKING:
    from istaroth.agd.repo import TextMapTracker, TalkTracker

import attrs

# ============================================================================
# AGD JSON File Types
# ============================================================================
# These types match the structure of JSON files from AnimeGameData

type TextMap = dict[str, str]
"""Dictionary mapping string IDs to localized text content.

Example file: TextMap/TextMapCHS.json
"""


class NpcExcelConfigDataItem(TypedDict):
    """Type definition for individual NPC configuration entries."""

    jsonName: str
    alias: str
    scriptDataPath: str
    luaDataPath: str
    dyePart: str
    billboardIcon: str
    templateEmotionPath: str
    actionIdList: list[int]
    uniqueBodyId: int
    id: int
    nameTextMapHash: int
    prefabPathHash: int
    campID: int
    lodPatternName: str


type NpcExcelConfigData = list[NpcExcelConfigDataItem]
"""List of NPC configuration items from Excel data.

Example file: ExcelBinOutput/NpcExcelConfigData.json
"""


class DialogTalkRole(TypedDict):
    """Type definition for talk role in dialog entries."""

    type: str
    id: NotRequired[str]
    _id: NotRequired[int]


class DialogExcelConfigDataItem(TypedDict):
    """Type definition for individual dialog configuration entries."""

    GFLDJMJKIKE: int
    nextDialogs: list[int]
    talkRole: DialogTalkRole
    talkContentTextMapHash: int
    talkTitleTextMapHash: int
    talkRoleNameTextMapHash: int


type DialogExcelConfigData = list[DialogExcelConfigDataItem]
"""List of dialog configuration items from Excel data.

Example file: ExcelBinOutput/DialogExcelConfigData.json
"""


class LocalizationExcelConfigDataItem(TypedDict):
    """Type definition for localization configuration entries."""

    id: int
    assetType: str
    defaultPath: str
    scPath: str
    tcPath: str
    enPath: str
    krPath: str
    jpPath: str
    esPath: str
    frPath: str
    idPath: str
    ptPath: str
    ruPath: str
    thPath: str
    viPath: str
    dePath: str
    trPath: str
    itPath: str


type LocalizationExcelConfigData = list[LocalizationExcelConfigDataItem]
"""List of localization configuration items.

Example file: ExcelBinOutput/LocalizationExcelConfigData.json
"""


class DocumentExcelConfigDataItem(TypedDict):
    """Type definition for document configuration entries."""

    id: int
    titleTextMapHash: int
    contentTextMapHash: int
    questIDList: list[int]
    showOnlyUnlocked: bool
    isDisuse: bool
    subType: str
    isImportant: bool


type DocumentExcelConfigData = list[DocumentExcelConfigDataItem]
"""List of document configuration items mapping materials to readable content.

Example file: ExcelBinOutput/DocumentExcelConfigData.json
"""


class MaterialExcelConfigDataItem(TypedDict):
    """Type definition for material configuration entries."""

    id: int
    nameTextMapHash: int
    descTextMapHash: int
    icon: str
    itemType: str
    weight: int
    rank: int
    gadgetId: int


type MaterialExcelConfigData = list[MaterialExcelConfigDataItem]
"""List of material configuration items.

Example file: ExcelBinOutput/MaterialExcelConfigData.json
"""


class TalkExcelConfigDataItem(TypedDict):
    """Type definition for talk configuration entries."""

    id: int
    initDialog: int
    questId: int
    npcId: list[int]
    activeMode: str
    beginWay: str
    heroTalk: str
    priority: int
    performCfg: str
    prePerformCfg: str
    loadType: str
    beginCond: list[dict[str, Any]]
    beginCondComb: str
    finishExec: list[dict[str, Any]]
    nextTalks: list[int]
    nextRandomTalks: list[int]


type TalkExcelConfigData = list[TalkExcelConfigDataItem]
"""List of talk configuration items.

Example file: ExcelBinOutput/TalkExcelConfigData.json
"""


class TalkRole(TypedDict):
    """Type definition for talk role."""

    type: str
    _id: NotRequired[str]
    id: NotRequired[str]


class TalkDialogItem(TypedDict):
    """Type definition for individual talk dialog entries."""

    id: int
    nextDialogs: list[int]
    talkRole: TalkRole
    talkContentTextMapHash: int
    talkAssetPath: str
    talkAssetPathAlter: str
    talkAudioName: str
    actionBefore: str
    actionWhile: str
    actionAfter: str
    optionIcon: str
    iconPath: str


class TalkData(TypedDict):
    """Talk data structure containing dialog list and metadata.

    Example file: BinOutput/Talk/Quest/7407811.json
    """

    talkId: int
    dialogList: list[TalkDialogItem]


class QuestTalkItem(TypedDict):
    """Type definition for quest talk entries."""

    id: int
    beginWay: str
    activeMode: str
    beginCond: list[dict[str, str | list[str]]]
    priority: int
    initDialog: int
    npcId: list[int]
    performCfg: str
    heroTalk: str
    questId: int
    assetIndex: int
    prePerformCfg: str


class SubQuestItem(TypedDict):
    """Type definition for sub-quest entries."""

    subId: int
    mainId: int
    order: int
    finishCond: list[dict[str, Any]]
    guide: dict[str, Any]
    guideHint: dict[str, Any]
    isRewind: bool
    versionBegin: str
    versionEnd: str


class QuestData(TypedDict):
    """Quest data structure containing talks and metadata.

    Example file: BinOutput/Quest/74078.json
    """

    id: int
    series: int
    descTextMapHash: int
    subQuests: list[SubQuestItem]
    talks: NotRequired[list[QuestTalkItem]]  # Optional field, not always present


class AvatarExcelConfigDataItem(TypedDict):
    """Type definition for avatar configuration entries."""

    id: int
    nameTextMapHash: int
    descTextMapHash: int
    iconName: str
    sideIconName: str
    qualityType: str
    chargeEfficiency: float
    combatConfigHash: int
    propGrowCurves: list[dict[str, Any]]
    prefabPathHash: int
    prefabPathRemoteHash: int
    controllerPathHash: int
    controllerPathRemoteHash: int
    LODPatternName: str


type AvatarExcelConfigData = list[AvatarExcelConfigDataItem]
"""List of avatar configuration items.

Example file: ExcelBinOutput/AvatarExcelConfigData.json
"""


class FetterStoryExcelConfigDataItem(TypedDict):
    """Type definition for fetter story configuration entries."""

    avatarId: int
    fetterId: int
    storyTitleTextMapHash: int
    storyContextTextMapHash: int
    storyTitleLockedTextMapHash: int
    isHiden: bool
    openConds: list[dict[str, Any]]
    finishConds: list[dict[str, Any]]


type FetterStoryExcelConfigData = list[FetterStoryExcelConfigDataItem]


class FettersExcelConfigDataItem(TypedDict):
    avatarId: int
    fetterId: int
    voiceTitleTextMapHash: int
    voiceFileTextTextMapHash: int


type FettersExcelConfigData = list[FettersExcelConfigDataItem]


class MainQuestExcelConfigDataItem(TypedDict):
    id: int
    titleTextMapHash: int
    descTextMapHash: int
    type: str
    showType: str


type MainQuestExcelConfigData = list[MainQuestExcelConfigDataItem]
"""List of fetter story configuration items.

Example file: ExcelBinOutput/FetterStoryExcelConfigData.json
"""


# ============================================================================
# Istaroth Internal Types
# ============================================================================
# These types are defined and used within our codebase for processed data


@attrs.define
class LocalizedRoleNames:
    """Localized names for various talk roles."""

    player: str
    black_screen: str
    unknown_npc: str
    unknown_role: str


@attrs.define
class ReadableMetadata:
    """Metadata for a readable item."""

    title: str


@attrs.define
class TalkText:
    """Individual talk dialog text."""

    role: str
    message: str


@attrs.define
class TalkInfo:
    """Talk information with dialog text."""

    text: list[TalkText]


@attrs.define
class QuestInfo:
    """Quest information with associated talk dialogs."""

    title: str
    talks: list[TalkInfo]
    non_subquest_talks: list[TalkInfo]


@attrs.define
class CharacterStory:
    """Individual character story with title and content."""

    title: str
    content: str


@attrs.define
class CharacterStoryInfo:
    """Character story information containing all stories for a character."""

    character_name: str
    stories: list[CharacterStory]


@attrs.define
class SubtitleInfo:
    """Subtitle information containing all subtitle text."""

    text_lines: list[str]


@attrs.define
class MaterialInfo:
    """Material information with name and description."""

    name: str
    description: str


@attrs.define
class VoicelineInfo:
    """Voiceline information for a character."""

    character_name: str
    voicelines: dict[str, str]  # title -> content mapping


@attrs.define
class TrackerStats:
    """Statistics for text map and talk ID access tracking."""

    accessed_text_map_ids: set[str]
    accessed_talk_ids: set[str]

    def update(self, other: "TrackerStats") -> None:
        """Update this TrackerStats with IDs from another TrackerStats."""
        self.accessed_text_map_ids.update(other.accessed_text_map_ids)
        self.accessed_talk_ids.update(other.accessed_talk_ids)

    def to_dict(
        self, text_map_tracker: "TextMapTracker", talk_tracker: "TalkTracker"
    ) -> dict[str, Any]:
        """Convert TrackerStats to dictionary format for JSON serialization."""
        return {
            "stats": {
                "text_map": {
                    "unused": len(text_map_tracker.get_unused_ids()),
                    "total": text_map_tracker.get_total_count(),
                },
                "talk_ids": {
                    "unused": len(talk_tracker.get_unused_ids()),
                    "total": talk_tracker.get_total_count(),
                },
            },
            "unused_ids": {
                "text_map": sorted(text_map_tracker.get_unused_ids()),
                "talk_ids": sorted(talk_tracker.get_unused_ids()),
            },
        }


@attrs.define
class RenderedItem:
    """Rendered content suitable for RAG training."""

    filename: str
    content: str
