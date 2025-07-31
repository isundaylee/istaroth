"""Data repository for loading AnimeGameData (AGD) files."""

from __future__ import annotations

import functools
import json
import os
import pathlib

import attrs

from istaroth.agd import types


class IdTracker:
    """Base class for tracking which IDs have been accessed."""

    def __init__(self, all_ids: set[str]) -> None:
        self._all_ids = all_ids
        self._accessed_ids: set[str] = set()
        self._context_depth: int = 0

    def _track_access(self, key: str) -> None:
        """Track that an ID has been accessed."""
        self._accessed_ids.add(key)

    def get_accessed_ids(self) -> set[str]:
        """Return set of accessed IDs."""
        return self._accessed_ids.copy()

    def get_unused_ids(self) -> set[str]:
        """Return set of unused IDs."""
        return self._all_ids - self._accessed_ids

    def get_total_count(self) -> int:
        """Return total count of all IDs."""
        return len(self._all_ids)

    def format_unused_stats(self) -> str:
        """Format unused statistics as 'unused / total (percentage%)'."""
        unused_count = len(self.get_unused_ids())
        total_count = self.get_total_count()
        percentage = (unused_count / total_count * 100) if total_count > 0 else 0.0
        return f"{unused_count} / {total_count} ({percentage:.1f}%)"

    def _reset_stats(self) -> None:
        """Reset access tracking statistics."""
        self._accessed_ids.clear()

    def __enter__(self):
        """Context manager entry - reset stats only on first entry."""
        if self._context_depth == 0:
            self._reset_stats()
        self._context_depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ARG002
        """Context manager exit - decrement depth counter."""
        self._context_depth -= 1


class MaterialTracker(IdTracker):
    """Tracks which material IDs have been accessed."""

    def __init__(self, material_data: types.MaterialExcelConfigData) -> None:
        self._material_dict = {
            str(material["id"]): material for material in material_data
        }
        super().__init__(set(self._material_dict.keys()))

    def get(self, material_id_str: str) -> types.MaterialExcelConfigDataItem | None:
        """Get material data by ID and track access."""
        if material_id_str in self._material_dict:
            self._track_access(material_id_str)
            return self._material_dict[material_id_str]
        return None

    def get_all(self) -> types.MaterialExcelConfigData:
        """Get all material data without tracking (for discovery purposes)."""
        return list(self._material_dict.values())


class TextMapTracker(IdTracker):
    """Wrapper around TextMap that tracks which text IDs have been accessed."""

    def __init__(self, text_map: types.TextMap) -> None:
        super().__init__(set(text_map.keys()))
        self._text_map = text_map

    def get(self, key: str, default: str) -> str:
        """Get text by ID with default, tracks access if key exists."""
        if key in self._text_map:
            self._track_access(key)
            return self._text_map[key].replace("\\n", "\n")
        return default

    def get_optional(self, key: str) -> str | None:
        """Get text by ID, returns None if not found."""
        if key in self._text_map:
            self._track_access(key)
            return self._text_map[key]
        return None


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
    def load_material_excel_config_data(self) -> MaterialTracker:
        """Load material Excel configuration data as MaterialTracker."""
        file_path = self.agd_path / "ExcelBinOutput" / "MaterialExcelConfigData.json"
        with open(file_path, encoding="utf-8") as f:
            data: types.MaterialExcelConfigData = json.load(f)
            return MaterialTracker(data)

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
