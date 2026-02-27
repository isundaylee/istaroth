"""De-obfuscation logic for AGD JSON files with obfuscated field names."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

# Global field mappings - union of all mappings used across different data types
_COMMON_FIELD_MAPPINGS = {
    "JOLEJEFDNJJ": "id",
    "FJIMHCGKKPJ": "id",
    "DLPKBOPINEE": "descTextMapHash",
    "HMPOGBDMBOK": "titleTextMapHash",
    "NKEKKINIKEB": "chapterId",
    "BMCONAJCMAK": "subQuests",
    "DCHHEHNNEOO": "talks",
    "PCNNNPLAEAI": "talks",
    "DMIMNILOLKP": "talks",
    "FKJCGCAMNEH": "subId",
    "JDCNDABFDFP": "order",
    "PDFCHAAMEHA": "talkId",
    "IKCBIFLCCOH": "dialogList",
    "DBIHEJMJCMK": "talkContentTextMapHash",
    "BCBFGKALICJ": "talkRole",
    "IJOEEMHDLHF": "talkRoleNameTextMapHash",
    "JDOFKFPHIDC": "npcId",
    "PGCNMMEBDIE": "npcId",
    "ELEPNLBFNOP": "npcId",
    "DANPPPLPAEE": "configId",
    "JEMDGACPOPC": "configId",
    "CLNOODHDADD": "configId",
    "FHNJHCFCADD": "questId",
    "GCABNOAOIFL": "CUSTOM_addlLocalID",
    "PFAJMABJOFK": "CUSTOM_addlLocalID",
    "JLLIMLALADN": "nextDialogs",
    "_type": "type",
    "_id": "_id",
    "id": "id",
    # OSRELWin6.3.0_R41701329_S41708913_D41667700
    "ILHDNJDDEOP": "id",
    "CBBBCAKOFGO": "descTextMapHash",
    "MMOEEOFGHHG": "titleTextMapHash",
    "IBNCKLKHAKG": "chapterId",
    "GFLHMKOOHHA": "subQuests",
    "IBEGAHMEABP": "talks",
    "KCMPGABPPOD": "subId",
    "AOOILFKIPDJ": "order",
    "KINCAGMDMHH": "npcId",
    "OAOCMNEPKOG": "questId",
    "ADHLLDAPKCM": "talkId",
    "MOEOFGCKILF": "dialogList",
    "GABLFFECBDO": "talkContentTextMapHash",
    "LCECPDILLEE": "talkRole",
    "OBKPGBMNDJF": "configId",
    # CNRELWin6.4.0_R42630645_S42523468_D42623923
    "BLKKAMEMBBJ": "id",
    "OCMKKHHNKJO": "descTextMapHash",
    "DMLOMLNJCNA": "titleTextMapHash",
    "KDKGIPFDENG": "chapterId",
    "NLCNGJKMAEN": "subQuests",
    "DGJMIPFDEOF": "talks",
    "MPKBGPAKIOA": "subId",
    "EDICBFEMNNF": "order",
    "HOKOLLABBGP": "questId",
    "CAKFHGJGEEK": "npcId",
    "LBPGKDMGFBN": "talkId",
    "LOJEOMAPIIM": "dialogList",
    "CMKPOJOEHHA": "talkContentTextMapHash",
    "HJIPOJOECIF": "talkRole",
    "EOFLGOBJBCG": "configId",
}


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
    obfuscated_keys = set(field_mappings.keys())

    # Single loop over data fields
    for key, value in data.items():
        if key in obfuscated_keys:
            # This is an obfuscated key, map it to the real key
            real_key = field_mappings[key]
            if real_key in array_processors:
                assert isinstance(
                    value, list
                ), f"{real_key} must be a list, got {type(value)}"
                value = array_processors[real_key](value)
            result[real_key] = value
        else:
            # This is an original non-obfuscated key that won't be overwritten
            result[key] = value

    return result


def _process_array_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process obfuscated array items using common field mappings."""
    return [_deobfuscate_data(item, _COMMON_FIELD_MAPPINGS, {}) for item in items]


def _process_dialog_list(dialogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process obfuscated dialog list items."""
    deobfuscated_dialogs = []
    for dialog in dialogs:
        deobfuscated_dialog = _deobfuscate_data(dialog, _COMMON_FIELD_MAPPINGS, {})
        if obfuscated_role := deobfuscated_dialog.get("talkRole"):
            deobfuscated_dialog["talkRole"] = _deobfuscate_data(
                obfuscated_role, _COMMON_FIELD_MAPPINGS, {}
            )

        deobfuscated_dialogs.append(deobfuscated_dialog)
    return deobfuscated_dialogs


def deobfuscate_talk_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate talk data JSON by renaming obfuscated field names.

    Only processes fields that are needed according to types.TalkData.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    array_processors = {
        "dialogList": _process_dialog_list,
    }
    return _deobfuscate_data(data, _COMMON_FIELD_MAPPINGS, array_processors)


def deobfuscate_quest_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate quest data JSON by renaming obfuscated field names.

    Only processes fields that are needed according to types.QuestData.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    array_processors = {
        "subQuests": _process_array_items,
        "talks": _process_array_items,
    }
    return _deobfuscate_data(data, _COMMON_FIELD_MAPPINGS, array_processors)


def deobfuscate_talk_group_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate talk group data JSON by renaming obfuscated field names.

    Handles ActivityGroup, NpcGroup, and GadgetGroup data.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    return _deobfuscate_data(
        data, _COMMON_FIELD_MAPPINGS, {"talks": _process_array_items}
    )


def deobfuscate_document_excel_config_data(
    data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """De-obfuscate document Excel config data JSON by renaming obfuscated field names.

    Processes a list of document configuration items.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    return _process_array_items(data)
