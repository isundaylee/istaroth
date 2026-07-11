"""First-seen game-version index for AGD source ids.

Maps raw AGD source ids (main quests, talks, readables, ...) to the game
version in which they first appeared. The index is folded from the per-version
delta files under ``first_seen/`` in the ``text/`` submodule, each listing the
ids newly seen in that version's AGD snapshot (built by
``scripts/agd_build_first_seen.py`` from the AGD git history and committed
alongside the corpus regenerations they stamp).
"""

from __future__ import annotations

import enum
import pathlib
from typing import Any, Iterable

import attrs

from istaroth import json_utils
from istaroth.agd import repo

DATA_DIR = pathlib.Path(__file__).parent.parent.parent / "text" / "first_seen"


class SourceDomain(enum.StrEnum):
    """Raw AGD data domain a source id belongs to."""

    MAIN_QUEST = "main_quest"
    TALK = "talk"
    READABLE = "readable"
    SUBTITLE = "subtitle"
    MATERIAL = "material"
    WEAPON = "weapon"
    ACHIEVEMENT = "achievement"
    AVATAR = "avatar"
    ARTIFACT_SET = "artifact_set"
    ANIMAL_CODEX = "animal_codex"


STR_KEYED_DOMAINS = frozenset({SourceDomain.READABLE, SourceDomain.SUBTITLE})
"""Domains keyed by language-neutral filename stems; the rest are int-keyed."""


@attrs.frozen
class SourceId:
    """A raw AGD source id with its domain."""

    domain: SourceDomain
    key: int | str


_LANGUAGE_SUFFIXES = frozenset(
    {
        "CHS",
        "CHT",
        "DE",
        "EN",
        "ES",
        "FR",
        "ID",
        "IT",
        "JP",
        "KR",
        "PT",
        "RU",
        "TH",
        "TR",
        "VI",
    }
)


def strip_language_suffix(stem: str) -> str:
    """Strip the trailing ``_<LANG>`` token, if any, from a readable/subtitle stem.

    CHS files mostly carry no language suffix while other languages do, so the
    language-neutral key is the stem with the suffix dropped when present.
    """
    base, sep, suffix = stem.rpartition("_")
    return base if sep and suffix in _LANGUAGE_SUFFIXES else stem


def readable_source_id(readable_filename: str) -> SourceId:
    """Source id for a readable filename (e.g. ``Book100_EN.txt``)."""
    return SourceId(
        SourceDomain.READABLE,
        strip_language_suffix(pathlib.PurePosixPath(readable_filename).stem),
    )


def subtitle_source_id(subtitle_path: str) -> SourceId:
    """Source id for a subtitle path (e.g. ``Subtitle/CHS/Foo_CHS.srt``)."""
    return SourceId(
        SourceDomain.SUBTITLE,
        strip_language_suffix(pathlib.PurePosixPath(subtitle_path).stem),
    )


def version_sort_key(version: str) -> tuple[int, ...]:
    """Sort key for game version strings like ``"5.8"``."""
    return tuple(int(part) for part in version.split("."))


@attrs.frozen
class FirstSeenIndex:
    """Folded ``{domain: {source id: first version}}`` lookup."""

    _versions: dict[SourceDomain, dict[int | str, str]]

    @classmethod
    def load(cls, data_dir: pathlib.Path = DATA_DIR) -> "FirstSeenIndex":
        """Fold all per-version delta files in version order."""
        delta_paths = sorted(
            data_dir.glob("*.json"), key=lambda p: version_sort_key(p.stem)
        )
        if not delta_paths:
            raise FileNotFoundError(f"No first-seen delta files in {data_dir}")
        versions: dict[SourceDomain, dict[int | str, str]] = {
            domain: {} for domain in SourceDomain
        }
        for path in delta_paths:
            data = json_utils.loads(path.read_bytes())
            version = data["version"]
            if version != path.stem:
                raise ValueError(
                    f"Version {version!r} in {path.name} does not match filename"
                )
            for domain_name, keys in data["new"].items():
                mapping = versions[SourceDomain(domain_name)]
                for key in keys:
                    if key in mapping:
                        raise ValueError(
                            f"Source id {key!r} in {domain_name} listed by both "
                            f"version {mapping[key]} and {version}"
                        )
                    mapping[key] = version
        return cls(versions)

    def resolve(self, source_ids: Iterable[SourceId]) -> tuple[str, str]:
        """Return (min, max) first-seen version over the given source ids."""
        resolved = []
        for source_id in source_ids:
            if (version := self._versions[source_id.domain].get(source_id.key)) is None:
                raise KeyError(
                    f"{source_id.domain.value} id {source_id.key!r} not in the "
                    "first-seen index; if it is new, rerun "
                    "scripts/agd_build_first_seen.py"
                )
            resolved.append(version)
        if not resolved:
            raise ValueError("Cannot resolve versions for empty source ids")
        resolved.sort(key=version_sort_key)
        return resolved[0], resolved[-1]


_EXCEL_DOMAINS: dict[SourceDomain, tuple[str, str]] = {
    SourceDomain.MAIN_QUEST: ("MainQuestExcelConfigData.json", "id"),
    SourceDomain.MATERIAL: ("MaterialExcelConfigData.json", "id"),
    SourceDomain.WEAPON: ("WeaponExcelConfigData.json", "id"),
    SourceDomain.ACHIEVEMENT: ("AchievementExcelConfigData.json", "id"),
    SourceDomain.AVATAR: ("AvatarExcelConfigData.json", "id"),
    SourceDomain.ARTIFACT_SET: ("ReliquarySetExcelConfigData.json", "setId"),
    SourceDomain.ANIMAL_CODEX: ("AnimalCodexExcelConfigData.json", "id"),
}


def _row_id(row: dict[str, Any], id_key: str) -> int:
    # Field-name style varies by era (and by file within one era): 1.x dumps
    # use PascalCase ("Id"/"SetId"), some ~2.7-3.x dumps underscore-prefixed
    # camelCase ("_id"), current dumps plain camelCase.
    for key in (id_key, id_key[0].upper() + id_key[1:], f"_{id_key}"):
        if key in row:
            return int(row[key])
    raise KeyError(f"No {id_key!r} field in excel row: {sorted(row)[:5]}...")


def scan_snapshot(*, data_repo: repo.DataRepo) -> dict[SourceDomain, set[int | str]]:
    """Enumerate all source ids present in one AGD build.

    Uses the data repo's language for the filename-keyed domains; scan (and
    union) both languages for full coverage. Subtitles only exist from 1.6
    onward, so a missing Subtitle dir yields an empty set rather than erroring.
    """
    present: dict[SourceDomain, set[int | str]] = {
        domain: {_row_id(row, id_key) for row in data_repo.load_excel_raw(filename)}
        for domain, (filename, id_key) in _EXCEL_DOMAINS.items()
    }
    present[SourceDomain.TALK] = {
        _row_id(row, "id")
        for name in data_repo.talk_excel_file_names()
        for row in data_repo.load_excel_raw(name)
    }
    readable_names = data_repo.list_readable_filenames()
    if not readable_names:
        raise FileNotFoundError(f"No readable files for {data_repo.language_short}")
    present[SourceDomain.READABLE] = {
        strip_language_suffix(pathlib.PurePosixPath(name).stem)
        for name in readable_names
    }
    present[SourceDomain.SUBTITLE] = {
        strip_language_suffix(pathlib.PurePosixPath(name).stem)
        for name in data_repo.list_subtitle_names()
    }
    return present
