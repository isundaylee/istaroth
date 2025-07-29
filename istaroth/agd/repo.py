"""Data repository for loading AnimeGameData (AGD) files."""

import functools
import json
import os
import pathlib

import attrs

from istaroth.agd import types


class TextMapTracker:
    """Wrapper around TextMap that tracks which text IDs have been accessed."""

    def __init__(self, text_map: types.TextMap) -> None:
        self._text_map = text_map
        self._accessed_ids: set[str] = set()

    def __getitem__(self, key: str) -> str:
        """Get text by ID and track access."""
        self._accessed_ids.add(key)
        return self._text_map[key]

    def __contains__(self, key: str) -> bool:
        """Check if key exists without tracking access."""
        return key in self._text_map

    def get(self, key: str, default: str) -> str:
        """Get text by ID with default, tracks access if key exists."""
        if key in self._text_map:
            self._accessed_ids.add(key)
            return self._text_map[key].replace("\\n", "\n")
        return default

    def get_optional(self, key: str) -> str | None:
        """Get text by ID, returns None if not found."""
        if key in self._text_map:
            self._accessed_ids.add(key)
            return self._text_map[key]
        return None

    def get_unused_entries(self) -> dict[str, str]:
        """Return dictionary of unused text map entries."""
        return {
            text_id: content
            for text_id, content in self._text_map.items()
            if text_id not in self._accessed_ids
        }


@attrs.frozen
class DataRepo:
    """Repository for loading AnimeGameData files."""

    agd_path: pathlib.Path = attrs.field(converter=pathlib.Path)
    language: str = attrs.field(default="CHS")

    @property
    def language_short(self) -> str:
        """Get the short language code used in AGD file structure (maps ENG to EN)."""
        return "EN" if self.language == "ENG" else self.language

    @classmethod
    def from_env(cls) -> "DataRepo":
        """Create DataRepo from environment variables.

        Reads AGD_PATH for data location and AGD_LANGUAGE for language (defaults to CHS).
        """
        agd_path = os.environ.get("AGD_PATH")
        if not agd_path:
            raise ValueError("AGD_PATH environment variable not set")
        language = os.environ.get("AGD_LANGUAGE", "CHS")
        return cls(agd_path, language=language)

    @functools.lru_cache(maxsize=None)
    def load_text_map(self) -> TextMapTracker:
        """Load TextMap file for the instance's language."""
        file_path = self.agd_path / "TextMap" / f"TextMap{self.language_short}.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.TextMap = json.load(f)
            return TextMapTracker(data)

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

    @functools.lru_cache(maxsize=None)
    def load_avatar_excel_config_data(self) -> types.AvatarExcelConfigData:
        """Load avatar Excel configuration data."""
        file_path = self.agd_path / "ExcelBinOutput" / "AvatarExcelConfigData.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.AvatarExcelConfigData = json.load(f)
            return data

    @functools.lru_cache(maxsize=None)
    def load_fetter_story_excel_config_data(self) -> types.FetterStoryExcelConfigData:
        """Load fetter story Excel configuration data."""
        file_path = self.agd_path / "ExcelBinOutput" / "FetterStoryExcelConfigData.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.FetterStoryExcelConfigData = json.load(f)
            return data
