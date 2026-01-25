"""Talk parsing utilities for processing AGD talk files."""

from __future__ import annotations

import logging
import pathlib
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeAlias, assert_never, cast

if TYPE_CHECKING:
    from istaroth.agd import repo

logger = logging.getLogger(__name__)


TalkGroupType: TypeAlias = Literal["ActivityGroup", "GadgetGroup", "NpcGroup"]


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

    _GROUP_DIRECTORIES: ClassVar[set[str]] = {
        "ActivityGroup",
        "GadgetGroup",
        "NpcGroup",
        "StoryboardGroup",
    }

    def __init__(self, data_repo: repo.DataRepo) -> None:
        self.agd_path = data_repo.agd_path

        self.talk_id_to_path = dict[str, str]()
        self.talk_group_id_to_path = dict[tuple[TalkGroupType, str], str]()

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
        talk_id = str(talk_data["talkId"])
        self.talk_id_to_path[talk_id] = relative_path.as_posix()

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
