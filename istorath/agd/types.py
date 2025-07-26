"""Type definitions for AnimeGameData (AGD) structures."""

from typing import TypedDict

import attrs

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


@attrs.define
class ReadableMetadata:
    """Metadata for a readable item."""
    title: str