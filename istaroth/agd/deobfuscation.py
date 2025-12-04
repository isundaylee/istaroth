"""De-obfuscation logic for AGD JSON files with obfuscated field names."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def _deobfuscate_data(
    data: dict[str, Any],
    field_mappings: dict[str, str],
    array_processors: Mapping[str, Callable[[list[Any]], list[Any]]],
) -> dict[str, Any]:
    """Generic de-obfuscation function.

    Args:
        data: Raw JSON data that may contain obfuscated field names
        field_mappings: Mapping from obfuscated keys to real keys
        array_processors: Mapping from real keys to functions that process array values

    Returns:
        De-obfuscated data, or original data if no obfuscation detected
    """
    if not any(key in data for key in field_mappings):
        return data

    result: dict[str, Any] = {}

    for obfuscated_key, real_key in field_mappings.items():
        if obfuscated_key in data:
            value = data[obfuscated_key]
            if real_key in array_processors:
                assert isinstance(
                    value, list
                ), f"{real_key} must be a list, got {type(value)}"
                value = array_processors[real_key](value)
            result[real_key] = value

    return result


def _process_dialog_list(dialogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process obfuscated dialog list items."""
    deobfuscated_dialogs = []
    for dialog in dialogs:
        if (
            "FJIMHCGKKPJ" not in dialog
            or "BCBFGKALICJ" not in dialog
            or "DBIHEJMJCMK" not in dialog
        ):
            continue

        obfuscated_role = dialog.get("BCBFGKALICJ", {})
        talk_role: dict[str, Any] = {"type": obfuscated_role.get("_type")}
        if obfuscated_role.get("_id"):
            talk_role["_id"] = obfuscated_role["_id"]
        if obfuscated_role.get("id"):
            talk_role["id"] = obfuscated_role["id"]

        deobfuscated_dialog: dict[str, Any] = {
            "id": dialog.get("FJIMHCGKKPJ"),
            "talkRole": talk_role,
            "talkContentTextMapHash": dialog.get("DBIHEJMJCMK"),
        }
        if role_name_hash := dialog.get("IJOEEMHDLHF"):
            deobfuscated_dialog["talkRoleNameTextMapHash"] = role_name_hash

        deobfuscated_dialogs.append(deobfuscated_dialog)
    return deobfuscated_dialogs


def _process_sub_quests(subquests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process obfuscated subquest items."""
    return [
        {
            "subId": subquest.get("FKJCGCAMNEH"),
            "order": subquest.get("JDCNDABFDFP"),
        }
        for subquest in subquests
        if "FKJCGCAMNEH" in subquest and "JDCNDABFDFP" in subquest
    ]


def _process_talks(talks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process obfuscated talk items."""
    return [{"id": talk.get("FJIMHCGKKPJ")} for talk in talks if "FJIMHCGKKPJ" in talk]


def deobfuscate_talk_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate talk data JSON by renaming obfuscated field names.

    Only processes fields that are needed according to types.TalkData.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    field_mappings = {
        "PDFCHAAMEHA": "talkId",
        "IKCBIFLCCOH": "dialogList",
    }
    array_processors = {
        "dialogList": _process_dialog_list,
    }
    return _deobfuscate_data(data, field_mappings, array_processors)


def deobfuscate_quest_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate quest data JSON by renaming obfuscated field names.

    Only processes fields that are needed according to types.QuestData.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    field_mappings = {
        "FJIMHCGKKPJ": "id",
        "DLPKBOPINEE": "descTextMapHash",
        "HMPOGBDMBOK": "titleTextMapHash",
        "NKEKKINIKEB": "chapterId",
        "BMCONAJCMAK": "subQuests",
        "DCHHEHNNEOO": "talks",
    }
    array_processors = {
        "subQuests": _process_sub_quests,
        "talks": _process_talks,
    }
    return _deobfuscate_data(data, field_mappings, array_processors)
