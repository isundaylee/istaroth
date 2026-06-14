"""Tests for AGD de-obfuscation functionality."""

import json
from typing import Any

from istaroth.agd import deobfuscation, repo


def _load_raw(data_repo: repo.DataRepo, relative_path: str) -> Any:
    return json.loads((data_repo.agd_path / relative_path).read_text(encoding="utf-8"))


def test_deobfuscate_quest_data(data_repo: repo.DataRepo) -> None:
    """De-obfuscate quest 74078.json, covering nested subQuest/finishCond fields."""
    quest_path = "BinOutput/Quest/74078.json"
    deobfuscated_data = deobfuscation.deobfuscate_quest_data(
        _load_raw(data_repo, quest_path)
    )

    # Top-level QuestData fields.
    assert deobfuscated_data["id"] == 74078
    assert deobfuscated_data["descTextMapHash"] == 1583924206
    assert deobfuscated_data["titleTextMapHash"] == 1474993071
    assert deobfuscated_data["chapterId"] == 10155

    # Nested SubQuestItem + FinishCondItem fields (all FinishCondItem keys).
    sub_quests = deobfuscated_data["subQuests"]
    assert sub_quests[0]["subId"] == 7407801
    assert sub_quests[0]["order"] == 101
    [lua_cond] = sub_quests[0]["finishCond"]
    assert lua_cond["damageRatio"] == "QUEST_CONTENT_LUA_NOTIFY"
    assert lua_cond["param"] == [0, 0]
    assert lua_cond["count"] == 1
    assert lua_cond["CUSTOM_paramStr"] == "7407801_FINISH"

    # A COMPLETE_TALK condition whose param points at the talk that completes it.
    complete_talk = next(
        cond
        for sub in sub_quests
        for cond in sub.get("finishCond", [])
        if cond["damageRatio"] == "QUEST_CONTENT_COMPLETE_TALK"
    )
    assert complete_talk["param"] == [7407801, 0]

    # Nested QuestTalkItem ids.
    assert [t["id"] for t in deobfuscated_data["talks"][:2]] == [7407801, 7407802]

    # QuestTalkItem.beginCond: nested items keep the literal `_type` / `_param`
    # keys (not renamed by deobfuscation). Drives lead-in talk step placement.
    [begin_cond] = deobfuscated_data["talks"][0]["beginCond"]
    assert begin_cond["_type"] == "QUEST_COND_STATE_EQUAL"
    assert begin_cond["_param"] == ["7407803", "2"]

    # load_quest_data returns the same structure.
    loaded_data = data_repo.load_quest_data(quest_path)
    assert loaded_data["id"] == 74078
    assert loaded_data["subQuests"][0]["subId"] == 7407801


def test_deobfuscate_talk_data(data_repo: repo.DataRepo) -> None:
    """De-obfuscate talk 7407811.json, covering nextDialogs branches and roles."""
    talk_path = "BinOutput/Talk/Quest/7407811.json"
    deobfuscated_data = deobfuscation.deobfuscate_talk_data(
        _load_raw(data_repo, talk_path)
    )

    assert deobfuscated_data["talkId"] == 7407811
    by_id = {d["id"]: d for d in deobfuscated_data["dialogList"]}

    # NPC line: nested talkRole, content/name hashes, single nextDialogs pointer.
    npc = by_id[740781101]
    assert npc["talkRole"]["type"] == "TALK_ROLE_NPC"
    assert npc["talkRole"]["_id"] == "21048"
    assert npc["talkContentTextMapHash"] == 1510417298
    assert npc["talkRoleNameTextMapHash"] == 0
    assert npc["nextDialogs"] == [740781102]

    # Branch point: one dialog fans out into two player options (the nextDialogs
    # mapping must be present for branch rendering to work at all).
    assert by_id[740781156]["nextDialogs"] == [740781157, 740781158]
    assert by_id[740781157]["talkRole"]["type"] == "TALK_ROLE_PLAYER"

    # load_talk_data returns the same structure.
    loaded_data = data_repo.load_talk_data(talk_path)
    assert loaded_data["talkId"] == 7407811
    assert loaded_data["dialogList"][0]["id"] == 740781101


def test_deobfuscate_talk_group_data(data_repo: repo.DataRepo) -> None:
    """De-obfuscate an activity talk group, covering activityId and talks[].id."""
    group_path = "BinOutput/Talk/ActivityGroup/2022.json"
    deobfuscated_data = deobfuscation.deobfuscate_talk_group_data(
        _load_raw(data_repo, group_path)
    )

    assert deobfuscated_data["activityId"] == 2022
    assert deobfuscated_data["talks"][0]["id"] == 4011141

    # load_talk_group_data returns the same structure.
    loaded_data = data_repo.load_talk_group_data(group_path)
    assert loaded_data["talks"][0]["id"] == 4011141


def test_deobfuscate_document_excel_config_data(data_repo: repo.DataRepo) -> None:
    """De-obfuscate DocumentExcelConfigData, covering the cleartext fields plus the
    obfuscated page-2 localization id field."""
    deobfuscated_data = deobfuscation.deobfuscate_document_excel_config_data(
        _load_raw(data_repo, "ExcelBinOutput/DocumentExcelConfigData.json")
    )

    doc = next(d for d in deobfuscated_data if d["id"] == 101733)
    assert doc["titleTextMapHash"] == 3763660007
    assert doc["questIDList"] == [200363]
    assert doc["questContentLocalizedId"] == [200565]

    # A Paged weapon-story doc keeps its page-2 readable's localization id in an
    # obfuscated field that rotates every build; the deobf pass must expose it as
    # CUSTOM_addlLocalID so the second page resolves a title (issue #71). Asserting
    # the deobfuscated output means this fails loudly on the next AGD bump if the
    # rotated key isn't added to the mapping — the signal to add it.
    weapon_doc = next(d for d in deobfuscated_data if d["id"] == 191431)  # 息燧之笛
    assert weapon_doc["questContentLocalizedId"] == [291431]  # page 1 (cleartext)
    assert weapon_doc["CUSTOM_addlLocalID"] == [291001]  # page 2 (was obfuscated)

    # load_document_excel_config_data returns the same structure.
    loaded = data_repo.load_document_excel_config_data()
    assert (
        next(d for d in loaded if d["id"] == 101733)["titleTextMapHash"] == 3763660007
    )
    assert next(d for d in loaded if d["id"] == 191431)["CUSTOM_addlLocalID"] == [
        291001
    ]
