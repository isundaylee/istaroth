"""Tests for AGD de-obfuscation functionality."""

from typing import Any

import orjson

from istaroth.agd import deobfuscation, repo


def _load_raw(data_repo: repo.DataRepo, relative_path: str) -> Any:
    return orjson.loads((data_repo.agd_path / relative_path).read_bytes())


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
    """De-obfuscate activity and gadget talk groups.

    The ActivityGroup case covers activityId and talks[].id. The GadgetGroup
    case covers the ``groupId`` field (the (configId, groupId) composite
    disambiguator from issue #186) alongside configId.
    """
    activity_path = "BinOutput/Talk/ActivityGroup/2022.json"
    activity = deobfuscation.deobfuscate_talk_group_data(
        _load_raw(data_repo, activity_path)
    )
    assert activity["activityId"] == 2022
    assert activity["talks"][0]["id"] == 4011141

    gadget_path = "BinOutput/Talk/GadgetGroup/1003_220200001.json"
    gadget = deobfuscation.deobfuscate_talk_group_data(
        _load_raw(data_repo, gadget_path)
    )
    assert gadget["configId"] == 1003
    assert gadget["groupId"] == 220200001
    assert gadget["talks"][0]["id"] == 1400825

    # load_talk_group_data returns the same structure for both group types.
    assert data_repo.load_talk_group_data(activity_path)["talks"][0]["id"] == 4011141
    assert data_repo.load_talk_group_data(gadget_path)["configId"] == 1003
    assert data_repo.load_talk_group_data(gadget_path)["groupId"] == 220200001


def test_deobfuscate_coop_graph_data(data_repo: repo.DataRepo) -> None:
    """De-obfuscate a Coop story graph, covering the node-graph play-order fields
    and the new COND/END sub-fields (coopCondGrp, savePointId, showCond/enableCond)."""
    deobfuscated_data = deobfuscation.deobfuscate_coop_graph_data(
        _load_raw(data_repo, "BinOutput/Coop/Coop101401.json")
    )

    story = deobfuscated_data["coopInteractionMap"]["1900102"]
    assert story["id"] == 1900102
    assert story["startNodeId"] == 7

    nodes = story["coopMap"]
    # TALK node: its coopNodeId is the local talk id; nextNodeArray is the edge.
    assert nodes["7"]["coopNodeType"] == "COOP_NODE_TALK"
    assert nodes["7"]["coopNodeId"] == 7
    assert nodes["7"]["nextNodeArray"] == [8]
    # SELECT node: player choice fanning out into two branches; selectList option
    # i pairs with nextNodeArray[i]. Each select item carries showCond/enableCond.
    assert nodes["8"]["coopNodeType"] == "COOP_NODE_SELECT"
    assert nodes["8"]["nextNodeArray"] == [10, 100]
    assert [s["dialogId"] for s in nodes["8"]["selectList"]] == [1900102191, 1900102192]
    for item in nodes["8"]["selectList"]:
        assert "showCond" in item
        assert "enableCond" in item
    # END node: terminal, no outgoing edges, carries savePointId.
    assert nodes["11"]["coopNodeType"] == "COOP_NODE_END"
    assert nodes["11"]["nextNodeArray"] == []
    assert "savePointId" in nodes["11"]

    # Scan every story in the file for a COND node with coopCondGrp.
    found_cond = False
    for story_data in deobfuscated_data["coopInteractionMap"].values():
        for node in story_data["coopMap"].values():
            if node["coopNodeType"] == "COOP_NODE_COND":
                assert "coopCondGrp" in node
                cond_grp = node["coopCondGrp"]
                assert "condCombType" in cond_grp
                assert "coopCondList" in cond_grp
                for cond_entry in cond_grp["coopCondList"]:
                    assert "type" in cond_entry
                    assert "param" in cond_entry
                found_cond = True
    assert found_cond, "No COND node found in Coop101401.json"


