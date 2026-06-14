"""Talk parsing utilities for processing AGD talk files."""

from __future__ import annotations

import collections
import logging
import pathlib
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    NamedTuple,
    TypeAlias,
    assert_never,
    cast,
)

if TYPE_CHECKING:
    from istaroth.agd import repo, types

logger = logging.getLogger(__name__)


TalkGroupType: TypeAlias = Literal["ActivityGroup", "GadgetGroup", "NpcGroup"]


def _free_group_quest_id(talk_id: str) -> str:
    """Owning quest id for a FreeGroup talk, inferred from its talkId numbering.

    FreeGroup talkIds follow ``<questId><index>``; dropping the trailing two-digit
    index yields the quest id, except for the ``<questId>99<index>`` ambient-talk
    bucket where two more digits are dropped.
    """
    base = talk_id[:-2]
    if len(base) >= 6 and base.endswith("99"):
        base = base[:-2]
    return base


class _TalkSignature(NamedTuple):
    """Content fingerprint of a talk file used to resolve talkId collisions."""

    dialogs: tuple[tuple[int, int], ...]
    """The (dialog id, content hash) sequence, for byte-identity checks."""
    text_ids: frozenset[int]
    """Dialog ids whose content hash resolves to real text."""


class TalkParser:
    """Parser for talk-related files in AGD."""

    _BAD_TALK_PATHS: ClassVar[list[pathlib.Path]] = [
        pathlib.Path("BinOutput/Talk/Coop/1900102_10.json"),
        pathlib.Path("BinOutput/Talk/Gadget/6800002.json"),
        pathlib.Path("BinOutput/Talk/Gadget/80045.json"),
        pathlib.Path("BinOutput/Talk/Npc/7401203.json"),
        pathlib.Path("BinOutput/Talk/Npc/7401204.json"),
        pathlib.Path("BinOutput/Talk/Npc/7401205.json"),
        pathlib.Path("BinOutput/Talk/NpcOther/12634.json"),
        pathlib.Path("BinOutput/Talk/Quest/80046.json"),
        pathlib.Path("BinOutput/Talk/Quest/GlobalDialog.json"),
        pathlib.Path("BinOutput/Talk/BlossomGroup/5900009.json"),
    ]

    _EXCLUDE_DIRECTORIES: ClassVar[set[str]] = {"BlossomGroup"}

    # FreeGroup holds Lua-invoked "free talks" with no reference-graph linkage in
    # the dump. They are not registered as resolvable talkIds (their ids collide
    # with other talks); instead each is attached to its owning quest by the
    # talkId-numbering heuristic and rendered in a separate quest section.
    _FREE_GROUP_DIRECTORY: ClassVar[str] = "FreeGroup"

    _GROUP_DIRECTORIES: ClassVar[set[str]] = {
        "ActivityGroup",
        "GadgetGroup",
        "NpcGroup",
        "StoryboardGroup",
    }

    def __init__(
        self, data_repo: repo.DataRepo, talk_excel_data: types.TalkExcelConfigData
    ) -> None:
        self.agd_path = data_repo.agd_path

        self.talk_id_to_path = dict[str, str]()
        self.talk_group_id_to_path = dict[tuple[TalkGroupType, str], str]()

        # talkId -> candidate file paths; collapsed to one path after the scan.
        self._talk_candidates: dict[str, list[str]] = collections.defaultdict(list)

        # questId -> FreeGroup talk paths, attached by the talkId-numbering
        # heuristic; collected as (talkId, path) then sorted by talkId below.
        _free_group: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
        self.free_group_quest_to_paths = dict[str, list[str]]()

        invalid_paths = dict[pathlib.Path, str]()

        # Scan Talk directory and all subdirectories for JSON files
        for json_file in (self.agd_path / "BinOutput" / "Talk").glob("**/*.json"):
            relative_path = json_file.relative_to(self.agd_path)

            if relative_path in self._BAD_TALK_PATHS:
                logger.warning("Known bad talk file %s", relative_path)
                continue

            data = data_repo.load_talk_group_data(relative_path.as_posix())

            subdir = relative_path.parts[2]

            try:
                if subdir in self._EXCLUDE_DIRECTORIES:
                    continue
                elif subdir == self._FREE_GROUP_DIRECTORY:
                    self._handle_free_group_file(relative_path, data, _free_group)
                elif subdir in self._GROUP_DIRECTORIES:
                    self._handle_talk_group_file(
                        relative_path, cast(TalkGroupType, relative_path.parts[2]), data
                    )
                elif self._is_talk_file(relative_path, data):
                    self._handle_talk_file(relative_path, data)
                elif "activityId" in data:
                    self._handle_talk_group_file(relative_path, "ActivityGroup", data)
                elif "npcId" in data:
                    self._handle_talk_group_file(relative_path, "NpcGroup", data)
                else:
                    raise RuntimeError(f"Unknown talk file type {relative_path}")
            except Exception as e:
                logger.warning("Error parsing talk file %s: %s", relative_path, e)
                invalid_paths[relative_path] = str(e)

        if invalid_paths:
            raise ValueError(
                f"{len(invalid_paths)} invalid talk file paths: {invalid_paths}"
            )

        for quest_id, talks in _free_group.items():
            self.free_group_quest_to_paths[quest_id] = [
                path for _, path in sorted(talks)
            ]

        self._resolve_talk_candidates(data_repo, self._init_dialog_map(talk_excel_data))

    def _handle_talk_group_file(
        self,
        relative_path: pathlib.Path,
        group_type: TalkGroupType,
        data: dict[str, Any],
    ) -> None:
        if not data["talks"]:
            return

        match group_type:
            case "ActivityGroup" | "NpcGroup" | "StoryboardGroup":
                id = (
                    data.get("activityId")
                    or data.get("npcId")
                    or data.get("storyboardId")
                )
            case "GadgetGroup":
                id = data.get("configId")
            case _:
                assert_never(group_type)

        assert isinstance(id, int), relative_path
        key = (group_type, str(id))
        if key in self.talk_group_id_to_path:
            logger.warning(
                "Ignoring %s already present as %s in %s",
                relative_path,
                key,
                self.talk_group_id_to_path[key],
            )
            return

        self.talk_group_id_to_path[key] = (relative_path).as_posix()

    def _handle_talk_file(
        self, relative_path: pathlib.Path, talk_data: dict[str, Any]
    ) -> None:
        self._talk_candidates[str(talk_data["talkId"])].append(relative_path.as_posix())

    @staticmethod
    def _handle_free_group_file(
        relative_path: pathlib.Path,
        talk_data: dict[str, Any],
        free_group: dict[str, list[tuple[int, str]]],
    ) -> None:
        """Attach a FreeGroup talk to its owning quest by talkId numbering."""
        talk_id = int(talk_data["talkId"])
        free_group[_free_group_quest_id(str(talk_id))].append(
            (talk_id, relative_path.as_posix())
        )

    @staticmethod
    def _init_dialog_map(talk_excel_data: types.TalkExcelConfigData) -> dict[str, int]:
        """Map talkId -> initDialog for config entries with a nonzero one."""
        return {
            str(entry["id"]): init_dialog
            for entry in talk_excel_data
            if (init_dialog := entry["initDialog"])
        }

    def _resolve_talk_candidates(
        self, data_repo: repo.DataRepo, init_dialogs: dict[str, int]
    ) -> None:
        """Collapse per-talkId candidate files into a single authoritative path.

        Several files can share a ``talkId`` (e.g. a canonical and a hash-named
        copy, distinct Coop hangouts reusing a local id, or the same id in
        ``Quest`` and ``Npc``). Resolution, in order: (1) the file whose
        ``initDialog`` dialog actually carries text, when exactly one qualifies;
        (2) when the text-bearing files are equivalent, the canonically-named
        ``<talkId>.json`` copy over a hash-named one; (3) otherwise the talkId
        is genuinely ambiguous and is dropped. Dialogs
        are loaded (deobfuscated) only for colliding ids, which also warms the
        cache for later rendering.
        """
        text_map = data_repo.load_text_map()
        stats = collections.Counter[str]()
        for talk_id, candidates in self._talk_candidates.items():
            if len(candidates) == 1:
                self.talk_id_to_path[talk_id] = candidates[0]
                continue

            stats["collision"] += 1
            signatures: dict[str, _TalkSignature] = {}
            for p in candidates:
                if (sig := self._talk_signature(data_repo, text_map, p)) is None:
                    logger.warning("Skipping talk file %s with no dialogList", p)
                else:
                    signatures[p] = sig
            if not (usable := [p for p in candidates if p in signatures]):
                stats["dropped"] += 1
                continue

            init_dialog = init_dialogs.get(talk_id)
            if init_dialog is not None and (
                len(
                    eligible := [
                        p for p in usable if init_dialog in signatures[p].text_ids
                    ]
                )
                == 1
            ):
                self.talk_id_to_path[talk_id] = eligible[0]
                stats["by_init_dialog"] += 1
                continue

            textful = [p for p in usable if signatures[p].text_ids]
            if len({signatures[p].dialogs for p in textful}) <= 1:
                # Equivalent content (byte-identical or all empty): prefer the
                # canonically-named `<talkId>.json` copy over a hash-named one.
                # They share the same (id, content-hash) signature but can come
                # from different builds, and the hash-named copy may use a
                # newer/unmapped obfuscation key (e.g. a missing nextDialogs),
                # so the canonical name is the safer authoritative pick.
                self.talk_id_to_path[talk_id] = min(
                    textful or usable,
                    key=lambda p: (pathlib.Path(p).stem != talk_id, p),
                )
                stats["deduped"] += 1
                continue

            stats["dropped"] += 1
            log = logger.warning if init_dialog is not None else logger.debug
            log(
                "Dropping ambiguous talkId %s with conflicting content: %s",
                talk_id,
                sorted(usable),
            )

        if stats["collision"]:
            logger.info(
                "Talk collisions: %d by initDialog, %d deduped, %d dropped",
                stats["by_init_dialog"],
                stats["deduped"],
                stats["dropped"],
            )

    @staticmethod
    def _talk_signature(
        data_repo: repo.DataRepo, text_map: repo.TextMapTracker, talk_path: str
    ) -> _TalkSignature | None:
        """Content signature of a candidate file, or None if it has no dialogList.

        ``dialogs`` is the raw (id, content-hash) sequence for byte-identity
        checks; ``text_ids`` are the dialog ids whose hash resolves to real text.
        """
        data = data_repo.load_talk_data(talk_path)
        try:
            dialogs = data["dialogList"]
        except KeyError:
            return None
        return _TalkSignature(
            dialogs=tuple(
                (d["id"], d.get("talkContentTextMapHash", 0)) for d in dialogs
            ),
            text_ids=frozenset(
                d["id"]
                for d in dialogs
                if text_map.has(str(d.get("talkContentTextMapHash", "")))
            ),
        )

    @staticmethod
    def _is_talk_file(relative_path: pathlib.Path, talk_data: Any) -> bool:
        """Check if a file is a valid talk file."""

        # Check some invariants
        try:
            assert isinstance(talk_data, dict), relative_path

            has_talk_id = "talkId" in talk_data
            has_activity_id = "activityId" in talk_data
            has_npc_id = "npcId" in talk_data
            assert (
                sum(1 if t else 0 for t in [has_talk_id, has_activity_id, has_npc_id])
                <= 1
            )
        except AssertionError:
            logger.warning("Invariant-violating talk file %s", relative_path)
            return False

        return has_talk_id
