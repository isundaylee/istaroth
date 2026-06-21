"""Data repository for loading AnimeGameData (AGD) files."""

from __future__ import annotations

import functools
import itertools
import json
import logging
import os
import pathlib
import subprocess
from typing import Any, Callable, Generic, Iterable, TypeVar, cast

import attrs
from numpy import isin

from istaroth import text_cleanup
from istaroth.agd import (
    coop_graph,
    deobfuscation,
    localization,
    talk_parsing,
    types,
)

logger = logging.getLogger(__name__)

_K = TypeVar("_K")
_T = TypeVar("_T")
# Ordered newest-to-oldest; earlier refs win when multiple fallbacks contain a hash.
_TEXT_MAP_FALLBACK_REFS: tuple[str, ...] = ("8c3aecbd6ed",)


class IdTracker(Generic[_K]):
    """Base class for tracking which IDs have been accessed.

    Generic over the id type ``_K``: readable filenames are ``str``, while
    text-map hashes, talk, and material ids are ``int`` (their wire type).
    """

    def __init__(self, all_ids: set[_K]) -> None:
        self._all_ids = all_ids
        self._accessed_ids: set[_K] = set()
        self._context_depth: int = 0

    def _track_access(self, key: _K) -> None:
        """Track that an ID has been accessed."""
        self._accessed_ids.add(key)

    def get_all_ids(self) -> set[_K]:
        return self._all_ids.copy()

    def has(self, key: _K) -> bool:
        """Whether key is a known ID, without tracking access."""
        return key in self._all_ids

    def get_accessed_ids(self) -> set[_K]:
        """Return set of accessed IDs."""
        return self._accessed_ids.copy()

    def get_unused_ids(self) -> set[_K]:
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

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - decrement depth counter."""
        self._context_depth -= 1


class MaterialTracker(IdTracker[types.MaterialId]):
    """Tracks which material IDs have been accessed."""

    def __init__(self, material_data: types.MaterialExcelConfigData) -> None:
        self._material_dict: dict[
            types.MaterialId, types.MaterialExcelConfigDataItem
        ] = {material["id"]: material for material in material_data}
        super().__init__(set(self._material_dict.keys()))

    def get(
        self, material_id: types.MaterialId
    ) -> types.MaterialExcelConfigDataItem | None:
        """Get material data by ID and track access."""
        if material_id in self._material_dict:
            self._track_access(material_id)
            return self._material_dict[material_id]
        return None

    def get_all(self) -> types.MaterialExcelConfigData:
        """Get all material data without tracking (for discovery purposes)."""
        return list(self._material_dict.values())


class TalkTracker(IdTracker[types.TalkId]):
    """Tracks which talk IDs have been accessed."""

    def __init__(
        self,
        talk_excel_data: types.TalkExcelConfigData,
        talk_file_mapping: dict[types.TalkId, str],
    ) -> None:
        self._talk_dict: dict[types.TalkId, types.TalkExcelConfigDataItem] = {
            talk["id"]: talk for talk in talk_excel_data
        }
        self._talk_file_mapping = talk_file_mapping
        super().__init__(set(self._talk_dict.keys()))

    def get(self, talk_id: types.TalkId) -> types.TalkExcelConfigDataItem | None:
        """Get talk configuration data by ID and track access."""
        if talk_id in self._talk_dict:
            self._track_access(talk_id)
            return self._talk_dict[talk_id]
        return None

    def get_all(self) -> types.TalkExcelConfigData:
        """Get all talk configuration data without tracking (for discovery purposes)."""
        return list(self._talk_dict.values())

    def get_talk_file_path(self, talk_id: types.TalkId) -> str | None:
        """Get the file path for a talk ID and track access."""
        talk_item = self.get(talk_id)
        if talk_item is None:
            return None

        # Look up the file path in the pre-built mapping
        return self._talk_file_mapping.get(talk_id)


class TextMapTracker(IdTracker[types.TextMapHash]):
    """Wrapper around TextMap that tracks which text IDs have been accessed.

    ``TextMap`` ships with ``str`` keys (JSON object keys are always strings);
    they are int-keyed once here so lookups carry a ``TextMapHash`` directly.
    """

    def __init__(
        self,
        text_map: types.TextMap,
        language: localization.Language,
        fallback_text_map: types.TextMap | None = None,
    ) -> None:
        self._text_map: dict[types.TextMapHash, str] = {
            int(k): v for k, v in text_map.items()
        }
        self._fallback_text_map = self._normalize_text_map(fallback_text_map or {})
        self._text_maps = (self._text_map, self._fallback_text_map)
        super().__init__(set(self._text_map))
        self._language = language

    @staticmethod
    def _normalize_text_map(text_map: types.TextMap) -> dict[types.TextMapHash, str]:
        return {int(k): v for k, v in text_map.items()}

    def has(self, key: types.TextMapHash) -> bool:
        """Whether key resolves in the current or fallback TextMap."""
        return self._get_raw_text(key) is not None

    def _get_cleaned_text(self, text: str) -> str:
        return text_cleanup.clean_text_markers(text, self._language)

    def _get_raw_text(self, key: types.TextMapHash) -> str | None:
        for text_map in self._text_maps:
            if (text := text_map.get(key)) is not None:
                return text
        return None

    def get(self, key: types.TextMapHash, default: str) -> str:
        """Get text by ID with default, tracks access if key exists."""
        if (text := self._get_raw_text(key)) is not None:
            self._track_access(key)
            return self._get_cleaned_text(text)
        return default

    def get_optional(self, key: types.TextMapHash) -> str | None:
        """Get text by ID, returns None if not found."""
        if (text := self._get_raw_text(key)) is not None:
            self._track_access(key)
            return self._get_cleaned_text(text)
        return None

    def get_current_optional(self, key: types.TextMapHash) -> str | None:
        """Get current-build text by ID, returns None if not found."""
        if (text := self._text_map.get(key)) is not None:
            self._track_access(key)
            return self._get_cleaned_text(text)
        return None

    def get_optional_untracked(self, key: types.TextMapHash) -> str | None:
        """Get text by ID without recording access."""
        if (text := self._get_raw_text(key)) is not None:
            return self._get_cleaned_text(text)
        return None


class ReadablesTracker(IdTracker[types.ReadableFilename]):
    """Tracks which readable filenames have been accessed."""

    def __init__(self, agd_path: pathlib.Path, language_short: str) -> None:
        self._agd_path = agd_path
        self._language_short = language_short
        self._readable_base_path = agd_path / "Readable" / language_short

        # Discover all readable files
        all_readable_filenames: set[types.ReadableFilename] = set()
        if self._readable_base_path.exists():
            for file_path in self._readable_base_path.glob("*.txt"):
                # Store the filename relative to the readable base directory
                all_readable_filenames.add(file_path.name)

        super().__init__(set(sorted(all_readable_filenames)))

    def get_content(self, readable_filename: types.ReadableFilename) -> str | None:
        """Get readable file content by filename and track access."""
        if readable_filename in self._all_ids:
            self._track_access(readable_filename)
            file_path = self._readable_base_path / readable_filename
            return file_path.read_text(encoding="utf-8").strip()
        return None


@attrs.frozen
class DataRepo:
    """Repository for loading AnimeGameData files."""

    agd_path: pathlib.Path = attrs.field(converter=pathlib.Path)
    language: localization.Language

    @staticmethod
    def _language_short(language: localization.Language) -> str:
        """Short language code used in AGD file structure (maps ENG to EN)."""
        return "EN" if language == localization.Language.ENG else language.value

    @property
    def language_short(self) -> str:
        """Get the short language code used in AGD file structure (maps ENG to EN)."""
        return self._language_short(self.language)

    def _load_excel(self, filename: str) -> Any:
        return json.loads(
            (self.agd_path / "ExcelBinOutput" / filename).read_text(encoding="utf-8")
        )

    @staticmethod
    def _index_unique(
        data: Iterable[_T], key: Callable[[_T], _K], *, duplicate_name: str
    ) -> dict[_K, _T]:
        mapping: dict[_K, _T] = {}
        for item in data:
            item_key = key(item)
            if item_key in mapping:
                raise ValueError(f"Duplicate {duplicate_name}: {item_key}")
            mapping[item_key] = item
        return mapping

    @classmethod
    def from_env(cls) -> "DataRepo":
        """Create DataRepo from environment variables.

        Reads AGD_PATH for data location and AGD_LANGUAGE for language (defaults to CHS).
        """
        agd_path = os.environ.get("AGD_PATH")
        if not agd_path:
            raise ValueError("AGD_PATH environment variable not set")
        language_str = os.environ.get("AGD_LANGUAGE", "CHS")
        language = localization.Language(
            language_str
        )  # Will raise ValueError for invalid languages
        return cls(agd_path, language=language)

    @functools.lru_cache(maxsize=None)
    def _load_text_map_for(self, language: localization.Language) -> TextMapTracker:
        """Load the TextMap for a specific language, merging Medium variant if present."""
        language_short = self._language_short(language)
        return TextMapTracker(
            self._load_current_text_map(language_short),
            language,
            self._load_fallback_text_map(language_short),
        )

    def _load_current_text_map(self, language_short: str) -> types.TextMap:
        """Load current-build TextMap, merging Medium variant if present."""
        text_map_dir = self.agd_path / "TextMap"
        medium_path = text_map_dir / f"TextMap_Medium{language_short}.json"
        data: types.TextMap = (
            json.loads(medium_path.read_text(encoding="utf-8"))
            if medium_path.exists()
            else {}
        )
        data.update(
            json.loads(
                (text_map_dir / f"TextMap{language_short}.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        return data

    @functools.lru_cache(maxsize=None)
    def _load_fallback_text_map(self, language_short: str) -> types.TextMap:
        """Load older-build TextMaps used for current-build misses."""
        data: types.TextMap = {}
        for fallback_ref in _TEXT_MAP_FALLBACK_REFS:
            ref_data: types.TextMap = {}
            medium = self._git_show_text_map(
                fallback_ref, f"TextMap_Medium{language_short}.json", required=False
            )
            if medium is not None:
                ref_data.update(medium)
            required_text_map = self._git_show_text_map(
                fallback_ref, f"TextMap{language_short}.json", required=True
            )
            assert required_text_map is not None
            ref_data.update(required_text_map)
            for key, value in ref_data.items():
                data.setdefault(key, value)
        return data

    def _git_show_text_map(
        self, fallback_ref: str, filename: str, *, required: bool
    ) -> types.TextMap | None:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.agd_path),
                "show",
                f"{fallback_ref}:TextMap/{filename}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            data: types.TextMap = json.loads(result.stdout)
            return data
        if required:
            raise RuntimeError(
                f"Failed to load fallback TextMap {filename} at {fallback_ref}: "
                f"{result.stderr.strip()}"
            )
        return None

    def load_text_map(self) -> TextMapTracker:
        """Load TextMap for the instance's language, merging Medium variant if present."""
        return self._load_text_map_for(self.language)

    def load_source_text_map(self) -> TextMapTracker:
        """Load the CHS (source) TextMap regardless of the instance's language.

        Dev markers like ``$HIDDEN``/``(test)`` only exist in the CHS title text,
        so language-independent checks (e.g. filtering test/hidden quests) must
        consult CHS rather than the output language's text map.
        """
        return self._load_text_map_for(localization.Language.CHS)

    @functools.lru_cache(maxsize=None)
    def load_npc_excel_config_data(self) -> types.NpcExcelConfigData:
        """Load NPC Excel configuration data."""
        return self._load_excel("NpcExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_dialog_excel_config_data(self) -> types.DialogExcelConfigData:
        """Load Dialog Excel configuration data."""
        raw_data: list[dict[str, Any]] = self._load_excel("DialogExcelConfigData.json")
        return cast(
            types.DialogExcelConfigData,
            deobfuscation.deobfuscate_dialog_excel_config_data(raw_data),
        )

    @functools.lru_cache(maxsize=None)
    def load_localization_excel_config_data(self) -> types.LocalizationExcelConfigData:
        """Load localization Excel configuration data."""
        return self._load_excel("LocalizationExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_document_excel_config_data(
        self,
    ) -> dict[types.DocumentId, types.DocumentExcelConfigDataItem]:
        """Load DocumentExcelConfigData.json keyed by document id."""
        raw_data: list[dict[str, Any]] = self._load_excel(
            "DocumentExcelConfigData.json"
        )
        data = cast(
            types.DocumentExcelConfigData,
            deobfuscation.deobfuscate_document_excel_config_data(raw_data),
        )
        return self._index_unique(
            data, lambda doc_item: doc_item["id"], duplicate_name="document ID"
        )

    @functools.lru_cache(maxsize=None)
    def build_readable_stem_to_localization_id(self) -> dict[str, types.LocalizationId]:
        """Map a readable file stem to its localization id for the instance language.

        Inverts the per-readable linear scan over LocalizationExcelConfigData into a
        single pass so readable-metadata lookups become O(1). First entry wins, which
        matches the original break-on-first-match behavior.
        """
        language_short = self.language_short
        mapping: dict[str, types.LocalizationId] = {}
        for entry in self.load_localization_excel_config_data():
            for path_value in entry.values():
                if not isinstance(path_value, str):
                    continue
                path = pathlib.Path(path_value)
                if (
                    path_value.endswith(f"_{language_short}")
                    or language_short in path.parts
                ):
                    mapping.setdefault(path.name, entry["id"])
        return mapping

    @functools.lru_cache(maxsize=None)
    def build_localization_id_to_readable_path(
        self,
    ) -> dict[types.LocalizationId, types.ReadableFilename]:
        """Map a localization id to its readable filename for the instance language.

        The inverse of ``build_readable_stem_to_localization_id``, precomputed once
        so story-document assembly (e.g. weapons) resolves each page id in O(1)
        instead of rescanning LocalizationExcelConfigData per item. First language
        path wins, matching the original break-on-first-match behavior.
        """
        language_short = self.language_short
        mapping: dict[types.LocalizationId, types.ReadableFilename] = {}
        for entry in self.load_localization_excel_config_data():
            for path_value in entry.values():
                if not isinstance(path_value, str):
                    continue
                path = pathlib.Path(path_value)
                if (
                    path_value.endswith(f"_{language_short}")
                    or language_short in path.parts
                ):
                    mapping.setdefault(entry["id"], f"{path.name}.txt")
        return mapping

    @functools.lru_cache(maxsize=None)
    def build_localization_id_to_title_hash(
        self,
    ) -> dict[types.LocalizationId, types.TextMapHash]:
        """Map a localization id to its document title hash.

        Inverts the per-readable linear scan over DocumentExcelConfigData; first
        document wins per id, matching the original break-on-first-match behavior.
        """
        mapping: dict[types.LocalizationId, types.TextMapHash] = {}
        for doc_item in self.load_document_excel_config_data().values():
            for loc_id in itertools.chain(
                doc_item.get("CUSTOM_addlLocalID", []),
                doc_item["questContentLocalizedId"],
                doc_item["questIDList"],
            ):
                mapping.setdefault(loc_id, doc_item["titleTextMapHash"])
        return mapping

    @functools.lru_cache(maxsize=None)
    def load_book_suit_excel_config_data(
        self,
    ) -> dict[types.BookSuitId, types.BookSuitExcelConfigDataItem]:
        """Load BookSuitExcelConfigData.json keyed by suit id."""
        return self._index_unique(
            self._load_excel("BookSuitExcelConfigData.json"),
            lambda suit: suit["id"],
            duplicate_name="book suit ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_books_codex_excel_config_data(self) -> types.BooksCodexExcelConfigData:
        """Load BooksCodexExcelConfigData.json."""
        return self._load_excel("BooksCodexExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def build_book_series_mapping(
        self,
    ) -> dict[types.BookSuitId, list[types.ReadableFilename]]:
        """Group multi-volume book series to their ordered volume readable filenames.

        Active book-codex entries are grouped by their material's suit (``setID``)
        and ordered by ``sortOrder``; only suits with two or more volumes count as a
        series (single-volume and non-codex books stay standalone). Each volume
        resolves material id -> document -> localization -> readable filename (the
        material id and document id coincide for books). Raises if a volume claims a
        suit or readable that can't be resolved, surfacing the data gap rather than
        silently dropping the grouping.
        """
        materials = {
            material["id"]: material
            for material in self.load_material_excel_config_data().get_all()
        }
        suits = self.load_book_suit_excel_config_data()
        documents = self.load_document_excel_config_data()
        readable_paths = self.build_localization_id_to_readable_path()

        grouped: dict[types.BookSuitId, list[types.ReadableFilename]] = {}
        for codex in sorted(
            self.load_books_codex_excel_config_data(),
            key=lambda codex: codex["sortOrder"],
        ):
            if codex["isDisuse"]:
                continue
            material_id = codex["materialId"]
            if (material := materials.get(material_id)) is None:
                raise ValueError(
                    f"Book codex {codex['id']} references unknown material "
                    f"{material_id}"
                )
            if (suit_id := material["setID"]) == 0:
                continue
            if suit_id not in suits:
                raise ValueError(
                    f"Book material {material_id} claims unknown suit {suit_id}"
                )
            if (document := documents.get(material_id)) is None:
                raise ValueError(
                    f"Book material {material_id} (suit {suit_id}) has no document"
                )
            if (
                filename := next(
                    (
                        readable_path
                        for loc_id in itertools.chain(
                            document["questIDList"],
                            document["questContentLocalizedId"],
                            document.get("CUSTOM_addlLocalID", []),
                        )
                        if (readable_path := readable_paths.get(loc_id)) is not None
                    ),
                    None,
                )
            ) is None:
                raise ValueError(
                    f"Book material {material_id} (suit {suit_id}) has no readable file"
                )
            grouped.setdefault(suit_id, []).append(filename)
        return {
            suit_id: filenames
            for suit_id, filenames in grouped.items()
            if len(filenames) >= 2
        }

    @functools.lru_cache(maxsize=None)
    def load_material_excel_config_data(self) -> MaterialTracker:
        """Load material Excel configuration data as MaterialTracker."""
        return MaterialTracker(self._load_excel("MaterialExcelConfigData.json"))

    @functools.lru_cache(maxsize=None)
    def load_achievement_excel_config_data(
        self,
    ) -> types.AchievementExcelConfigData:
        """Load AchievementExcelConfigData.json."""
        return self._load_excel("AchievementExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_achievement_goal_excel_config_data(
        self,
    ) -> types.AchievementGoalExcelConfigData:
        """Load AchievementGoalExcelConfigData.json."""
        return self._load_excel("AchievementGoalExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def build_achievement_section_mapping(
        self,
    ) -> dict[
        types.AchievementGoalId,
        tuple[
            types.AchievementGoalExcelConfigDataItem,
            list[types.AchievementExcelConfigDataItem],
        ],
    ]:
        """Index active achievements by section in configured display order."""
        mapping = {
            section["id"]: (section, list[types.AchievementExcelConfigDataItem]())
            for section in self.load_achievement_goal_excel_config_data()
        }
        if len(mapping) != len(self.load_achievement_goal_excel_config_data()):
            raise ValueError("Duplicate achievement section ID")
        for achievement in self.load_achievement_excel_config_data():
            if achievement["isDisuse"]:
                continue
            if (section := mapping.get(achievement["goalId"])) is None:
                raise ValueError(
                    f"Achievement {achievement['id']} references unknown section "
                    f"{achievement['goalId']}"
                )
            section[1].append(achievement)
        for _, achievements in mapping.values():
            achievements.sort(
                key=lambda achievement: (achievement["orderId"], achievement["id"])
            )
        return mapping

    @functools.lru_cache(maxsize=None)
    def build_talk_group_mapping(
        self,
    ) -> dict[tuple[talk_parsing.TalkGroupType, talk_parsing.TalkGroupId], str]:
        return self._get_talk_parser().talk_group_id_to_path

    @functools.lru_cache(maxsize=None)
    def build_free_group_mapping(self) -> dict[types.QuestId, list[str]]:
        """questId -> FreeGroup talk file paths attached by the id heuristic."""
        return self._get_talk_parser().free_group_quest_to_paths

    @functools.lru_cache(maxsize=None)
    def load_coop_interaction_excel_config_data(
        self,
    ) -> types.CoopInteractionExcelConfigData:
        """Load CoopInteractionExcelConfigData.json (cleartext)."""
        return self._load_excel("CoopInteractionExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_coop_chapter_excel_config_data(
        self,
    ) -> types.CoopChapterExcelConfigData:
        """Load CoopChapterExcelConfigData.json (cleartext)."""
        return self._load_excel("CoopChapterExcelConfigData.json")

    def build_coop_story_mapping(self) -> dict[types.CoopStoryId, list[str]]:
        """coopStoryId -> its Coop talk file paths, sorted by local talk id."""
        return self._get_talk_parser().coop_story_to_paths

    @functools.lru_cache(maxsize=None)
    def build_coop_story_graph_mapping(
        self,
    ) -> dict[types.CoopStoryId, coop_graph.CoopStoryGraph]:
        """coopStoryId -> play-order node graph, from the BinOutput/Coop/*.json files."""
        graphs: dict[types.CoopStoryId, coop_graph.CoopStoryGraph] = {}
        for json_file in (self.agd_path / "BinOutput" / "Coop").glob("*.json"):
            raw_data = json.loads(json_file.read_text(encoding="utf-8"))
            data = deobfuscation.deobfuscate_coop_graph_data(raw_data)
            for story in data["coopInteractionMap"].values():
                graphs[story["id"]] = coop_graph.build_story_graph(story)
        return graphs

    @functools.lru_cache(maxsize=None)
    def build_hangout_quest_to_stories(
        self,
    ) -> dict[types.QuestId, list[types.CoopStoryId]]:
        """hangout questId -> its coopStoryIds that have talk files, sorted."""
        stories_with_files = self.build_coop_story_mapping()
        mapping: dict[types.QuestId, list[types.CoopStoryId]] = {}
        for entry in self.load_coop_interaction_excel_config_data():
            if (coop_story_id := entry["id"]) in stories_with_files:
                mapping.setdefault(entry["mainQuestId"], []).append(coop_story_id)
        return {quest_id: sorted(stories) for quest_id, stories in mapping.items()}

    @functools.lru_cache(maxsize=None)
    def build_coop_chapter_to_avatar_mapping(
        self,
    ) -> dict[types.ChapterId, types.AvatarId]:
        """Coop chapter id -> its primary character's avatar id."""
        return {
            chapter["id"]: chapter["avatarId"]
            for chapter in self.load_coop_chapter_excel_config_data()
        }

    @functools.lru_cache(maxsize=None)
    def build_avatar_id_to_name_mapping(self) -> dict[types.AvatarId, str]:
        """Avatar id -> localized character name (only avatars whose name resolves)."""
        text_map = self.load_text_map()
        return {
            avatar["id"]: name
            for avatar in self.load_avatar_excel_config_data()
            if (name := text_map.get_optional(avatar["nameTextMapHash"])) is not None
        }

    @functools.lru_cache(maxsize=None)
    def get_dialog_id_to_content_hash_mapping(
        self,
    ) -> dict[types.DialogId, types.TextMapHash]:
        """Dialog id -> talkContentTextMapHash, for resolving Coop choice prompts."""
        return {
            dialog_item["id"]: dialog_item["talkContentTextMapHash"]
            for dialog_item in self.load_dialog_excel_config_data()
        }

    @functools.lru_cache(maxsize=None)
    def build_quest_mapping(self) -> dict[types.QuestId, str]:
        """Build a mapping from quest ID to BinOutput/Quest file path.

        AGD retains stale hash-named duplicates of quests across builds, so when
        several files share an ID the canonically-named ``{id}.json`` wins.
        """
        quest_id_to_path: dict[types.QuestId, str] = {}

        for json_file in (self.agd_path / "BinOutput" / "Quest").glob("*.json"):
            relative_path_str = json_file.relative_to(self.agd_path).as_posix()
            quest_data = self.load_quest_data(relative_path_str)
            assert isinstance(quest_data, dict), relative_path_str
            quest_id = quest_data.get("id")
            assert isinstance(quest_id, int), relative_path_str

            canonical_path = f"BinOutput/Quest/{quest_id}.json"
            if (existing := quest_id_to_path.get(quest_id)) is not None:
                if existing == canonical_path or relative_path_str != canonical_path:
                    logger.warning(
                        "Duplicate quest ID %s: keeping %s, ignoring %s",
                        quest_id,
                        existing,
                        relative_path_str,
                    )
                    continue
                logger.warning(
                    "Duplicate quest ID %s: replacing %s with canonical %s",
                    quest_id,
                    existing,
                    relative_path_str,
                )

            quest_id_to_path[quest_id] = relative_path_str

        return quest_id_to_path

    @functools.lru_cache(maxsize=None)
    def _get_talk_parser(self) -> talk_parsing.TalkParser:
        return talk_parsing.TalkParser(self, self.load_talk_excel_config_data())

    def precompute_for_fork(self) -> None:
        """Pre-compute expensive mappings in parent process for inheritance via fork.

        This method should be called in the parent process before creating
        multiprocessing pools with fork start method to ensure child processes
        inherit the cached results.
        """
        self.build_talk_group_mapping()
        self.load_source_text_map()
        self.load_text_map()

        # Warm the quest mapping (and, transitively, the load_quest_data cache it
        # populates) so forked workers don't each re-glob and re-parse all quests.
        self.build_quest_mapping()

        # Warm the dialog-derived mapping so forked workers inherit it instead of
        # each re-parsing the large dialog Excel config and rebuilding it by
        # iterating over all of it. This transitively warms
        # load_dialog_excel_config_data too.
        self.get_dialog_id_to_role_name_hash_mapping()

        # Warm the readable-metadata lookup maps so forked workers don't each
        # re-scan the localization/document Excel configs once per readable.
        self.build_readable_stem_to_localization_id()
        self.build_localization_id_to_readable_path()
        self.build_localization_id_to_title_hash()

        # Warm the book-series grouping so forked book workers inherit it instead
        # of each re-scanning the codex/material/suit configs.
        self.build_book_series_mapping()

        # Warm the NPC name mappings (output-language + CHS source) so forked
        # talk-group workers inherit them instead of each re-scanning the NPC
        # Excel config and text maps.
        self.get_npc_id_to_name_mapping()
        self.get_npc_id_to_source_name_mapping()

        # Warm the achievement section index so workers inherit the parsed
        # configs and do not each scan all achievements once per section.
        self.build_achievement_section_mapping()

        # Warm the hangout (Coop) mappings so forked Hangouts workers inherit the
        # parsed Coop story graphs, interaction/chapter configs, and the avatar /
        # main-quest / dialog-content lookups instead of each re-parsing them.
        self.build_coop_story_graph_mapping()
        self.build_hangout_quest_to_stories()
        self.load_main_quest_excel_config_data()
        self.build_coop_chapter_to_avatar_mapping()
        self.build_avatar_id_to_name_mapping()
        self.get_dialog_id_to_content_hash_mapping()

        # Warm the avatar/constellation Excel configs (~1.8MB across the skill,
        # talent, and depot files) so forked character-story workers inherit them
        # instead of each re-parsing the large files on first constellation lookup.
        self.load_avatar_excel_config_data()
        self.load_avatar_skill_depot_excel_config_data()
        self.load_avatar_talent_excel_config_data()
        self.load_avatar_skill_excel_config_data()

        # Warm the living-beings archive configs so forked creature workers inherit
        # the parsed codex index and describe/title/special-name lookups instead of
        # each re-parsing them.
        self.load_animal_codex_excel_config_data()
        self.load_monster_describe_excel_config_data()
        self.load_monster_title_excel_config_data()
        self.load_monster_special_name_excel_config_data()
        self.load_animal_describe_excel_config_data()

    @functools.lru_cache(maxsize=None)
    def load_talk_excel_config_data(self) -> types.TalkExcelConfigData:
        """Load and return the raw talk Excel configuration data."""

        def _load_talk_file(file_path: pathlib.Path) -> types.TalkExcelConfigData:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            assert isinstance(data, list), file_path
            return data

        base_path = self.agd_path / "ExcelBinOutput"
        if split_paths := sorted(base_path.glob("TalkExcelConfigData_*.json")):
            data = []
            for file_path in split_paths:
                data.extend(_load_talk_file(file_path))
            return data

        file_path = base_path / "TalkExcelConfigData.json"
        if not file_path.exists():
            raise FileNotFoundError(
                "TalkExcelConfigData.json or TalkExcelConfigData_*.json not found"
            )
        return _load_talk_file(file_path)

    @functools.lru_cache(maxsize=None)
    def build_talk_tracker(self) -> TalkTracker:
        """Build the access-tracking TalkTracker with resolved talk file paths."""
        return TalkTracker(
            self.load_talk_excel_config_data(),
            self._get_talk_parser().talk_id_to_path,
        )

    @functools.lru_cache(maxsize=None)
    def load_talk_data(self, talk_file: str) -> types.TalkData:
        """Load talk data from specified talk file."""
        file_path = self.agd_path / talk_file
        with open(file_path, encoding="utf-8") as f:
            raw_data: dict[str, Any] = json.load(f)
            data = deobfuscation.deobfuscate_talk_data(raw_data)
            return data  # type: ignore[return-value]

    @functools.lru_cache(maxsize=None)
    def load_talk_group_data(self, path: str) -> dict[str, Any]:
        """Load talk group data from specified talk file."""
        file_path = self.agd_path / path
        with open(file_path, encoding="utf-8") as f:
            raw_data: dict[str, Any] = json.load(f)
            data = deobfuscation.deobfuscate_talk_group_data(raw_data)
            if (
                (
                    field := {
                        "NpcGroup": "npcId",
                        "ActivityGroup": "activityId",
                        "StoryboardGroup": "storyboardId",
                    }.get(file_path.parts[-2])
                )
                is not None
            ) and file_path.stem.isdigit():
                data.setdefault(field, int(file_path.stem))
            return data

    @functools.lru_cache(maxsize=None)
    def load_quest_data(self, quest_file: str) -> types.QuestData:
        """Load quest data from specified quest file."""
        file_path = self.agd_path / quest_file
        with open(file_path, encoding="utf-8") as f:
            raw_data: dict[str, Any] = json.load(f)
            data = deobfuscation.deobfuscate_quest_data(raw_data)
            return data  # type: ignore[return-value]

    @functools.lru_cache(maxsize=None)
    def load_avatar_excel_config_data(self) -> types.AvatarExcelConfigData:
        """Load avatar Excel configuration data."""
        return self._load_excel("AvatarExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_avatar_skill_depot_excel_config_data(
        self,
    ) -> dict[types.SkillDepotId, types.AvatarSkillDepotExcelConfigDataItem]:
        """Load avatar skill-depot data as a dict keyed by depot id."""
        return self._index_unique(
            self._load_excel("AvatarSkillDepotExcelConfigData.json"),
            lambda item: item["id"],
            duplicate_name="skill depot ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_avatar_talent_excel_config_data(
        self,
    ) -> dict[types.TalentId, types.AvatarTalentExcelConfigDataItem]:
        """Load constellation (talent) data as a dict keyed by talent id."""
        return self._index_unique(
            self._load_excel("AvatarTalentExcelConfigData.json"),
            lambda item: item["talentId"],
            duplicate_name="talent ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_avatar_skill_excel_config_data(
        self,
    ) -> dict[types.SkillId, types.AvatarSkillExcelConfigDataItem]:
        """Load avatar skill data as a dict keyed by skill id."""
        return self._index_unique(
            self._load_excel("AvatarSkillExcelConfigData.json"),
            lambda item: item["id"],
            duplicate_name="skill ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_fetter_story_excel_config_data(self) -> types.FetterStoryExcelConfigData:
        """Load fetter story Excel configuration data."""
        return self._load_excel("FetterStoryExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_fetters_excel_config_data(self) -> types.FettersExcelConfigData:
        """Load fetters Excel configuration data."""
        return self._load_excel("FettersExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_animal_codex_excel_config_data(
        self,
    ) -> dict[types.AnimalCodexId, types.AnimalCodexExcelConfigDataItem]:
        """Load AnimalCodexExcelConfigData.json keyed by codex entry id."""
        return self._index_unique(
            self._load_excel("AnimalCodexExcelConfigData.json"),
            lambda entry: entry["id"],
            duplicate_name="animal codex ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_monster_describe_excel_config_data(
        self,
    ) -> dict[types.CreatureDescribeId, types.MonsterDescribeExcelConfigDataItem]:
        """Load MonsterDescribeExcelConfigData.json keyed by describe id."""
        return self._index_unique(
            self._load_excel("MonsterDescribeExcelConfigData.json"),
            lambda entry: entry["id"],
            duplicate_name="monster describe ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_monster_title_excel_config_data(
        self,
    ) -> dict[types.MonsterTitleId, types.MonsterTitleExcelConfigDataItem]:
        """Load MonsterTitleExcelConfigData.json keyed by title id."""
        return self._index_unique(
            self._load_excel("MonsterTitleExcelConfigData.json"),
            lambda entry: entry["titleID"],
            duplicate_name="monster title ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_monster_special_name_excel_config_data(
        self,
    ) -> types.MonsterSpecialNameExcelConfigData:
        """Load MonsterSpecialNameExcelConfigData.json."""
        return self._load_excel("MonsterSpecialNameExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_animal_describe_excel_config_data(
        self,
    ) -> dict[types.CreatureDescribeId, types.AnimalDescribeExcelConfigDataItem]:
        """Load AnimalDescribeExcelConfigData.json keyed by describe id."""
        return self._index_unique(
            self._load_excel("AnimalDescribeExcelConfigData.json"),
            lambda entry: entry["id"],
            duplicate_name="animal describe ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_main_quest_excel_config_data(
        self,
    ) -> dict[types.QuestId, types.MainQuestExcelConfigDataItem]:
        """Load main quest Excel config data as a dict keyed by quest id."""
        return self._index_unique(
            self._load_excel("MainQuestExcelConfigData.json"),
            lambda quest: quest["id"],
            duplicate_name="main quest ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_chapter_excel_config_data(
        self,
    ) -> dict[types.ChapterId, types.ChapterExcelConfigDataItem]:
        """Load ChapterExcelConfigData.json keyed by chapter id."""
        return self._index_unique(
            self._load_excel("ChapterExcelConfigData.json"),
            lambda chapter: chapter["id"],
            duplicate_name="chapter ID",
        )

    def _build_npc_id_to_name(self, text_map: TextMapTracker) -> dict[str, str]:
        """Build NPC ID -> name using the given text map."""
        npc_id_to_name: dict[str, str] = {}
        for npc in self.load_npc_excel_config_data():
            npc_id = str(npc["id"])
            if (name := text_map.get_optional(npc["nameTextMapHash"])) is not None:
                npc_id_to_name[npc_id] = name

        return npc_id_to_name

    @functools.lru_cache(maxsize=None)
    def get_npc_id_to_name_mapping(self) -> dict[str, str]:
        """Get cached mapping from NPC ID to name."""
        return self._build_npc_id_to_name(self.load_text_map())

    @functools.lru_cache(maxsize=None)
    def get_npc_id_to_source_name_mapping(self) -> dict[str, str]:
        """NPC ID -> CHS (source) name, for language-independent test/hidden filtering.

        Dev markers like ``$HIDDEN``/``(test)`` only exist in the CHS name text.
        """
        return self._build_npc_id_to_name(self.load_source_text_map())

    @functools.lru_cache(maxsize=None)
    def get_dialog_id_to_role_name_hash_mapping(
        self,
    ) -> dict[types.DialogId, types.TextMapHash]:
        """Get cached mapping from dialog ID to talkRoleNameTextMapHash."""
        dialog_data = self.load_dialog_excel_config_data()

        dialog_id_to_role_hash: dict[types.DialogId, types.TextMapHash] = {}
        for dialog_item in dialog_data:
            dialog_id = dialog_item["id"]
            role_name_hash = dialog_item["talkRoleNameTextMapHash"]
            dialog_id_to_role_hash[dialog_id] = role_name_hash

        return dialog_id_to_role_hash

    @functools.lru_cache(maxsize=None)
    def load_reliquary_set_excel_config_data(self) -> types.ReliquarySetExcelConfigData:
        """Load ReliquarySetExcelConfigData.json."""
        return self._load_excel("ReliquarySetExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_reliquary_excel_config_data(self) -> types.ReliquaryExcelConfigData:
        """Load ReliquaryExcelConfigData.json."""
        return self._load_excel("ReliquaryExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_equip_affix_excel_config_data(self) -> types.EquipAffixExcelConfigData:
        """Load EquipAffixExcelConfigData.json."""
        return self._load_excel("EquipAffixExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_weapon_excel_config_data(
        self,
    ) -> dict[types.WeaponId, types.WeaponExcelConfigDataItem]:
        """Load WeaponExcelConfigData.json as a dict mapping weapon ID to weapon."""
        return self._index_unique(
            self._load_excel("WeaponExcelConfigData.json"),
            lambda weapon: weapon["id"],
            duplicate_name="weapon ID",
        )

    @functools.lru_cache(maxsize=None)
    def get_readables(self) -> ReadablesTracker:
        """Get ReadablesTracker for tracking access to readable files."""
        return ReadablesTracker(self.agd_path, self.language_short)
