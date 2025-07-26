"""Data repository for loading AnimeGameData (AGD) files."""

import json
from pathlib import Path

import attrs

from istorath.agd import types


@attrs.define
class DataRepo:
    """Repository for loading AnimeGameData files."""
    
    agd_path: Path = attrs.field(converter=Path)
        
    def load_text_map(self, language: str = "CHS") -> types.TextMap:
        """Load TextMap file for specified language."""
        file_path = self.agd_path / "TextMap" / f"TextMap{language}.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.TextMap = json.load(f)
            return data
    
    def load_npc_excel_config_data(self) -> types.NpcExcelConfigData:
        """Load NPC Excel configuration data."""
        file_path = self.agd_path / "ExcelBinOutput" / "NpcExcelConfigData.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.NpcExcelConfigData = json.load(f)
            return data