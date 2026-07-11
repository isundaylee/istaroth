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

from istaroth import caching

if TYPE_CHECKING:
    from istaroth.agd import agd_types, id_types, repo

logger = logging.getLogger(__name__)


TalkGroupType: TypeAlias = Literal["ActivityGroup", "GadgetGroup", "NpcGroup"]

TalkGroupId: TypeAlias = str
"""Str half of a talk-group key; pairs with ``TalkGroupType``.

For most types this is a single AGD id (NPC id, activity id, ...). For
``GadgetGroup`` it is the composite ``"<configId>_<groupId>"`` form: a
``configId`` alone is not unique across GadgetGroup files (issue #186), so the
``groupId`` disambiguator from the file's own top-level field is folded in.
"""

# ``GadgetGroupId`` always ships as a 9-digit int (min 111101079), so
# ``configId * 10**GADGET_GROUP_ID_DIGITS + groupId`` is collision-free and fits
# both ``TextMetadata.id`` and JS ``Number.MAX_SAFE_INTEGER`` (max composite
# ~8.4e14 vs ~9.0e15). Used to derive a stable int id for the rendered file.
_GADGET_GROUP_ID_DIGITS = 9


def gadget_group_composite_id(
    config_id: id_types.GadgetConfigId, group_id: id_types.GadgetGroupId
) -> int:
    """Stable int id for a GadgetGroup from its ``(configId, groupId)`` pair."""
    return config_id * 10**_GADGET_GROUP_ID_DIGITS + group_id


def parse_gadget_group_composite_id(
    composite_id: str,
) -> tuple[id_types.GadgetConfigId, id_types.GadgetGroupId]:
    """Inverse of the ``"<configId>_<groupId>"`` composite-key string form."""
    config_str, _, group_str = composite_id.partition("_")
    return int(config_str), int(group_str)


# ActivityGroup activity ids overlap NpcGroup npc ids (issue #294) — e.g. 2001
# is both an activity and an NPC — so ActivityGroup rendered files offset their
# metadata id above the NpcGroup range (max ~2e6) and below the GadgetGroup
# composite range (min ~1e12). NpcGroup, the vast majority, keeps the raw id.
_ACTIVITY_GROUP_METADATA_ID_OFFSET = 10**9


def activity_group_metadata_id(activity_id: id_types.ActivityId) -> int:
    """Stable int id for an ActivityGroup rendered file, disjoint from npc ids."""
    return _ACTIVITY_GROUP_METADATA_ID_OFFSET + activity_id


def _free_group_quest_id(talk_id: str) -> id_types.QuestId | None:
    """Owning quest id for a FreeGroup talk, inferred from its talkId numbering.

    FreeGroup talkIds follow ``<questId><index>``; dropping the trailing two-digit
    index yields the quest id, except for the ``<questId>99<index>`` ambient-talk
    bucket where two more digits are dropped. Takes the talk id in its ``str``
    form (digit-slicing) and returns the ``int`` quest id, or None when the id is
    too short to contain one (degenerate FreeGroup files like ``7.json``).
    """
    base = talk_id[:-2]
    if len(base) >= 6 and base.endswith("99"):
        base = base[:-2]
    return int(base) if base else None


class _TalkSignature(NamedTuple):
    """Content fingerprint of a talk file used to resolve talkId collisions."""

    dialogs: tuple[tuple[int, int], ...]
    """The (dialog id, content hash) sequence, for byte-identity checks."""
    dialog_texts: tuple[tuple[int, str], ...]
    """The (dialog id, resolved text) sequence for hashes that resolve."""
    text_counts: collections.Counter[str]
    """Resolved text multiplicities, independent of remapped dialog ids."""
    text_dialogs: frozenset[tuple[int, int]]
    """(dialog id, content hash) pairs whose hash resolves to real text."""
    text_ids: frozenset[int]
    """Dialog ids whose content hash resolves to real text."""