def test_deobfuscate_coop_cond_node() -> None:
    """De-obfuscate a synthetic COND node with coopCondGrp."""
    raw = {
        "DACOOAMDHDE": 101,  # coopNodeId
        "HMLLJAMHHHG": "COOP_NODE_COND",
        "MPEMBNCPNJO": [201, 202],
        "AJBJJLPHHOH": {
            "ONIPBCHBDBF": "LOGIC_AND",
            "POJHMDGHNLM": [
                {"DLPKMDPABFM": "COOP_COND_QUEST_FINISH", "IEKGEJMAOCN": [1901503]},
                {"DLPKMDPABFM": "COOP_COND_CONFIDENCE_COMPARE", "IEKGEJMAOCN": [1, 4]},
            ],
        },
    }
    deobf = deobfuscation._deobfuscate_coop_node(raw)
    assert deobf["coopNodeId"] == 101
    assert deobf["coopNodeType"] == "COOP_NODE_COND"
    assert deobf["nextNodeArray"] == [201, 202]
    grp = deobf["coopCondGrp"]
    assert grp["condCombType"] == "LOGIC_AND"
    assert grp["coopCondList"] == [
        {"type": "COOP_COND_QUEST_FINISH", "param": [1901503]},
        {"type": "COOP_COND_CONFIDENCE_COMPARE", "param": [1, 4]},
    ]


def test_deobfuscate_coop_select_node() -> None:
    """De-obfuscate a synthetic SELECT node with showCond/enableCond."""
    raw = {
        "DACOOAMDHDE": 201,
        "HMLLJAMHHHG": "COOP_NODE_SELECT",
        "MPEMBNCPNJO": [301, 302],
        "ICBFHNOKIDE": [
            {
                "LNKEDDLBLEP": 1001,
                "DDBMPGNIHFD": {"ONIPBCHBDBF": "LOGIC_NONE", "POJHMDGHNLM": []},
            },
            {
                "LNKEDDLBLEP": 1002,
                "OPDLPCGPPIL": {
                    "ONIPBCHBDBF": "LOGIC_AND",
                    "POJHMDGHNLM": [
                        {
                            "DLPKMDPABFM": "COOP_COND_QUEST_FINISH",
                            "IEKGEJMAOCN": [1904714],
                        }
                    ],
                },
            },
        ],
    }
    deobf = deobfuscation._deobfuscate_coop_node(raw)
    assert deobf["selectList"][0]["dialogId"] == 1001
    assert deobf["selectList"][0]["showCond"]["condCombType"] == "LOGIC_NONE"
    assert deobf["selectList"][0]["showCond"]["coopCondList"] == []
    # Second option has enableCond.
    assert deobf["selectList"][1]["dialogId"] == 1002
    assert deobf["selectList"][1]["enableCond"]["condCombType"] == "LOGIC_AND"
    assert deobf["selectList"][1]["enableCond"]["coopCondList"] == [
        {"type": "COOP_COND_QUEST_FINISH", "param": [1904714]}
    ]


def test_deobfuscate_coop_end_node() -> None:
    """De-obfuscate a synthetic END node with savePointId."""
    raw = {
        "DACOOAMDHDE": 401,
        "HMLLJAMHHHG": "COOP_NODE_END",
        "MPEMBNCPNJO": [],
        "AOOCCGGPPAI": 90501,
    }
    deobf = deobfuscation._deobfuscate_coop_node(raw)
    assert deobf["coopNodeId"] == 401
    assert deobf["coopNodeType"] == "COOP_NODE_END"
    assert deobf["savePointId"] == 90501


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

    # load_document_excel_config_data returns the same structure, keyed by id.
    loaded = data_repo.load_document_excel_config_data()
    assert loaded[101733]["titleTextMapHash"] == 3763660007
    assert loaded[191431]["CUSTOM_addlLocalID"] == [291001]


def test_deobfuscate_anecdote_excel_config_data(data_repo: repo.DataRepo) -> None:
    """De-obfuscate AnecdoteExcelConfigData via its dedicated (invented-name)
    mapping; like the document test above, this fails loudly on the next AGD bump
    until the rotated keys are re-derived."""
    deobfuscated_data = deobfuscation.deobfuscate_anecdote_excel_config_data(
        _load_raw(data_repo, "ExcelBinOutput/AnecdoteExcelConfigData.json")
    )

    entry = next(e for e in deobfuscated_data if e["id"] == 100001)  # 诺艾尔·剑术
    assert entry["questIds"] == [510000101]
    assert entry["titleTextMapHash"] == 1253956347
    assert entry["teaserTextMapHash"] == 93015952
    assert entry["descTextMapHash"] == 3335685669
    assert entry["isHide"] is False

    # load_anecdote_excel_config_data returns the same structure, keyed by id.
    loaded = data_repo.load_anecdote_excel_config_data()
    assert loaded[100001]["questIds"] == [510000101]
