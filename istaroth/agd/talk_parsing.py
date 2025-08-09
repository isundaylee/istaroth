"""Talk parsing utilities for processing AGD talk files."""

import json
import logging
import pathlib
from typing import Any, ClassVar, Literal, TypeAlias, cast

logger = logging.getLogger(__name__)


TalkGroupType: TypeAlias = Literal[
    "ActivityGroup", "BlossomGroup", "GadgetGroup", "NpcGroup"
]


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
    ]

    _GROUP_DIRECTORIES: ClassVar[set[str]] = {
        "ActivityGroup",
        "BlossomGroup",
        "GadgetGroup",
        "NpcGroup",
    }

    def __init__(self, agd_path: pathlib.Path) -> None:
        self.agd_path = agd_path

        self.talk_id_to_path = dict[str, str]()
        self.talk_group_id_to_path = dict[tuple[TalkGroupType, str], str]()

        # Scan Talk directory and all subdirectories for JSON files
        for json_file in (agd_path / "BinOutput" / "Talk").glob("**/*.json"):
            relative_path = json_file.relative_to(agd_path)
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            if len(relative_path.parts) > 2 and (
                relative_path.parts[2] in self._GROUP_DIRECTORIES
            ):
                self._handle_talk_group_file(
                    relative_path, cast(TalkGroupType, relative_path.parts[2]), data
                )
            else:
                if not self._is_talk_file(relative_path, data):
                    continue
                self._handle_talk_file(relative_path, data)

    def _handle_talk_group_file(
        self,
        relative_path: pathlib.Path,
        group_type: TalkGroupType,
        data: dict[str, Any],
    ) -> None:
        match group_type:
            case "ActivityGroup":
                self.talk_group_id_to_path[("ActivityGroup", data["activityId"])] = (
                    relative_path
                ).as_posix()
            case _:
                # TODO add more
                pass

    def _handle_talk_file(
        self, relative_path: pathlib.Path, talk_data: dict[str, Any]
    ) -> None:
        talk_id = str(talk_data["talkId"])
        self.talk_id_to_path[talk_id] = relative_path.as_posix()

    @classmethod
    def _is_talk_file(cls, relative_path: pathlib.Path, talk_data: Any) -> bool:
        """Check if a file is a valid talk file."""
        if relative_path in cls._BAD_TALK_PATHS:
            logger.warning("Known bad talk file %s", relative_path)
            return False

        # Check some invariants
        try:
            assert isinstance(talk_data, dict), relative_path
            assert not (
                talk_data.get("talkId") and talk_data.get("activityId")
            ), relative_path
        except AssertionError:
            logger.warning("Invariant-violating talk file %s", relative_path)
            return False

        if talk_data.get("activityId"):
            logger.warning("Misplaced talk activity group file %s", relative_path)
            return False

        if talk_data.get("talkId") is None:
            logger.warning("Talk without talkId: %s", relative_path)
            return False

        return True
