"""Data repository for loading AnimeGameData (AGD) files."""

import functools
import json
import os
import pathlib

import attrs

from istorath.agd import types


@attrs.frozen
class DataRepo:
    """Repository for loading AnimeGameData files."""

    agd_path: pathlib.Path = attrs.field(converter=pathlib.Path)

    @classmethod
    def from_env(cls) -> "DataRepo":
        """Create DataRepo from AGD_PATH environment variable."""
        agd_path = os.environ.get("AGD_PATH")
        if not agd_path:
            raise ValueError("AGD_PATH environment variable not set")
        return cls(agd_path)

    @functools.lru_cache(maxsize=None)
    def load_text_map(self, language: str = "CHS") -> types.TextMap:
        """Load TextMap file for specified language."""
        file_path = self.agd_path / "TextMap" / f"TextMap{language}.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.TextMap = json.load(f)
            return data

    @functools.lru_cache(maxsize=None)
    def load_npc_excel_config_data(self) -> types.NpcExcelConfigData:
        """Load NPC Excel configuration data."""
        file_path = self.agd_path / "ExcelBinOutput" / "NpcExcelConfigData.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.NpcExcelConfigData = json.load(f)
            return data

    @functools.lru_cache(maxsize=None)
    def load_localization_excel_config_data(self) -> types.LocalizationExcelConfigData:
        """Load localization Excel configuration data."""
        file_path = (
            self.agd_path / "ExcelBinOutput" / "LocalizationExcelConfigData.json"
        )
        with open(file_path, encoding="utf-8") as f:
            data: types.LocalizationExcelConfigData = json.load(f)
            return data

    @functools.lru_cache(maxsize=None)
    def load_document_excel_config_data(self) -> types.DocumentExcelConfigData:
        """Load document Excel configuration data."""
        file_path = self.agd_path / "ExcelBinOutput" / "DocumentExcelConfigData.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.DocumentExcelConfigData = json.load(f)
            return data

    @functools.lru_cache(maxsize=None)
    def load_material_excel_config_data(self) -> types.MaterialExcelConfigData:
        """Load material Excel configuration data."""
        file_path = self.agd_path / "ExcelBinOutput" / "MaterialExcelConfigData.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.MaterialExcelConfigData = json.load(f)
            return data

    @functools.lru_cache(maxsize=None)
    def load_talk_data(self, talk_file: str) -> types.TalkData:
        """Load talk data from specified talk file."""
        file_path = self.agd_path / talk_file
        with open(file_path, encoding="utf-8") as f:
            data: types.TalkData = json.load(f)
            return data

    @functools.lru_cache(maxsize=None)
    def load_quest_data(self, quest_file: str) -> types.QuestData:
        """Load quest data from specified quest file."""
        file_path = self.agd_path / quest_file
        with open(file_path, encoding="utf-8") as f:
            data: types.QuestData = json.load(f)
            return data
