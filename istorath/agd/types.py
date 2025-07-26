"""Type definitions for AnimeGameData (AGD) structures."""

from typing import TypedDict

# TextMap is simply a dictionary mapping string IDs to string values
type TextMap = dict[str, str]


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


# NpcExcelConfigData is a list of NPC configuration items
type NpcExcelConfigData = list[NpcExcelConfigDataItem]