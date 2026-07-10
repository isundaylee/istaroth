"""Data repository for loading AnimeGameData (AGD) files."""

from __future__ import annotations

import functools
import itertools
import logging
import os
import pathlib
import subprocess
from typing import Any, Callable, Iterable, TypeVar, cast

import attrs
import orjson

from istaroth import text_cleanup
from istaroth.agd import (
    agd_types,
    coop_graph,
    deobfuscation,
    id_types,
    localization,
    talk_parsing,
    tracking,
)

logger = logging.getLogger(__name__)

_K = TypeVar("_K")
_T = TypeVar("_T")
_CachedMethodT = TypeVar("_CachedMethodT", bound=Callable[..., Any])

# Names of the DataRepo methods marked with @_warm_on_fork, in class-definition
# order; precompute_for_fork warms each so forked workers inherit the caches.
_FORK_WARM_METHOD_NAMES: list[str] = []


def _warm_on_fork(method: _CachedMethodT) -> _CachedMethodT:
    """``lru_cache`` a DataRepo method and register it for fork pre-warming.

    Applies an unbounded ``lru_cache`` and records the method in
    ``_FORK_WARM_METHOD_NAMES`` so ``precompute_for_fork`` warms it (and, through
    that call, everything it transitively pulls). Every fork-warmed method thus
    caches uniformly under a single decorator, and a newly added one can't
    silently fall off a hand-maintained warm list.
    """
    _FORK_WARM_METHOD_NAMES.append(method.__name__)
    return cast(_CachedMethodT, functools.lru_cache(maxsize=None)(method))


# Ordered newest-to-oldest; earlier refs win when multiple fallbacks contain a hash.
# Sex-pronoun SEXPRO tokens also resolve against these builds (see
# _load_pronoun_hashes): 6.x dropped their TextMap rows and reassigned the manual
# hash ids, so both token -> hash and hash -> text are read from here.
#
# 6.6.0/6.5.0 recover the great majority of hashes that a version bump drops from
# the current TextMap (investigated in issue #273): checked back through 5.4.0,
# nothing older than the immediately preceding minor version ever contributed a
# recoverable hash, so there's no benefit to walking further back. 8c3aecbd6ed
# (5.4.0) stays for the older SEXPRO manual-hash pairing above.
_TEXT_MAP_FALLBACK_REFS: tuple[str, ...] = (
    "4d9593eb73a",  # 6.6.0
    "f9a21406731",  # 6.5.0
    "8c3aecbd6ed",  # 5.4.0
)


class MaterialTracker(
    tracking.DictTracker[id_types.MaterialId, agd_types.MaterialExcelConfigDataItem]
):
    """Tracks which material IDs have been accessed."""

    def __init__(self, material_data: agd_types.MaterialExcelConfigData) -> None:
        super().__init__({material["id"]: material for material in material_data})


class TalkTracker(
    tracking.DictTracker[id_types.TalkId, agd_types.TalkExcelConfigDataItem]
):
    """Tracks which talk IDs have been accessed."""

    def __init__(
        self,
        talk_excel_data: agd_types.TalkExcelConfigData,
        talk_file_mapping: dict[id_types.TalkId, str],
    ) -> None:
        super().__init__({talk["id"]: talk for talk in talk_excel_data})
        self._talk_file_mapping = talk_file_mapping

    def get_talk_file_path(self, talk_id: id_types.TalkId) -> str | None:
        """Get the file path for a talk ID and track access."""
        if self.get(talk_id) is None:
            return None

        # Look up the file path in the pre-built mapping
        return self._talk_file_mapping.get(talk_id)


class TextMapTracker(tracking.IdTracker[id_types.TextMapHash]):
    """Wrapper around TextMap that tracks which text IDs have been accessed.

    ``TextMap`` ships with ``str`` keys (JSON object keys are always strings);
    they are int-keyed once here so lookups carry a ``TextMapHash`` directly.

    Deliberately bends the base contract: ``_all_ids`` is only the *current*
    build's hashes, but reads that resolve via the older fallback TextMap still
    record their hash as accessed (and ``has`` reports fallback hits).
    Since ``get_unused_ids`` subtracts accessed from ``_all_ids``, those
    out-of-set fallback hashes never inflate the current-build unused count --
    they simply don't count as unused current hashes, which is the intent.
    """

    def __init__(
        self,
        text_map: agd_types.TextMap,
        language: localization.Language,
        fallback_text_map: agd_types.TextMap | None = None,
        *,
        pronoun_hashes: dict[str, id_types.TextMapHash],
    ) -> None:
        self._text_map = self._normalize_text_map(text_map)
        self._fallback_text_map = self._normalize_text_map(fallback_text_map or {})
        self._text_maps = (self._text_map, self._fallback_text_map)
        super().__init__(set(self._text_map))
        self._language = language
        self._pronoun_hashes = pronoun_hashes

    @staticmethod
    def _normalize_text_map(
        text_map: agd_types.TextMap,
    ) -> dict[id_types.TextMapHash, str]:
        return {int(k): v for k, v in text_map.items()}

    def has(self, key: id_types.TextMapHash) -> bool:
        """Whether key resolves in the current or fallback TextMap."""
        return self._get_raw_text(key) is not None

    def clean_text(self, text: str) -> str:
        """Clean game-text markers (incl. SEXPRO pronouns) for this language."""
        return self._get_cleaned_text(text)

    def _get_cleaned_text(self, text: str) -> str:
        text = text_cleanup.resolve_sexpro(text, self._resolve_pronoun_token)
        return text_cleanup.clean_text_markers(text, self._language)

    def _resolve_pronoun_token(self, token: str) -> str:
        """Raw text for a SEXPRO ``INFO_*_PRONOUN_*`` token (raises if unknown)."""
        if (text := self._get_raw_text(self._pronoun_hashes[token])) is None:
            raise KeyError(f"Unresolvable SEXPRO pronoun token: {token}")
        return text

    def _get_raw_text(self, key: id_types.TextMapHash) -> str | None:
        for text_map in self._text_maps:
            if (text := text_map.get(key)) is not None:
                return text
        return None

    def get(self, key: id_types.TextMapHash, default: str) -> str:
        """Get text by ID with default, tracks access if key exists."""
        if (text := self._get_raw_text(key)) is not None:
            self._track_access(key)
            return self._get_cleaned_text(text)
        return default

    def get_optional(self, key: id_types.TextMapHash) -> str | None:
        """Get text by ID, returns None if not found."""
        if (text := self._get_raw_text(key)) is not None:
            self._track_access(key)
            return self._get_cleaned_text(text)
        return None

    def get_required(self, key: id_types.TextMapHash) -> str:
        """Get text by ID, raises when the hash resolves nowhere."""
        if (text := self.get_optional(key)) is None:
            raise ValueError(f"Unresolvable text map hash {key}")
        return text

    def get_current_optional(self, key: id_types.TextMapHash) -> str | None:
        """Get current-build text by ID, returns None if not found."""
        if (text := self._text_map.get(key)) is not None:
            self._track_access(key)
            return self._get_cleaned_text(text)
        return None

    def get_optional_untracked(self, key: id_types.TextMapHash) -> str | None:
        """Get text by ID without recording access."""
        if (text := self._get_raw_text(key)) is not None:
            return self._get_cleaned_text(text)
        return None

    def get_current_optional_untracked(self, key: id_types.TextMapHash) -> str | None:
        """Get current-build text by ID without recording access."""
        if (text := self._text_map.get(key)) is not None:
            return self._get_cleaned_text(text)
        return None


