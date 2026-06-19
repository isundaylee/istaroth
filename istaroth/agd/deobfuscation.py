"""De-obfuscation logic for AGD JSON files with obfuscated field names."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

# Global field mappings - union of all mappings used across different data types.
# NOTE: when adding current-build mappings here, extend
# tests/test_deobfuscation.py to cover them.
_COMMON_FIELD_MAPPINGS = {
    "JOLEJEFDNJJ": "id",
    "FJIMHCGKKPJ": "id",
    "DLPKBOPINEE": "descTextMapHash",
    "HMPOGBDMBOK": "titleTextMapHash",
    "NKEKKINIKEB": "chapterId",
    "BMCONAJCMAK": "subQuests",
    "DCHHEHNNEOO": "talks",
    "DMIMNILOLKP": "talks",
    "FKJCGCAMNEH": "subId",
    "JDCNDABFDFP": "order",
    "PDFCHAAMEHA": "talkId",
    "IKCBIFLCCOH": "dialogList",
    "DBIHEJMJCMK": "talkContentTextMapHash",
    "BCBFGKALICJ": "talkRole",
    "IJOEEMHDLHF": "talkRoleNameTextMapHash",
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
    # OSRELWin4.3.0_R19706476_S19529137_D19702261
    "CCFPGAKINNB": "id",
    "PCNNNPLAEAI": "talks",
    "JDOFKFPHIDC": "npcId",
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
    "PELBMPLIEKC": "talkRoleNameTextMapHash",
    "HJIPOJOECIF": "talkRole",
    "EOFLGOBJBCG": "configId",
    # OSRELWin6.5.0_R43466102_S43178437_D43466102
    "HFIMFOOGLLF": "activityId",
    "NFIEHACCECI": "id",
    "AJGGCMPLKHK": "descTextMapHash",
    "BPNEONFJEEO": "titleTextMapHash",
    "BALAIBAGIEL": "chapterId",
    "MEGJPCLADOG": "subQuests",
    "NFFIGDHFAJG": "talks",
    "KKMJBEPGLGD": "subId",
    "DGINIFCGMGL": "order",
    "NIBKFBCGDGM": "questId",
    "GFFJADIFFGO": "npcId",
    "AADKDKPMGNO": "talkId",
    "GALIDJOEHOC": "dialogList",
    "AIGJBMCHCJG": "talkContentTextMapHash",
    "BMFGJJJPBBC": "talkRoleNameTextMapHash",
    "PIBKEGJOJHN": "talkRole",
    "GBLICFDCPCK": "nextDialogs",
    "JJCCNELFGMF": "configId",
    # CNRELWin6.6.0_R44873995_S44916582_D44916582
    "LBCEBBMAHEI": "activityId",
    "GMOMCKNPBGE": "id",
    "JDFENJAFCPF": "descTextMapHash",
    "ALLMCLJBBDM": "titleTextMapHash",
    "DMKHKJJFOAA": "chapterId",
    "IKECHKLEFFK": "subQuests",
    "CIAOBJHFJJM": "talks",
    "LAFBPKMMBHD": "subId",
    "EDPMKKJIKCJ": "order",
    "LFCEBJOANIJ": "questId",
    "NJNLKKMFCDF": "npcId",
    "KAGCBAHODIP": "beginCond",
    "KFCNJPJOJLA": "talkId",
    "IOEDPLCPFFB": "dialogList",
    "HJJLLECCCPI": "talkContentTextMapHash",
    "GMENEADIGBP": "talkRoleNameTextMapHash",
    "DGGDDIMMIDO": "talkRole",
    "JDAPCNPEAEH": "nextDialogs",
    "JPCHNCNMMBE": "configId",
    "CPAPOLIHGCN": "CUSTOM_addlLocalID",
    "PGELADPAKLA": "finishCond",
    # NOTE: `damageRatio` is the (misleading) cleartext name used by the older
    # 4.8-5.8 AGD dumps; the field is actually the generic enum `_type` reused
    # across finishCond/failCond/guide/exec and even the talk/quest root, not a
    # damage ratio. Kept as-is to match those cleartext dumps.
    "MEGMIMEDODJ": "damageRatio",
    "KFDJJBPNIHG": "param",
    "EIOBNIHPLNG": "count",
    # 6.x-only finishCond string param (e.g. COMPLETE_ANY_TALK's talk-id list);
    # no cleartext lineage name exists, so use the CUSTOM_ convention.
    "PGEONGPJEPN": "CUSTOM_paramStr",
    # CNRELWin6.6.0 Coop story graph (BinOutput/Coop/Coop*.json) node-graph fields.
    # `coopNodeType` values are already cleartext enums (COOP_NODE_TALK/SELECT/END);
    # a TALK node's `coopNodeId` equals the local talk id, so `talkConfig` is unused.
    "NGKBJGGOPEG": "coopInteractionMap",
    "CEKCHKLHGFL": "coopMap",
    "KNDKMMOMHOG": "startNodeId",
    "DACOOAMDHDE": "coopNodeId",
    "HMLLJAMHHHG": "coopNodeType",
    "MPEMBNCPNJO": "nextNodeArray",
    "ICBFHNOKIDE": "selectList",
    "LNKEDDLBLEP": "dialogId",
    # DialogExcelConfigData dialog id (its other text fields are already cleartext).
    "GFLDJMJKIKE": "id",
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


def _process_subquest_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process subquest items, recursing into their nested finishCond arrays."""
    return [
        _deobfuscate_data(
            item, _COMMON_FIELD_MAPPINGS, {"finishCond": _process_array_items}
        )
        for item in items
    ]


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
        "subQuests": _process_subquest_items,
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


def deobfuscate_coop_graph_data(data: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate a Coop story-graph file (BinOutput/Coop/Coop*.json).

    Renames the top-level keys and deeply de-obfuscates ``coopInteractionMap`` —
    a dict keyed by coopStoryId, each holding a ``coopMap`` dict of nodes keyed by
    node id. Other top-level sections (save points, temperaments, ...) are left
    as-is since only the interaction node graph is consumed. Also handles the older
    cleartext dumps, whose keys are already in their final form.
    """
    top = _deobfuscate_data(data, _COMMON_FIELD_MAPPINGS, {})
    top["coopInteractionMap"] = {
        story_id: _deobfuscate_coop_story(story)
        for story_id, story in top["coopInteractionMap"].items()
    }
    return top


def _deobfuscate_coop_story(story: dict[str, Any]) -> dict[str, Any]:
    """De-obfuscate one coopInteractionMap entry and its node map."""
    deobfuscated = _deobfuscate_data(story, _COMMON_FIELD_MAPPINGS, {})
    deobfuscated["coopMap"] = {
        node_id: _deobfuscate_data(
            node, _COMMON_FIELD_MAPPINGS, {"selectList": _process_array_items}
        )
        for node_id, node in deobfuscated["coopMap"].items()
    }
    return deobfuscated


def deobfuscate_dialog_excel_config_data(
    data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """De-obfuscate DialogExcelConfigData JSON by renaming obfuscated field names.

    Exposes the dialog id (the rotating obfuscated key) as ``id``; the dialog's
    text fields ship cleartext already.
    """
    return _process_array_items(data)


def deobfuscate_document_excel_config_data(
    data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """De-obfuscate document Excel config data JSON by renaming obfuscated field names.

    Processes a list of document configuration items.
    Returns data unchanged if it doesn't contain obfuscated field names.
    """
    return _process_array_items(data)
