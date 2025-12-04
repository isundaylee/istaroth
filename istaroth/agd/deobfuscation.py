"""De-obfuscation logic for AGD JSON files with obfuscated field names."""

from __future__ import annotations

from typing import Any


def deobfuscate_talk_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate talk data JSON by renaming obfuscated field names.

    Only processes fields that are needed according to types.TalkData.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    # Field name mappings for de-obfuscating talk JSON files
    top_level_field_mappings = {
        "PDFCHAAMEHA": "talkId",
        "IKCBIFLCCOH": "dialogList",
    }

    # Check if data needs de-obfuscation (has obfuscated field names)
    if not any(key in data for key in top_level_field_mappings):
        return data

    result: dict[str, Any] = {}

    # Process top-level fields
    for obfuscated_key, real_key in top_level_field_mappings.items():
        if obfuscated_key in data:
            value = data[obfuscated_key]
            # Recursively de-obfuscate dialogList array
            if real_key == "dialogList":
                assert isinstance(
                    value, list
                ), f"dialogList must be a list, got {type(value)}"
                deobfuscated_dialogs = []
                for dialog in value:
                    if (
                        "FJIMHCGKKPJ" not in dialog
                        or "BCBFGKALICJ" not in dialog
                        or "DBIHEJMJCMK" not in dialog
                    ):
                        continue

                    obfuscated_role = dialog.get("BCBFGKALICJ", {})
                    talk_role: dict[str, Any] = {
                        "type": obfuscated_role.get("_type"),
                    }
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
                value = deobfuscated_dialogs
            result[real_key] = value

    return result


def deobfuscate_quest_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate quest data JSON by renaming obfuscated field names.

    Only processes fields that are needed according to types.QuestData.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    # Field name mappings for de-obfuscating quest JSON files
    # Maps obfuscated field names to their actual names
    # Only top-level fields are checked here; nested fields are handled in array processing
    top_level_field_mappings = {
        "FJIMHCGKKPJ": "id",
        "DLPKBOPINEE": "descTextMapHash",
        "HMPOGBDMBOK": "titleTextMapHash",
        "NKEKKINIKEB": "chapterId",
        "BMCONAJCMAK": "subQuests",
        "DCHHEHNNEOO": "talks",
    }

    # Check if data needs de-obfuscation (has obfuscated field names)
    if not any(key in data for key in top_level_field_mappings):
        return data

    result: dict[str, Any] = {}

    # Process top-level fields
    for obfuscated_key, real_key in top_level_field_mappings.items():
        if obfuscated_key in data:
            value = data[obfuscated_key]
            # Recursively de-obfuscate subQuests and talks arrays
            if real_key == "subQuests":
                assert isinstance(
                    value, list
                ), f"subQuests must be a list, got {type(value)}"
                value = [
                    {
                        "subId": subquest.get("FKJCGCAMNEH"),
                        "order": subquest.get("JDCNDABFDFP"),
                    }
                    for subquest in value
                    if "FKJCGCAMNEH" in subquest and "JDCNDABFDFP" in subquest
                ]
            elif real_key == "talks":
                assert isinstance(
                    value, list
                ), f"talks must be a list, got {type(value)}"
                value = [
                    {"id": talk.get("FJIMHCGKKPJ")}
                    for talk in value
                    if "FJIMHCGKKPJ" in talk
                ]
            result[real_key] = value

    return result