class ReadablesTracker(tracking.IdTracker[id_types.ReadableFilename]):
    """Tracks which readable filenames have been accessed."""

    def __init__(
        self,
        readable_filenames: Iterable[id_types.ReadableFilename],
        readable_base_path: pathlib.Path,
    ) -> None:
        self._readable_base_path = readable_base_path
        super().__init__(set(readable_filenames))

    def get_content(self, readable_filename: id_types.ReadableFilename) -> str | None:
        """Get readable file content by filename and track access."""
        if readable_filename in self._all_ids:
            self._track_access(readable_filename)
            file_path = self._readable_base_path / readable_filename
            return file_path.read_text(encoding="utf-8").strip()
        return None


@attrs.frozen
class DataRepo:
    """Repository for loading AnimeGameData files.

    Method naming convention:

    - ``load_*`` reads a raw AGD file (returned as-is, or keyed by id).
    - ``build_*`` constructs a derived, cached object. Two suffixes distinguish
      what it returns: ``build_*_tracker`` returns a ``*Tracker``;
      ``build_*_mapping`` returns a ``dict`` index/mapping. The ``_mapping``
      suffix is kept even on ``build_<key>_to_<value>_mapping`` names, so the
      method reads as "the whole mapping" rather than a single-item conversion.
    """

    agd_path: pathlib.Path = attrs.field(converter=pathlib.Path)
    language: localization.Language
    git_ref: str | None = None
    """Load AGD files from this git revision of ``agd_path`` instead of the
    checkout. Honored by the excel loaders and file-name listings (what the
    first-seen scan needs); the BinOutput/TextMap/readable-content loaders
    always read the checkout."""

    @staticmethod
    def _language_short(language: localization.Language) -> str:
        """Short language code used in AGD file structure (maps ENG to EN)."""
        return "EN" if language == localization.Language.ENG else language.value

    @property
    def language_short(self) -> str:
        """Get the short language code used in AGD file structure (maps ENG to EN)."""
        return self._language_short(self.language)

    def _read_bytes(self, relative_path: str) -> bytes:
        """Read a file from ``git_ref`` when set, else from the checkout."""
        if self.git_ref is None:
            return (self.agd_path / relative_path).read_bytes()
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.agd_path),
                "show",
                f"{self.git_ref}:{relative_path}",
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise FileNotFoundError(
                f"Failed to load {relative_path} at {self.git_ref}: "
                f"{result.stderr.decode().strip()}"
            )
        return result.stdout

    def _list_file_names(self, relative_dir: str) -> list[str]:
        """File names directly under ``relative_dir`` (empty for a missing dir)."""
        if self.git_ref is None:
            dir_path = self.agd_path / relative_dir
            if not dir_path.exists():
                return []
            return sorted(p.name for p in dir_path.iterdir() if p.is_file())
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.agd_path),
                "ls-tree",
                "--name-only",
                self.git_ref,
                f"{relative_dir}/",
            ],
            capture_output=True,
            check=True,
        )
        return sorted(
            line.rsplit("/", 1)[-1]
            for line in result.stdout.decode().splitlines()
            if line
        )

    def _load_excel(self, filename: str) -> Any:
        return orjson.loads(self._read_bytes(f"ExcelBinOutput/{filename}"))

    def load_excel_raw(self, filename: str) -> Any:
        """Load an ExcelBinOutput file as raw parsed JSON (no field typing)."""
        return self._load_excel(filename)

    def list_readable_filenames(self) -> list[id_types.ReadableFilename]:
        """Readable file names for the instance's language."""
        return [
            name
            for name in self._list_file_names(f"Readable/{self.language_short}")
            if name.endswith(".txt")
        ]

    def list_subtitle_names(self) -> list[str]:
        """Subtitle file names for the instance's language (any extension)."""
        return self._list_file_names(f"Subtitle/{self.language_short}")

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
    def _build_text_map_tracker_for(
        self, language: localization.Language
    ) -> TextMapTracker:
        """Load the TextMap for a specific language, merging Medium variant if present."""
        language_short = self._language_short(language)
        return TextMapTracker(
            self._load_current_text_map(language_short),
            language,
            self._load_fallback_text_map(language_short),
            pronoun_hashes=self._load_pronoun_hashes(),
        )

    def _load_current_text_map(self, language_short: str) -> agd_types.TextMap:
        """Load current-build TextMap, merging Medium variant if present."""
        text_map_dir = self.agd_path / "TextMap"
        medium_path = text_map_dir / f"TextMap_Medium{language_short}.json"
        data: agd_types.TextMap = (
            orjson.loads(medium_path.read_bytes()) if medium_path.exists() else {}
        )
        data.update(
            orjson.loads((text_map_dir / f"TextMap{language_short}.json").read_bytes())
        )
        return data

    @functools.lru_cache(maxsize=None)
    def _load_fallback_text_map(self, language_short: str) -> agd_types.TextMap:
        """Load older-build TextMaps used for current-build misses."""
        data: agd_types.TextMap = {}
        for fallback_ref in _TEXT_MAP_FALLBACK_REFS:
            ref_data: agd_types.TextMap = {}
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

    @functools.lru_cache(maxsize=None)
    def _load_pronoun_hashes(self) -> dict[str, id_types.TextMapHash]:
        """Map SEXPRO ``INFO_*_PRONOUN_*`` tokens to their TextMap hashes.

        The SEXPRO branches are token *names*; token -> hash comes from
        ManualTextMapConfigData (the language-neutral TextMapTracker then does
        hash -> text). 6.x dropped these TextMap rows and reassigned the manual hash
        ids, so the manual config is read from the same older
        ``_TEXT_MAP_FALLBACK_REFS`` builds whose TextMaps back-fill the dropped
        hashes, keeping token and hash consistent.
        """
        pronoun_hashes: dict[str, id_types.TextMapHash] = {}
        for ref in _TEXT_MAP_FALLBACK_REFS:
            for entry in self._git_show_json(
                ref, "ExcelBinOutput/ManualTextMapConfigData.json"
            ):
                token = entry["textMapId"]
                if token.startswith("INFO_") and token not in pronoun_hashes:
                    pronoun_hashes[token] = int(entry["textMapContentTextMapHash"])
        return pronoun_hashes

    def _git_show_json(self, ref: str, path: str) -> Any:
        result = subprocess.run(
            ["git", "-C", str(self.agd_path), "show", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to load {path} at {ref}: {result.stderr.strip()}"
            )
        return orjson.loads(result.stdout)

    def _git_show_text_map(
        self, fallback_ref: str, filename: str, *, required: bool
    ) -> agd_types.TextMap | None:
        try:
            data: agd_types.TextMap = self._git_show_json(
                fallback_ref, f"TextMap/{filename}"
            )
            return data
        except RuntimeError:
            if required:
                raise
            return None

    @_warm_on_fork
    def build_text_map_tracker(self) -> TextMapTracker:
        """Load TextMap for the instance's language, merging Medium variant if present."""
        return self._build_text_map_tracker_for(self.language)

    @_warm_on_fork
    def build_source_text_map_tracker(self) -> TextMapTracker:
        """Load the CHS (source) TextMap regardless of the instance's language.

        Dev markers like ``$HIDDEN``/``(test)`` only exist in the CHS title text,
        so language-independent checks (e.g. filtering test/hidden quests) must
        consult CHS rather than the output language's text map.
        """
        return self._build_text_map_tracker_for(localization.Language.CHS)

    @functools.lru_cache(maxsize=None)
    def load_npc_excel_config_data(self) -> agd_types.NpcExcelConfigData:
        """Load NPC Excel configuration data."""
        return self._load_excel("NpcExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_dialog_excel_config_data(self) -> agd_types.DialogExcelConfigData:
        """Load Dialog Excel configuration data."""
        raw_data: list[dict[str, Any]] = self._load_excel("DialogExcelConfigData.json")
        return cast(
            agd_types.DialogExcelConfigData,
            deobfuscation.deobfuscate_dialog_excel_config_data(raw_data),
        )

    @functools.lru_cache(maxsize=None)
    def load_localization_excel_config_data(
        self,
    ) -> agd_types.LocalizationExcelConfigData:
        """Load localization Excel configuration data."""
        return self._load_excel("LocalizationExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_document_excel_config_data(
        self,
    ) -> dict[id_types.DocumentId, agd_types.DocumentExcelConfigDataItem]:
        """Load DocumentExcelConfigData.json keyed by document id."""
        raw_data: list[dict[str, Any]] = self._load_excel(
            "DocumentExcelConfigData.json"
        )
        data = cast(
            agd_types.DocumentExcelConfigData,
            deobfuscation.deobfuscate_document_excel_config_data(raw_data),
        )
        return self._index_unique(
            data, lambda doc_item: doc_item["id"], duplicate_name="document ID"
        )

    @_warm_on_fork
    def _build_readable_localization_maps(
        self,
    ) -> tuple[
        dict[str, id_types.LocalizationId],
        dict[id_types.LocalizationId, id_types.ReadableFilename],
    ]:
        """Build both readable<->localization lookup maps in a single scan.

        Inverts the per-readable linear scan over LocalizationExcelConfigData into a
        single pass so readable-metadata lookups (stem -> id) and story-document
        assembly (id -> filename) both become O(1). First match wins for each key,
        matching the original break-on-first-match behavior.
        """
        language_short = self.language_short
        stem_to_id: dict[str, id_types.LocalizationId] = {}
        id_to_filename: dict[id_types.LocalizationId, id_types.ReadableFilename] = {}
        for entry in self.load_localization_excel_config_data():
            for path_value in entry.values():
                if not isinstance(path_value, str):
                    continue
                path = pathlib.Path(path_value)
                if (
                    path_value.endswith(f"_{language_short}")
                    or language_short in path.parts
                ):
                    stem_to_id.setdefault(path.name, entry["id"])
                    id_to_filename.setdefault(entry["id"], f"{path.name}.txt")
        return stem_to_id, id_to_filename

    def build_readable_stem_to_localization_id_mapping(
        self,
    ) -> dict[str, id_types.LocalizationId]:
        """Map a readable file stem to its localization id for the instance language."""
        return self._build_readable_localization_maps()[0]

    def build_localization_id_to_readable_filename_mapping(
        self,
    ) -> dict[id_types.LocalizationId, id_types.ReadableFilename]:
        """Map a localization id to its readable filename for the instance language."""
        return self._build_readable_localization_maps()[1]

    @_warm_on_fork
    def build_localization_id_to_title_hash_mapping(
        self,
    ) -> dict[id_types.LocalizationId, id_types.TextMapHash]:
        """Map a localization id to its document title hash.

        Inverts the per-readable linear scan over DocumentExcelConfigData; first
        document wins per id, matching the original break-on-first-match behavior.
        """
        mapping: dict[id_types.LocalizationId, id_types.TextMapHash] = {}
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
    ) -> dict[id_types.BookSuitId, agd_types.BookSuitExcelConfigDataItem]:
        """Load BookSuitExcelConfigData.json keyed by suit id."""
        return self._index_unique(
            self._load_excel("BookSuitExcelConfigData.json"),
            lambda suit: suit["id"],
            duplicate_name="book suit ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_books_codex_excel_config_data(self) -> agd_types.BooksCodexExcelConfigData:
        """Load BooksCodexExcelConfigData.json."""
        return self._load_excel("BooksCodexExcelConfigData.json")

    @_warm_on_fork
    def build_book_series_mapping(
        self,
    ) -> dict[id_types.BookSuitId, list[id_types.ReadableFilename]]:
        """Group multi-volume book series to their ordered volume readable filenames.

        Active book-codex entries are grouped by their material's suit (``setID``)
        and ordered by ``sortOrder``; only suits with two or more volumes count as a
        series (single-volume and non-codex books stay standalone). Each volume
        resolves material id -> document -> localization -> readable filename (the
        material id and document id coincide for books). Raises if a volume claims a
        suit or readable that can't be resolved, surfacing the data gap rather than
        silently dropping the grouping.
        """
        materials = self.build_material_tracker()
        suits = self.load_book_suit_excel_config_data()
        documents = self.load_document_excel_config_data()
        readable_filenames = self.build_localization_id_to_readable_filename_mapping()

        grouped: dict[id_types.BookSuitId, list[id_types.ReadableFilename]] = {}
        for codex in sorted(
            self.load_books_codex_excel_config_data(),
            key=lambda codex: codex["sortOrder"],
        ):
            if codex["isDisuse"]:
                continue
            material_id = codex["materialId"]
            if (material := materials.get_untracked(material_id)) is None:
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
                        readable_filename
                        for loc_id in itertools.chain(
                            document["questIDList"],
                            document["questContentLocalizedId"],
                            document.get("CUSTOM_addlLocalID", []),
                        )
                        if (readable_filename := readable_filenames.get(loc_id))
                        is not None
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
    def build_material_tracker(self) -> MaterialTracker:
        """Load material Excel configuration data as MaterialTracker."""
        return MaterialTracker(self._load_excel("MaterialExcelConfigData.json"))

    @functools.lru_cache(maxsize=None)
    def load_achievement_excel_config_data(
        self,
    ) -> agd_types.AchievementExcelConfigData:
        """Load AchievementExcelConfigData.json."""
        return self._load_excel("AchievementExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_achievement_goal_excel_config_data(
        self,
    ) -> agd_types.AchievementGoalExcelConfigData:
        """Load AchievementGoalExcelConfigData.json."""
        return self._load_excel("AchievementGoalExcelConfigData.json")

    @_warm_on_fork
    def build_achievement_section_mapping(
        self,
    ) -> dict[
        id_types.AchievementGoalId,
        tuple[
            agd_types.AchievementGoalExcelConfigDataItem,
            list[agd_types.AchievementExcelConfigDataItem],
        ],
    ]:
        """Index active achievements by section in configured display order."""
        mapping = {
            section["id"]: (section, list[agd_types.AchievementExcelConfigDataItem]())
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

    @_warm_on_fork
    def build_talk_group_mapping(
        self,
    ) -> dict[tuple[talk_parsing.TalkGroupType, talk_parsing.TalkGroupId], str]:
        return self._get_talk_parser().talk_group_id_to_path

    @functools.lru_cache(maxsize=None)
    def build_free_group_mapping(self) -> dict[id_types.QuestId, list[str]]:
        """questId -> FreeGroup talk file paths attached by the id heuristic."""
        return self._get_talk_parser().free_group_quest_to_paths

    @functools.lru_cache(maxsize=None)
    def load_anecdote_excel_config_data(
        self,
    ) -> dict[id_types.AnecdoteId, agd_types.AnecdoteExcelConfigDataItem]:
        """Load AnecdoteExcelConfigData.json keyed by anecdote id."""
        data = cast(
            agd_types.AnecdoteExcelConfigData,
            deobfuscation.deobfuscate_anecdote_excel_config_data(
                self._load_excel("AnecdoteExcelConfigData.json")
            ),
        )
        return self._index_unique(
            data, lambda item: item["id"], duplicate_name="anecdote ID"
        )

    @functools.lru_cache(maxsize=None)
    def build_storyboard_quest_to_talk_ids_mapping(
        self,
    ) -> dict[id_types.QuestId, list[id_types.TalkId]]:
        """questId -> its ``TALK_STORYBOARD`` talk ids, sorted."""
        mapping: dict[id_types.QuestId, list[id_types.TalkId]] = {}
        for entry in self.load_talk_excel_config_data():
            if entry["loadType"] == "TALK_STORYBOARD":
                mapping.setdefault(entry["questId"], []).append(entry["id"])
        return {quest_id: sorted(ids) for quest_id, ids in mapping.items()}

    @functools.lru_cache(maxsize=None)
    def load_blossom_talk_excel_config_data(
        self,
    ) -> agd_types.BlossomTalkExcelConfigData:
        """Load BlossomTalkExcelConfigData.json (cleartext)."""
        return self._load_excel("BlossomTalkExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_blossom_refresh_excel_config_data(
        self,
    ) -> dict[id_types.BlossomRefreshId, agd_types.BlossomRefreshExcelConfigDataItem]:
        """Load BlossomRefreshExcelConfigData.json keyed by refresh id."""
        return self._index_unique(
            cast(
                agd_types.BlossomRefreshExcelConfigData,
                self._load_excel("BlossomRefreshExcelConfigData.json"),
            ),
            lambda item: item["id"],
            duplicate_name="blossom refresh ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_city_config_data(
        self,
    ) -> dict[id_types.CityId, agd_types.CityConfigDataItem]:
        """Load CityConfigData.json keyed by city id."""
        return self._index_unique(
            cast(agd_types.CityConfigData, self._load_excel("CityConfigData.json")),
            lambda item: item["cityId"],
            duplicate_name="city ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_coop_interaction_excel_config_data(
        self,
    ) -> agd_types.CoopInteractionExcelConfigData:
        """Load CoopInteractionExcelConfigData.json (cleartext)."""
        return self._load_excel("CoopInteractionExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_coop_chapter_excel_config_data(
        self,
    ) -> agd_types.CoopChapterExcelConfigData:
        """Load CoopChapterExcelConfigData.json (cleartext)."""
        return self._load_excel("CoopChapterExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def build_coop_story_mapping(self) -> dict[id_types.CoopStoryId, list[str]]:
        """coopStoryId -> its Coop talk file paths, sorted by local talk id."""
        return self._get_talk_parser().coop_story_to_paths

    @_warm_on_fork
    def build_coop_story_graph_mapping(
        self,
    ) -> dict[id_types.CoopStoryId, coop_graph.CoopStoryGraph]:
        """coopStoryId -> play-order node graph, from the BinOutput/Coop/*.json files."""
        graphs: dict[id_types.CoopStoryId, coop_graph.CoopStoryGraph] = {}
        for json_file in (self.agd_path / "BinOutput" / "Coop").glob("*.json"):
            raw_data = orjson.loads(json_file.read_bytes())
            data = deobfuscation.deobfuscate_coop_graph_data(raw_data)
            for story in data["coopInteractionMap"].values():
                graphs[story["id"]] = coop_graph.build_story_graph(story)
        return graphs

    @_warm_on_fork
    def build_hangout_quest_to_stories_mapping(
        self,
    ) -> dict[id_types.QuestId, list[id_types.CoopStoryId]]:
        """hangout questId -> its coopStoryIds that have talk files, sorted."""
        stories_with_files = self.build_coop_story_mapping()
        mapping: dict[id_types.QuestId, list[id_types.CoopStoryId]] = {}
        for entry in self.load_coop_interaction_excel_config_data():
            if (coop_story_id := entry["id"]) in stories_with_files:
                mapping.setdefault(entry["mainQuestId"], []).append(coop_story_id)
        return {quest_id: sorted(stories) for quest_id, stories in mapping.items()}

    @_warm_on_fork
    def build_coop_chapter_to_avatar_mapping(
        self,
    ) -> dict[id_types.ChapterId, id_types.AvatarId]:
        """Coop chapter id -> its primary character's avatar id."""
        return {
            chapter["id"]: chapter["avatarId"]
            for chapter in self.load_coop_chapter_excel_config_data()
        }

    @_warm_on_fork
    def build_avatar_id_to_name_mapping(self) -> dict[id_types.AvatarId, str]:
        """Avatar id -> localized character name (only avatars whose name resolves)."""
        text_map = self.build_text_map_tracker()
        return {
            avatar["id"]: name
            for avatar in self.load_avatar_excel_config_data()
            if (name := text_map.get_optional(avatar["nameTextMapHash"])) is not None
        }

    @_warm_on_fork
    def build_dialog_id_to_content_hash_mapping(
        self,
    ) -> dict[id_types.DialogId, id_types.TextMapHash]:
        """Dialog id -> talkContentTextMapHash, for resolving Coop choice prompts."""
        return {
            dialog_item["id"]: dialog_item["talkContentTextMapHash"]
            for dialog_item in self.load_dialog_excel_config_data()
        }

    @_warm_on_fork
    def build_quest_mapping(self) -> dict[id_types.QuestId, str]:
        """Build a mapping from quest ID to BinOutput/Quest file path.

        AGD retains stale hash-named duplicates of quests across builds, so when
        several files share an ID the canonically-named ``{id}.json`` wins.
        """
        quest_id_to_path: dict[id_types.QuestId, str] = {}

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
    def load_quest_excel_config_data(self) -> agd_types.QuestExcelConfigData:
        """Load the sub-quest master table."""
        return self._load_excel("QuestExcelConfigData.json")

    @_warm_on_fork
    def build_sub_quest_to_main_quest_mapping(
        self,
    ) -> dict[id_types.SubQuestId, id_types.QuestId]:
        """Sub-quest id -> its main quest id."""
        return {
            quest["subId"]: quest["mainId"]
            for quest in self.load_quest_excel_config_data()
        }

    @_warm_on_fork
    def build_talk_to_quest_mapping(self) -> dict[id_types.TalkId, id_types.QuestId]:
        """Talk id -> owning quest id (``TalkExcelConfigData.questId``).

        Checked against the quest BinOutput files' own talk lists: TalkExcel is
        a strict superset with no disagreements, so it is the single source.
        """
        return {
            talk_item["id"]: talk_item["questId"]
            for talk_item in self.load_talk_excel_config_data()
            if talk_item["questId"]
        }

    @_warm_on_fork
    def build_subtitle_stem_to_cutscene_ids_mapping(
        self,
    ) -> dict[str, list[id_types.CutsceneId]]:
        """Subtitle file stem -> ids of the cutscenes that play it.

        A video cutscene binds its subtitle track by ``subtitleId`` into
        ``LocalizationExcelConfigData``, whose per-language path stem equals the
        ``Subtitle/<lang>`` file stem, and names its videos after the stem minus
        the language suffix (per traveler variant). Both links are indexed: the
        localization one also covers subtitle files shared by both traveler
        variants, whose stems carry no ``_Boy``/``_Girl`` marker.
        """
        language_short = self.language_short
        localization_id_to_stems: dict[id_types.LocalizationId, list[str]] = {}
        for entry in self.load_localization_excel_config_data():
            for path_value in entry.values():
                if not isinstance(path_value, str):
                    continue
                path = pathlib.Path(path_value)
                if path.stem.endswith(f"_{language_short}"):
                    localization_id_to_stems.setdefault(entry["id"], []).append(
                        path.stem
                    )

        mapping: dict[str, set[id_types.CutsceneId]] = {}
        for json_file in sorted(
            (self.agd_path / "BinOutput" / "Cutscene").glob("*.json")
        ):
            cutscene_id = int(json_file.stem)
            for variant in orjson.loads(json_file.read_bytes()).values():
                assert isinstance(variant, dict), json_file
                if "videoConfig" not in variant:
                    continue
                video_config = cast(
                    agd_types.CutsceneVideoConfig, variant["videoConfig"]
                )
                for video_name in (
                    video_config["videoName"],
                    video_config["videoNameOther"],
                ):
                    if video_name:
                        stem = f"{pathlib.Path(video_name).stem}_{language_short}"
                        mapping.setdefault(stem, set()).add(cutscene_id)
                for localization_id in (
                    video_config.get("subtitleId"),
                    video_config.get("subtitleIdOther"),
                ):
                    if localization_id is None:
                        continue
                    for stem in localization_id_to_stems.get(localization_id, []):
                        mapping.setdefault(stem, set()).add(cutscene_id)
        return {stem: sorted(ids) for stem, ids in mapping.items()}

    @functools.lru_cache(maxsize=None)
    def _get_talk_parser(self) -> talk_parsing.TalkParser:
        return talk_parsing.TalkParser(self, self.load_talk_excel_config_data())

    def precompute_for_fork(self) -> None:
        """Pre-compute expensive mappings in parent process for inheritance via fork.

        This method should be called in the parent process before creating
        multiprocessing pools with fork start method to ensure child processes
        inherit the cached results. Warms every method marked with
        ``@_warm_on_fork`` (which transitively warms the loaders/parsers each one
        depends on), so adding a new fork-warmed method only requires the
        decorator, not a matching line here.
        """
        for method_name in _FORK_WARM_METHOD_NAMES:
            getattr(self, method_name)()

    @functools.lru_cache(maxsize=None)
    def load_talk_excel_config_data(self) -> agd_types.TalkExcelConfigData:
        """Load and return the raw talk Excel configuration data."""

        def _load_talk_file(filename: str) -> agd_types.TalkExcelConfigData:
            data = self._load_excel(filename)
            assert isinstance(data, list), filename
            return data

        split_names = sorted(
            name
            for name in self._list_file_names("ExcelBinOutput")
            if name.startswith("TalkExcelConfigData_") and name.endswith(".json")
        )
        if split_names:
            data = []
            for name in split_names:
                data.extend(_load_talk_file(name))
            return data

        try:
            return _load_talk_file("TalkExcelConfigData.json")
        except FileNotFoundError:
            raise FileNotFoundError(
                "TalkExcelConfigData.json or TalkExcelConfigData_*.json not found"
            )

    @functools.lru_cache(maxsize=None)
    def build_talk_tracker(self) -> TalkTracker:
        """Build the access-tracking TalkTracker with resolved talk file paths."""
        return TalkTracker(
            self.load_talk_excel_config_data(),
            self._get_talk_parser().talk_id_to_path,
        )

    @functools.lru_cache(maxsize=None)
    def load_talk_data(self, talk_file: str) -> agd_types.TalkData:
        """Load talk data from specified talk file."""
        file_path = self.agd_path / talk_file
        raw_data: dict[str, Any] = orjson.loads(file_path.read_bytes())
        data = deobfuscation.deobfuscate_talk_data(raw_data)
        return data  # type: ignore[return-value]

    @functools.lru_cache(maxsize=None)
    def load_talk_group_data(self, path: str) -> dict[str, Any]:
        """Load talk group data from specified talk file."""
        file_path = self.agd_path / path
        raw_data: dict[str, Any] = orjson.loads(file_path.read_bytes())
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
    def load_quest_data(self, quest_file: str) -> agd_types.QuestData:
        """Load quest data from specified quest file."""
        file_path = self.agd_path / quest_file
        raw_data: dict[str, Any] = orjson.loads(file_path.read_bytes())
        data = deobfuscation.deobfuscate_quest_data(raw_data)
        return data  # type: ignore[return-value]

    @_warm_on_fork
    def load_avatar_excel_config_data(self) -> agd_types.AvatarExcelConfigData:
        """Load avatar Excel configuration data."""
        return self._load_excel("AvatarExcelConfigData.json")

    @_warm_on_fork
    def load_avatar_skill_depot_excel_config_data(
        self,
    ) -> dict[id_types.SkillDepotId, agd_types.AvatarSkillDepotExcelConfigDataItem]:
        """Load avatar skill-depot data as a dict keyed by depot id."""
        return self._index_unique(
            self._load_excel("AvatarSkillDepotExcelConfigData.json"),
            lambda item: item["id"],
            duplicate_name="skill depot ID",
        )

    @_warm_on_fork
    def load_avatar_talent_excel_config_data(
        self,
    ) -> dict[id_types.TalentId, agd_types.AvatarTalentExcelConfigDataItem]:
        """Load constellation (talent) data as a dict keyed by talent id."""
        return self._index_unique(
            self._load_excel("AvatarTalentExcelConfigData.json"),
            lambda item: item["talentId"],
            duplicate_name="talent ID",
        )

    @_warm_on_fork
    def load_avatar_skill_excel_config_data(
        self,
    ) -> dict[id_types.SkillId, agd_types.AvatarSkillExcelConfigDataItem]:
        """Load avatar skill data as a dict keyed by skill id."""
        return self._index_unique(
            self._load_excel("AvatarSkillExcelConfigData.json"),
            lambda item: item["id"],
            duplicate_name="skill ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_fetter_story_excel_config_data(
        self,
    ) -> agd_types.FetterStoryExcelConfigData:
        """Load fetter story Excel configuration data."""
        return self._load_excel("FetterStoryExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_fetters_excel_config_data(self) -> agd_types.FettersExcelConfigData:
        """Load fetters Excel configuration data."""
        return self._load_excel("FettersExcelConfigData.json")

    @_warm_on_fork
    def load_animal_codex_excel_config_data(
        self,
    ) -> dict[id_types.AnimalCodexId, agd_types.AnimalCodexExcelConfigDataItem]:
        """Load AnimalCodexExcelConfigData.json keyed by codex entry id."""
        return self._index_unique(
            self._load_excel("AnimalCodexExcelConfigData.json"),
            lambda entry: entry["id"],
            duplicate_name="animal codex ID",
        )

    @_warm_on_fork
    def load_monster_describe_excel_config_data(
        self,
    ) -> dict[
        id_types.CreatureDescribeId, agd_types.MonsterDescribeExcelConfigDataItem
    ]:
        """Load MonsterDescribeExcelConfigData.json keyed by describe id."""
        return self._index_unique(
            self._load_excel("MonsterDescribeExcelConfigData.json"),
            lambda entry: entry["id"],
            duplicate_name="monster describe ID",
        )

    @_warm_on_fork
    def load_monster_title_excel_config_data(
        self,
    ) -> dict[id_types.MonsterTitleId, agd_types.MonsterTitleExcelConfigDataItem]:
        """Load MonsterTitleExcelConfigData.json keyed by title id."""
        return self._index_unique(
            self._load_excel("MonsterTitleExcelConfigData.json"),
            lambda entry: entry["titleID"],
            duplicate_name="monster title ID",
        )

    @_warm_on_fork
    def load_monster_special_name_excel_config_data(
        self,
    ) -> agd_types.MonsterSpecialNameExcelConfigData:
        """Load MonsterSpecialNameExcelConfigData.json."""
        return self._load_excel("MonsterSpecialNameExcelConfigData.json")

    @_warm_on_fork
    def load_animal_describe_excel_config_data(
        self,
    ) -> dict[id_types.CreatureDescribeId, agd_types.AnimalDescribeExcelConfigDataItem]:
        """Load AnimalDescribeExcelConfigData.json keyed by describe id."""
        return self._index_unique(
            self._load_excel("AnimalDescribeExcelConfigData.json"),
            lambda entry: entry["id"],
            duplicate_name="animal describe ID",
        )

    @_warm_on_fork
    def load_main_quest_excel_config_data(
        self,
    ) -> dict[id_types.QuestId, agd_types.MainQuestExcelConfigDataItem]:
        """Load main quest Excel config data as a dict keyed by quest id."""
        return self._index_unique(
            self._load_excel("MainQuestExcelConfigData.json"),
            lambda quest: quest["id"],
            duplicate_name="main quest ID",
        )

    @functools.lru_cache(maxsize=None)
    def load_chapter_excel_config_data(
        self,
    ) -> dict[id_types.ChapterId, agd_types.ChapterExcelConfigDataItem]:
        """Load ChapterExcelConfigData.json keyed by chapter id."""
        return self._index_unique(
            self._load_excel("ChapterExcelConfigData.json"),
            lambda chapter: chapter["id"],
            duplicate_name="chapter ID",
        )

    def _build_npc_id_to_name(
        self, text_map: TextMapTracker
    ) -> dict[id_types.NpcId, str]:
        """Build NPC ID -> name using the given text map."""
        return {
            npc["id"]: name
            for npc in self.load_npc_excel_config_data()
            if (name := text_map.get_optional(npc["nameTextMapHash"])) is not None
        }

    @_warm_on_fork
    def build_npc_id_to_name_mapping(self) -> dict[id_types.NpcId, str]:
        """Get cached mapping from NPC ID to name."""
        return self._build_npc_id_to_name(self.build_text_map_tracker())

    @_warm_on_fork
    def build_npc_id_to_source_name_mapping(self) -> dict[id_types.NpcId, str]:
        """NPC ID -> CHS (source) name, for language-independent test/hidden filtering.

        Dev markers like ``$HIDDEN``/``(test)`` only exist in the CHS name text.
        """
        return self._build_npc_id_to_name(self.build_source_text_map_tracker())

    @functools.lru_cache(maxsize=None)
    def load_new_activity_excel_config_data(
        self,
    ) -> dict[id_types.ActivityId, agd_types.NewActivityExcelConfigDataItem]:
        """Load NewActivityExcelConfigData.json keyed by activity id."""
        return self._index_unique(
            self._load_excel("NewActivityExcelConfigData.json"),
            lambda entry: entry["activityId"],
            duplicate_name="activity ID",
        )

    @_warm_on_fork
    def build_activity_id_to_name_mapping(self) -> dict[id_types.ActivityId, str]:
        """Activity id -> localized activity name (unresolvable names omitted)."""
        text_map = self.build_text_map_tracker()
        return {
            activity_id: name
            for activity_id, entry in self.load_new_activity_excel_config_data().items()
            if (name := text_map.get_optional(entry["nameTextMapHash"])) is not None
        }

    @functools.lru_cache(maxsize=None)
    def load_home_world_npc_excel_config_data(
        self,
    ) -> agd_types.HomeWorldNPCExcelConfigData:
        """Load HomeWorldNPCExcelConfigData.json."""
        return self._load_excel("HomeWorldNPCExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_role_combat_tarot_avatar_excel_config_data(
        self,
    ) -> agd_types.RoleCombatTarotAvatarExcelConfigData:
        """Load RoleCombatTarotAvatarExcelConfigData.json."""
        return self._load_excel("RoleCombatTarotAvatarExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_gcg_week_level_excel_config_data(
        self,
    ) -> agd_types.GCGWeekLevelExcelConfigData:
        """Load GCGWeekLevelExcelConfigData.json."""
        return self._load_excel("GCGWeekLevelExcelConfigData.json")

    @_warm_on_fork
    def build_npc_id_to_game_mode_mapping(
        self,
    ) -> dict[id_types.NpcId, localization.GameMode]:
        """NPC id -> game mode, for mode-dedicated NPC variants.

        Serenitea Pot companions, Imaginarium Theater cast, and TCG week-level
        opponents each get a dedicated NPC id whose NpcGroup talks hold that
        mode's dialogue. The master NPC table carries no mode marker; membership
        in the per-mode excel is the marker.
        """
        mode_npc_ids: list[tuple[localization.GameMode, Iterable[id_types.NpcId]]] = [
            (
                localization.GameMode.SERENITEA_POT,
                (e["npcID"] for e in self.load_home_world_npc_excel_config_data()),
            ),
            (
                localization.GameMode.IMAGINARIUM_THEATER,
                (
                    e["npcId"]
                    for e in self.load_role_combat_tarot_avatar_excel_config_data()
                ),
            ),
            (
                localization.GameMode.GENIUS_INVOKATION_TCG,
                (e["npcId"] for e in self.load_gcg_week_level_excel_config_data()),
            ),
        ]
        mapping: dict[id_types.NpcId, localization.GameMode] = {}
        for mode, npc_ids in mode_npc_ids:
            for npc_id in npc_ids:
                if npc_id == 0:
                    continue
                if (existing := mapping.get(npc_id)) is not None and existing != mode:
                    raise ValueError(
                        f"NPC {npc_id} claimed by both {existing} and {mode}"
                    )
                mapping[npc_id] = mode
        return mapping

    @_warm_on_fork
    def build_dialog_id_to_role_name_hash_mapping(
        self,
    ) -> dict[id_types.DialogId, id_types.TextMapHash]:
        """Get cached mapping from dialog ID to talkRoleNameTextMapHash."""
        dialog_data = self.load_dialog_excel_config_data()

        dialog_id_to_role_hash: dict[id_types.DialogId, id_types.TextMapHash] = {}
        for dialog_item in dialog_data:
            dialog_id = dialog_item["id"]
            role_name_hash = dialog_item["talkRoleNameTextMapHash"]
            dialog_id_to_role_hash[dialog_id] = role_name_hash

        return dialog_id_to_role_hash

    @functools.lru_cache(maxsize=None)
    def load_reliquary_set_excel_config_data(
        self,
    ) -> agd_types.ReliquarySetExcelConfigData:
        """Load ReliquarySetExcelConfigData.json."""
        return self._load_excel("ReliquarySetExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_reliquary_excel_config_data(self) -> agd_types.ReliquaryExcelConfigData:
        """Load ReliquaryExcelConfigData.json."""
        return self._load_excel("ReliquaryExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_equip_affix_excel_config_data(self) -> agd_types.EquipAffixExcelConfigData:
        """Load EquipAffixExcelConfigData.json."""
        return self._load_excel("EquipAffixExcelConfigData.json")

    @functools.lru_cache(maxsize=None)
    def load_weapon_excel_config_data(
        self,
    ) -> dict[id_types.WeaponId, agd_types.WeaponExcelConfigDataItem]:
        """Load WeaponExcelConfigData.json as a dict mapping weapon ID to weapon."""
        return self._index_unique(
            self._load_excel("WeaponExcelConfigData.json"),
            lambda weapon: weapon["id"],
            duplicate_name="weapon ID",
        )

    @functools.lru_cache(maxsize=None)
    def build_readables_tracker(self) -> ReadablesTracker:
        """Get ReadablesTracker for tracking access to readable files."""
        return ReadablesTracker(
            self.list_readable_filenames(),
            self.agd_path / "Readable" / self.language_short,
        )

    def build_scope_trackers(
        self,
    ) -> dict[tracking.TrackerKind, tracking.IdTracker[Any]]:
        """The trackers a ``tracking_scope`` observes, keyed by kind.

        The single registration point for per-item tracked resources: both
        ``tracking_scope`` and the run's unused-stats aggregation consume this.
        Adding a resource is a new ``TrackerKind`` member plus a line here.
        """
        return {
            tracking.TrackerKind.TEXT_MAP: self.build_text_map_tracker(),
            tracking.TrackerKind.TALK: self.build_talk_tracker(),
            tracking.TrackerKind.READABLES: self.build_readables_tracker(),
        }

    def tracking_scope(
        self, *, item_type: str, item_key: str
    ) -> tracking.TrackingScope:
        """Open a scope collecting access + issue side-data for one item.

        Enter it around processing a single renderable; read the accessed ids and
        recorded issues off the yielded scope after the block.
        """
        return tracking.TrackingScope(
            self.build_scope_trackers(), item_type=item_type, item_key=item_key
        )