class TalkParser:
    """Parser for talk-related files in AGD."""

    _BAD_TALK_PATHS: ClassVar[list[pathlib.Path]] = [
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

    # Coop holds hangout dialogue named `<coopStoryId>_<localTalkId>.json`, whose
    # local talkId collides across stories. They are not registered as resolvable
    # talkIds; the Hangouts renderable consumes them directly via the Coop story
    # graph, grouped here per coopStoryId.
    _COOP_DIRECTORY: ClassVar[str] = "Coop"

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
        self, data_repo: repo.DataRepo, talk_excel_data: agd_types.TalkExcelConfigData
    ) -> None:
        self.agd_path = data_repo.agd_path

        self.talk_id_to_path: dict[id_types.TalkId, str] = {}
        self.talk_group_id_to_path: dict[tuple[TalkGroupType, TalkGroupId], str] = {}
        self._talk_group_candidates: dict[tuple[TalkGroupType, TalkGroupId], list[str]]
        self._talk_group_candidates = collections.defaultdict(list)

        # coopStoryId -> Coop talk file paths, sorted by local talk id below.
        _coop_group: dict[id_types.CoopStoryId, list[tuple[int, str]]] = (
            collections.defaultdict(list)
        )
        self.coop_story_to_paths: dict[id_types.CoopStoryId, list[str]] = {}

        # talkId -> candidate file paths; collapsed to one path after the scan.
        self._talk_candidates: dict[id_types.TalkId, list[str]] = (
            collections.defaultdict(list)
        )

        # questId -> FreeGroup talk paths, attached by the talkId-numbering
        # heuristic; collected as (talkId, path) then sorted by talkId below.
        _free_group: dict[id_types.QuestId, list[tuple[int, str]]] = (
            collections.defaultdict(list)
        )
        self.free_group_quest_to_paths: dict[id_types.QuestId, list[str]] = {}

        invalid_paths = dict[pathlib.Path, str]()

        # Scan Talk directory and all subdirectories for JSON files
        talk_files = sorted((self.agd_path / "BinOutput" / "Talk").glob("**/*.json"))
        # Parse in parallel up front; the serial scan below then hits the cache,
        # keeping classification and dedup decisions in the original sorted order.
        caching.warm_concurrently(
            data_repo.load_talk_group_data,
            [
                rel.as_posix()
                for json_file in talk_files
                if (rel := json_file.relative_to(self.agd_path))
                not in self._BAD_TALK_PATHS
                and rel.parts[2] not in self._EXCLUDE_DIRECTORIES
                and rel.parts[2] != self._COOP_DIRECTORY
            ],
        )
        for json_file in talk_files:
            relative_path = json_file.relative_to(self.agd_path)

            if relative_path in self._BAD_TALK_PATHS:
                logger.warning("Known bad talk file %s", relative_path)
                continue

            subdir = relative_path.parts[2]

            # Excluded and Coop files need only their path, not parsed content, so
            # short-circuit before the (cached) load to skip ~1300 needless reads.
            if subdir in self._EXCLUDE_DIRECTORIES:
                continue
            if subdir == self._COOP_DIRECTORY:
                self._handle_coop_file(relative_path, _coop_group)
                continue

            data = data_repo.load_talk_group_data(relative_path.as_posix())

            try:
                if subdir == self._FREE_GROUP_DIRECTORY:
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

        self._resolve_talk_group_candidates()

        for quest_id, talks in _free_group.items():
            self.free_group_quest_to_paths[quest_id] = [
                path for _, path in sorted(talks)
            ]

        for coop_story_id, coop_talks in _coop_group.items():
            self.coop_story_to_paths[coop_story_id] = [
                path for _, path in sorted(coop_talks)
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
                assert isinstance(id, int), relative_path
                key_id = str(id)
            case "GadgetGroup":
                # configId alone is not unique across GadgetGroup files (issue
                # #186); fold in groupId as the file's own composite key. Both
                # fields are required on every GadgetGroup file, so let a
                # missing key raise rather than silently mis-keying the file.
                key_id = f'{data["configId"]}_{data["groupId"]}'
            case _:
                assert_never(group_type)

        key = (group_type, key_id)
        self._talk_group_candidates[key].append(relative_path.as_posix())

    def _resolve_talk_group_candidates(self) -> None:
        for key, candidates in self._talk_group_candidates.items():
            winner = min(
                candidates, key=lambda p: self._talk_group_preference_key(key, p)
            )
            self.talk_group_id_to_path[key] = winner
            for dropped in sorted(set(candidates) - {winner}):
                logger.warning(
                    "Ignoring %s already present as %s in %s",
                    dropped,
                    key,
                    winner,
                )

    @staticmethod
    def _talk_group_preference_key(
        key: tuple[TalkGroupType, TalkGroupId], path: str
    ) -> tuple[int, int, str]:
        _, group_id = key
        stem = pathlib.Path(path).stem
        if stem == group_id:
            return (0, 0, path)
        prefix, separator, suffix = stem.partition("_")
        if prefix == group_id and separator and suffix.isdigit():
            return (1, -int(suffix), path)
        return (2, 0, path)

    def _handle_talk_file(
        self, relative_path: pathlib.Path, talk_data: dict[str, Any]
    ) -> None:
        self._talk_candidates[int(talk_data["talkId"])].append(relative_path.as_posix())

    @staticmethod
    def _handle_free_group_file(
        relative_path: pathlib.Path,
        talk_data: dict[str, Any],
        free_group: dict[id_types.QuestId, list[tuple[int, str]]],
    ) -> None:
        """Attach a FreeGroup talk to its owning quest by talkId numbering."""
        talk_id = int(talk_data["talkId"])
        # Skip ids too short to derive a quest id (orphaned, as before).
        if (quest_id := _free_group_quest_id(str(talk_id))) is None:
            return
        free_group[quest_id].append((talk_id, relative_path.as_posix()))

    @staticmethod
    def _handle_coop_file(
        relative_path: pathlib.Path,
        coop_group: dict[id_types.CoopStoryId, list[tuple[int, str]]],
    ) -> None:
        """Group a Coop talk file under its coopStoryId, keyed by local talk id."""
        coop_story_id, _, local_talk_id = relative_path.stem.partition("_")
        if not (coop_story_id.isdigit() and local_talk_id.isdigit()):
            raise ValueError(f"Malformed Coop talk filename {relative_path}")
        coop_group[int(coop_story_id)].append(
            (int(local_talk_id), relative_path.as_posix())
        )

    @staticmethod
    def _init_dialog_map(
        talk_excel_data: agd_types.TalkExcelConfigData,
    ) -> dict[id_types.TalkId, id_types.DialogId]:
        """Map talkId -> initDialog for config entries with a nonzero one."""
        return {
            entry.id: init_dialog
            for entry in talk_excel_data
            if (init_dialog := entry.initDialog)
        }

    def _resolve_talk_candidates(
        self,
        data_repo: repo.DataRepo,
        init_dialogs: dict[id_types.TalkId, id_types.DialogId],
    ) -> None:
        """Collapse per-talkId candidate files into a single authoritative path.

        Several files can share a ``talkId`` (e.g. a canonical and a hash-named
        copy, distinct Coop hangouts reusing a local id, or the same id in
        ``Quest`` and ``Npc``). Resolution, in order: (1) the file whose
        ``initDialog`` dialog actually carries text, when exactly one qualifies;
        (2) when the text-bearing files are equivalent, the canonically-named
        ``<talkId>.json`` copy over a hash-named one; (3) when one candidate's
        text-bearing dialogs are a superset of every other's, that fuller copy
        (the rest being stubs); (4) otherwise the talkId is genuinely ambiguous
        and is dropped. Dialogs
        are loaded (deobfuscated) only for colliding ids, which also warms the
        cache for later rendering.
        """
        text_map = data_repo.build_text_map_tracker()
        # Colliding candidates need their dialogs loaded for signatures; parse
        # them in parallel so the serial resolution below hits the cache.
        caching.warm_concurrently(
            data_repo.load_talk_data,
            [
                path
                for candidates in self._talk_candidates.values()
                if len(candidates) > 1
                for path in candidates
            ],
        )
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
            if (
                len({signatures[p].dialogs for p in textful}) <= 1
                or len({signatures[p].dialog_texts for p in textful}) <= 1
                or len(
                    {tuple(sorted(signatures[p].text_counts.items())) for p in textful}
                )
                <= 1
            ):
                # Equivalent content: prefer the canonically-named `<talkId>.json`
                # copy over a hash-named one. Hash-identical files can come from
                # different builds, and text-identical files can carry remapped
                # hashes for the same displayed dialogue.
                self.talk_id_to_path[talk_id] = min(
                    textful or usable,
                    key=lambda p: (pathlib.Path(p).stem != str(talk_id), p),
                )
                stats["deduped"] += 1
                continue

            # Stub-vs-full collision: when one candidate's text-bearing dialogs
            # are a superset of every other textful candidate's, that fuller copy
            # is authoritative and the rest are stubs missing real dialogue
            # (issue #75). Comparing the (id, content-hash) pairs of text-bearing
            # dialogs — not dialog ids alone — keeps distinct talks that merely
            # reuse local dialog ids (e.g. Coop hangouts) ambiguous.
            superset = max(textful, key=lambda p: len(signatures[p].text_dialogs))
            if all(
                signatures[p].text_dialogs <= signatures[superset].text_dialogs
                for p in textful
            ):
                self.talk_id_to_path[talk_id] = min(
                    (
                        p
                        for p in textful
                        if signatures[p].text_dialogs
                        == signatures[superset].text_dialogs
                    ),
                    key=lambda p: (pathlib.Path(p).stem != str(talk_id), p),
                )
                stats["superset"] += 1
                continue

            text_superset = max(
                textful, key=lambda p: signatures[p].text_counts.total()
            )
            if all(
                signatures[p].text_counts <= signatures[text_superset].text_counts
                for p in textful
            ):
                self.talk_id_to_path[talk_id] = min(
                    (
                        p
                        for p in textful
                        if signatures[p].text_counts
                        == signatures[text_superset].text_counts
                    ),
                    key=lambda p: (pathlib.Path(p).stem != str(talk_id), p),
                )
                stats["superset"] += 1
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
                "Talk collisions: %d by initDialog, %d deduped, %d superset, %d dropped",
                stats["by_init_dialog"],
                stats["deduped"],
                stats["superset"],
                stats["dropped"],
            )

    @staticmethod
    def _talk_signature(
        data_repo: repo.DataRepo, text_map: repo.TextMapTracker, talk_path: str
    ) -> _TalkSignature | None:
        """Content signature of a candidate file, or None if it has no dialogList.

        ``dialogs`` is the raw (id, content-hash) sequence for byte-identity
        checks; ``text_ids`` are the dialog ids whose hash resolves to real text.

        Resolves against the current build only (not the TextMap fallback):
        a stale hash-named duplicate can carry a content hash that only the
        fallback resolves, to a near-identical older-build variant of the
        canonical file's text (e.g. differing punctuation), which would
        otherwise make two candidates look like conflicting content and drop
        the talkId. Same reasoning as role-name hash lookups staying
        current-only (see `_get_role_name_by_text_map_hash` in `_talk.py`).
        """
        data = data_repo.load_talk_data(talk_path)
        try:
            dialogs = data["dialogList"]
        except KeyError:
            return None
        raw_dialogs = tuple(
            (d["id"], d.get("talkContentTextMapHash", 0)) for d in dialogs
        )
        resolved_texts = list[tuple[int, str]]()
        for dialog_id, content_hash in raw_dialogs:
            if (
                text := text_map.get_current_optional_untracked(content_hash)
            ) is not None:
                resolved_texts.append((dialog_id, text))
        text_dialogs = frozenset(
            (dialog_id, content_hash)
            for dialog_id, content_hash in raw_dialogs
            if text_map.get_current_optional_untracked(content_hash) is not None
        )
        return _TalkSignature(
            dialogs=raw_dialogs,
            dialog_texts=tuple(resolved_texts),
            text_counts=collections.Counter(text for _, text in resolved_texts),
            text_dialogs=text_dialogs,
            text_ids=frozenset(i for i, _ in text_dialogs),
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
