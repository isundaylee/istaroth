"""Type definitions for AnimeGameData (AGD) structures."""

from typing import TypedDict

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