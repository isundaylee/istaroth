"""De-obfuscation logic for AGD JSON files with obfuscated field names."""

from __future__ import annotations

from typing import Any


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
