"""Type definitions for AnimeGameData (AGD) structures."""

from typing import TypedDict

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


class TalkRole(TypedDict):
    """Type definition for talk role."""

    type: str
    _id: str


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


class QuestData(TypedDict):
    """Quest data structure containing talks and metadata.

    Example file: BinOutput/Quest/74078.json
    """

    id: int
    series: int
    descTextMapHash: int
    talks: list[QuestTalkItem]


# ============================================================================
# Istorath Internal Types
# ============================================================================
# These types are defined and used within our codebase for processed data


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

    talks: list[TalkInfo]


@attrs.define
class RenderedItem:
    """Rendered content suitable for RAG training."""

    filename: str
    content: str
