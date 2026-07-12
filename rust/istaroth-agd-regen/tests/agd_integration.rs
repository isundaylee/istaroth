//! Integration tests against a real AGD checkout (port of the data-dependent
//! Python tests). Skipped (early return with a message) when `AGD_PATH` is
//! unset, mirroring the Python suite's skip behavior.
//!
//! Several of these are canaries meant to fail loudly on the next AGD version
//! bump — obfuscated keys rotate every build, so the deobfuscation tests
//! breaking is the signal to run the agd-deobfuscate/agd-version-upgrade
//! skills.

use istaroth_agd_regen::hierarchy::{self, HierarchyNode};
use istaroth_agd_regen::issues::Scope;
use istaroth_agd_regen::lang::Language;
use istaroth_agd_regen::renderables::{
    achievement, activity, book, character, creature, hangout, quest, readable, subtitle, talk,
    weapon,
};
use istaroth_agd_regen::repo::Repo;
use istaroth_agd_regen::{deob, vh::ValueExt};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

fn agd_path() -> Option<PathBuf> {
    match std::env::var("AGD_PATH") {
        Ok(p) => Some(PathBuf::from(p)),
        Err(_) => {
            eprintln!("AGD_PATH not set; skipping AGD integration test");
            None
        }
    }
}

fn first_seen_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../text/first_seen")
}

fn repo() -> Option<&'static Repo> {
    static REPO: OnceLock<Option<Repo>> = OnceLock::new();
    REPO.get_or_init(|| {
        let agd = agd_path()?;
        Some(
            Repo::load(
                &agd,
                &first_seen_dir(),
                Language::Chs,
                false,
                &Scope::default(),
            )
            .expect("Repo::load"),
        )
    })
    .as_ref()
}

macro_rules! require_repo {
    () => {
        match repo() {
            Some(repo) => repo,
            None => return,
        }
    };
}

fn load_raw(agd: &Path, relative_path: &str) -> Value {
    serde_json::from_slice(&std::fs::read(agd.join(relative_path)).unwrap()).unwrap()
}

// --- deobfuscation canaries over real AGD files ---

#[test]
fn deobfuscate_quest_data() {
    // Quest 74078, covering nested subQuest/finishCond fields.
    let Some(agd) = agd_path() else { return };
    let data = deob::deobfuscate_quest_data(load_raw(&agd, "BinOutput/Quest/74078.json")).unwrap();

    assert_eq!(data["id"], 74078);
    assert_eq!(data["descTextMapHash"], 1583924206);
    assert_eq!(data["titleTextMapHash"], 1474993071);
    assert_eq!(data["chapterId"], 10155);

    // Nested SubQuestItem + FinishCondItem fields (all FinishCondItem keys).
    let sub_quests = data["subQuests"].as_array().unwrap();
    assert_eq!(sub_quests[0]["subId"], 7407801);
    assert_eq!(sub_quests[0]["order"], 101);
    let [lua_cond] = &sub_quests[0]["finishCond"].as_array().unwrap()[..] else {
        panic!("expected exactly one finishCond");
    };
    assert_eq!(lua_cond["damageRatio"], "QUEST_CONTENT_LUA_NOTIFY");
    assert_eq!(lua_cond["param"], serde_json::json!([0, 0]));
    assert_eq!(lua_cond["count"], 1);
    assert_eq!(lua_cond["CUSTOM_paramStr"], "7407801_FINISH");

    // A COMPLETE_TALK condition whose param points at the talk that completes it.
    let complete_talk = sub_quests
        .iter()
        .flat_map(|s| s.get_arr("finishCond").into_iter().flatten())
        .find(|c| c["damageRatio"] == "QUEST_CONTENT_COMPLETE_TALK")
        .unwrap();
    assert_eq!(complete_talk["param"], serde_json::json!([7407801, 0]));

    // Nested QuestTalkItem ids.
    let talks = data["talks"].as_array().unwrap();
    assert_eq!(talks[0]["id"], 7407801);
    assert_eq!(talks[1]["id"], 7407802);

    // QuestTalkItem.beginCond: nested items keep the literal `_type` / `_param`
    // keys (not renamed by deobfuscation). Drives lead-in talk step placement.
    let [begin_cond] = &talks[0]["beginCond"].as_array().unwrap()[..] else {
        panic!("expected exactly one beginCond");
    };
    assert_eq!(begin_cond["_type"], "QUEST_COND_STATE_EQUAL");
    assert_eq!(begin_cond["_param"], serde_json::json!(["7407803", "2"]));
}

#[test]
fn deobfuscate_talk_data() {
    // Talk 7407811, covering nextDialogs branches and roles.
    let Some(agd) = agd_path() else { return };
    let data =
        deob::deobfuscate_talk_file(load_raw(&agd, "BinOutput/Talk/Quest/7407811.json")).unwrap();

    assert_eq!(data["talkId"], 7407811);
    let dialogs = data["dialogList"].as_array().unwrap();
    let by_id = |id: i64| dialogs.iter().find(|d| d["id"] == id).unwrap();

    // NPC line: nested talkRole, content/name hashes, single nextDialogs pointer.
    let npc = by_id(740781101);
    assert_eq!(npc["talkRole"]["type"], "TALK_ROLE_NPC");
    assert_eq!(npc["talkRole"]["_id"], "21048");
    assert_eq!(npc["talkContentTextMapHash"], 1510417298);
    assert_eq!(npc["talkRoleNameTextMapHash"], 0);
    assert_eq!(npc["nextDialogs"], serde_json::json!([740781102]));

    // Branch point: one dialog fans out into two player options (the
    // nextDialogs mapping must be present for branch rendering to work at all).
    assert_eq!(
        by_id(740781156)["nextDialogs"],
        serde_json::json!([740781157, 740781158])
    );
    assert_eq!(by_id(740781157)["talkRole"]["type"], "TALK_ROLE_PLAYER");
}

#[test]
fn deobfuscate_talk_group_data() {
    // The ActivityGroup case covers activityId and talks[].id. The GadgetGroup
    // case covers the `groupId` field (the (configId, groupId) composite
    // disambiguator from issue #186) alongside configId.
    let Some(agd) = agd_path() else { return };
    let activity_group =
        deob::deobfuscate_talk_file(load_raw(&agd, "BinOutput/Talk/ActivityGroup/2022.json"))
            .unwrap();
    assert_eq!(activity_group["activityId"], 2022);
    assert_eq!(activity_group["talks"][0]["id"], 4011141);

    let gadget_group = deob::deobfuscate_talk_file(load_raw(
        &agd,
        "BinOutput/Talk/GadgetGroup/1003_220200001.json",
    ))
    .unwrap();
    assert_eq!(gadget_group["configId"], 1003);
    assert_eq!(gadget_group["groupId"], 220200001);
    assert_eq!(gadget_group["talks"][0]["id"], 1400825);
}

#[test]
fn deobfuscate_coop_graph_data() {
    // A Coop story graph, covering the node-graph play-order fields and the
    // COND/END sub-fields (coopCondGrp, savePointId, showCond/enableCond).
    let Some(agd) = agd_path() else { return };
    let data = deob::deobfuscate_coop_graph_data(load_raw(&agd, "BinOutput/Coop/Coop101401.json"))
        .unwrap();

    let story = &data["coopInteractionMap"]["1900102"];
    assert_eq!(story["id"], 1900102);
    assert_eq!(story["startNodeId"], 7);

    let nodes = &story["coopMap"];
    // TALK node: its coopNodeId is the local talk id; nextNodeArray is the edge.
    assert_eq!(nodes["7"]["coopNodeType"], "COOP_NODE_TALK");
    assert_eq!(nodes["7"]["coopNodeId"], 7);
    assert_eq!(nodes["7"]["nextNodeArray"], serde_json::json!([8]));
    // SELECT node: player choice fanning out into two branches; selectList
    // option i pairs with nextNodeArray[i]. Each item carries showCond/enableCond.
    assert_eq!(nodes["8"]["coopNodeType"], "COOP_NODE_SELECT");
    assert_eq!(nodes["8"]["nextNodeArray"], serde_json::json!([10, 100]));
    let select_list = nodes["8"]["selectList"].as_array().unwrap();
    assert_eq!(select_list[0]["dialogId"], 1900102191);
    assert_eq!(select_list[1]["dialogId"], 1900102192);
    for item in select_list {
        assert!(item.get("showCond").is_some());
        assert!(item.get("enableCond").is_some());
    }
    // END node: terminal, no outgoing edges, carries savePointId.
    assert_eq!(nodes["11"]["coopNodeType"], "COOP_NODE_END");
    assert_eq!(nodes["11"]["nextNodeArray"], serde_json::json!([]));
    assert!(nodes["11"].get("savePointId").is_some());

    // Scan every story in the file for a COND node with coopCondGrp.
    let mut found_cond = false;
    for story_data in data["coopInteractionMap"].as_object().unwrap().values() {
        for node in story_data["coopMap"].as_object().unwrap().values() {
            if node["coopNodeType"] == "COOP_NODE_COND" {
                let cond_grp = node
                    .get("coopCondGrp")
                    .unwrap_or_else(|| panic!("COND node without coopCondGrp: {node}"));
                assert!(cond_grp.get("condCombType").is_some());
                for cond_entry in cond_grp["coopCondList"].as_array().unwrap() {
                    assert!(cond_entry.get("type").is_some());
                    assert!(cond_entry.get("param").is_some());
                }
                found_cond = true;
            }
        }
    }
    assert!(found_cond, "No COND node found in Coop101401.json");
}

#[test]
fn deobfuscate_document_excel_config_data() {
    // Covers the cleartext fields plus the obfuscated page-2 localization id
    // field: a Paged weapon-story doc keeps its page-2 readable's localization
    // id in an obfuscated field that rotates every build; the deobf pass must
    // expose it as CUSTOM_addlLocalID so the second page resolves a title
    // (issue #71). This fails loudly on the next AGD bump if the rotated key
    // isn't added to the mapping — the signal to add it.
    let Some(agd) = agd_path() else { return };
    let data = deob::deobfuscate_document_excel_config_data(
        load_raw(&agd, "ExcelBinOutput/DocumentExcelConfigData.json")
            .as_array()
            .unwrap()
            .clone(),
    )
    .unwrap();

    let doc = data.iter().find(|d| d["id"] == 101733).unwrap();
    assert_eq!(doc["titleTextMapHash"], 3763660007i64);
    assert_eq!(doc["questIDList"], serde_json::json!([200363]));
    assert_eq!(doc["questContentLocalizedId"], serde_json::json!([200565]));

    let weapon_doc = data.iter().find(|d| d["id"] == 191431).unwrap(); // 息燧之笛
    assert_eq!(
        weapon_doc["questContentLocalizedId"],
        serde_json::json!([291431]) // page 1 (cleartext)
    );
    assert_eq!(
        weapon_doc["CUSTOM_addlLocalID"],
        serde_json::json!([291001]) // page 2 (was obfuscated)
    );
}

#[test]
fn deobfuscate_anecdote_excel_config_data() {
    // Dedicated (invented-name) mapping; like the document test above, this
    // fails loudly on the next AGD bump until the rotated keys are re-derived.
    let Some(agd) = agd_path() else { return };
    let data = deob::deobfuscate_anecdote_excel_config_data(
        load_raw(&agd, "ExcelBinOutput/AnecdoteExcelConfigData.json")
            .as_array()
            .unwrap()
            .clone(),
    )
    .unwrap();

    let entry = data.iter().find(|e| e["id"] == 100001).unwrap(); // 诺艾尔·剑术
    assert_eq!(entry["questIds"], serde_json::json!([510000101]));
    assert_eq!(entry["titleTextMapHash"], 1253956347);
    assert_eq!(entry["teaserTextMapHash"], 93015952);
    assert_eq!(entry["descTextMapHash"], 3335685669i64);
    assert_eq!(entry["isHide"], false);
}

// --- Repo-level processing over real data ---

#[test]
fn sexpro_resolves_from_pinned_build() {
    // 6.x dropped the SEXPRO TextMap rows, so the token's hash (from
    // ManualTextMapConfigData) resolves through the pinned fallback refs.
    let repo = require_repo!();
    assert_eq!(
        repo.tm
            .clean_text("找{PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_HE|INFO_FEMALE_PRONOUN_SHE]}")
            .unwrap(),
        "找他"
    );
}

#[test]
fn readable_metadata_titles() {
    let repo = require_repo!();
    let scope = Scope::default();
    for (filename, expected_title) in [
        ("Book100.txt", "神霄折戟录·第六卷"),
        ("Weapon11101.txt", "无锋剑"),
    ] {
        let metadata = readable::get_readable_metadata(repo, &scope, filename).unwrap();
        assert_eq!(metadata.title, expected_title);
    }
}

#[test]
fn talk_7407811_info() {
    let repo = require_repo!();
    let scope = Scope::default();
    let info = talk::get_talk_info(repo, &scope, "BinOutput/Talk/Quest/7407811.json").unwrap();

    assert!(!info.text.is_empty());
    let roles: Vec<Option<&String>> = info.text.iter().map(|t| t.role.as_ref()).collect();
    assert!(roles.iter().any(|r| r.is_some_and(|r| r == talk::PLAYER)));
    assert!(
        roles
            .iter()
            .any(|r| r.is_none_or(|r| r != talk::PLAYER && r != talk::BLACK_SCREEN))
    );
    for talk_text in &info.text {
        assert!(!talk_text.message.trim().is_empty());
    }
}

#[test]
fn talk_6864003_narration_role() {
    // Speaker-less TALK_ROLE_NONE lines carry no role (None), not Unknown Role.
    let repo = require_repo!();
    let scope = Scope::default();
    let info = talk::get_talk_info(repo, &scope, "BinOutput/Talk/Gadget/6864003.json").unwrap();

    assert!(info.text.iter().any(|t| t.role.is_none()));
    assert!(info.text.iter().all(|t| {
        t.role
            .as_ref()
            .is_none_or(|r| !r.contains("TALK_ROLE_NONE"))
    }));
}

#[test]
fn quest_74078_info() {
    let repo = require_repo!();
    let scope = Scope::default();
    let info = quest::get_quest_info(repo, &scope, 74078).unwrap().unwrap();

    assert!(!info.title.trim().is_empty());
    assert!(!info.steps.is_empty());

    // Every dialogue step has meaningful talk content.
    let talk_steps: Vec<_> = info.steps.iter().filter(|s| s.talk.is_some()).collect();
    assert!(!talk_steps.is_empty());
    for step in &talk_steps {
        let talk_info = step.talk.as_ref().unwrap();
        assert!(!talk_info.text.is_empty());
        for talk_text in &talk_info.text {
            assert!(talk_text.role.as_ref().is_none_or(|r| !r.trim().is_empty()));
            assert!(!talk_text.message.trim().is_empty());
        }
    }

    // 74078 has non-dialogue objective steps, each carrying objective text.
    let objective_steps: Vec<_> = info.steps.iter().filter(|s| s.talk.is_none()).collect();
    assert!(!objective_steps.is_empty());
    assert!(objective_steps.iter().all(|s| s.description.is_some()));
}

#[test]
fn fallback_text_map_does_not_break_talk_collision_resolution() {
    // Fallback hash collisions dedupe by resolved text.
    let repo = require_repo!();
    for quest_id in [11020, 75079] {
        let scope = Scope::default();
        let info = quest::get_quest_info(repo, &scope, quest_id)
            .unwrap()
            .unwrap();
        assert!(!info.steps.is_empty());
    }
}

#[test]
fn quest_10008_associated_free_talks() {
    // FreeGroup "free talks" are attached to their owning quest.
    let repo = require_repo!();
    let scope = Scope::default();
    let info = quest::get_quest_info(repo, &scope, 10008).unwrap().unwrap();

    assert!(!info.associated_free_talks.is_empty());
    for talk_info in &info.associated_free_talks {
        assert!(!talk_info.text.is_empty());
        for talk_text in &talk_info.text {
            assert!(talk_text.role.as_ref().is_none_or(|r| !r.trim().is_empty()));
            assert!(!talk_text.message.trim().is_empty());
        }
    }
}

#[test]
fn furina_constellations_flat_list() {
    // Furina's six constellations render as a flat list (no ### element
    // subsections), including the C5 example name.
    let repo = require_repo!();
    let scope = Scope::default();
    let rendered = character::process_story(repo, &scope, 10000089)
        .unwrap()
        .unwrap();

    assert!(rendered.content.contains("## Constellations\n"));
    assert!(rendered.content.contains("秘密藏心间，无人知我名。"));
    assert!(!rendered.content.contains("###"));
}

#[test]
fn traveler_constellations_grouped_by_element() {
    // The Traveler's per-element constellations group under ### subsections.
    let repo = require_repo!();
    let scope = Scope::default();
    let rendered = character::process_story(repo, &scope, 10000005)
        .unwrap()
        .unwrap();

    let element_headers = rendered
        .content
        .lines()
        .filter(|l| l.starts_with("### "))
        .count();
    assert!(element_headers >= 2, "{}", rendered.content);
}

#[test]
fn achievement_section_46() {
    // Achievement sections include their localized achievement text.
    let repo = require_repo!();
    let scope = Scope::default();
    let rendered = achievement::process(repo, &scope, 46).unwrap().unwrap();

    assert_eq!(rendered.meta.title, "枫丹·白露澈明的泉舞·其之三");
    assert!(
        rendered
            .content
            .contains("## 水仙十字题解\n\n何物徒留名字？")
    );
}

#[test]
fn drunkards_tale_series_grouped() {
    // The four-volume 'A Drunkard's Tale' (suit 1019) groups its volumes in order.
    let repo = require_repo!();
    let scope = Scope::default();
    let rendered = book::process_book_series(repo, &scope, 1019)
        .unwrap()
        .unwrap();

    assert_eq!(rendered.meta.title, "醉客轶事");
    let positions: Vec<usize> = [
        "## 醉客轶事·一",
        "## 醉客轶事·二",
        "## 醉客轶事·三",
        "## 醉客轶事·四",
    ]
    .iter()
    .map(|volume| rendered.content.find(volume).unwrap())
    .collect();
    assert!(positions.is_sorted(), "{positions:?}");
}

#[test]
fn creature_group_automatron() {
    // The Automatron group resolves labels and each entry's names; the mek
    // carries its special name and title alongside the description.
    let repo = require_repo!();
    let scope = Scope::default();
    let rendered = creature::process(repo, &scope, "CODEX_SUBTYPE_AUTOMATRON")
        .unwrap()
        .unwrap();

    assert_eq!(rendered.meta.title, "自律机关");
    assert!(rendered.content.starts_with("# 自律机关 (魔物)\n"));
    assert!(
        rendered
            .content
            .contains("## 攻坚特化型机关\n谢尔比乌斯式机关\nAlso known as: 攻坚特化型")
    );
}

#[test]
fn creatures_discover_returns_subtype_groups() {
    // Discovery enumerates codex subType groups: far fewer files than entries
    // (a dozen-ish groups vs. hundreds of creatures).
    let repo = require_repo!();
    let discovered = creature::discover(repo).unwrap();

    assert!(discovered.contains(&"CODEX_SUBTYPE_AUTOMATRON".to_string()));
    assert!(discovered.len() < 20);
    assert!(repo.excel.animal_codex.len() > 100);
}

#[test]
fn activity_5295_groups_loose_talks() {
    // Loose TALK_ACTIVITY talks group under their owning activity's id and name.
    let repo = require_repo!();
    let scope = Scope::default();
    let no_used = Default::default();
    assert!(activity::discover(repo, &no_used).unwrap().contains(&5295));

    let rendered = activity::process(repo, &scope, &no_used, 5295)
        .unwrap()
        .unwrap();
    assert!(
        rendered.meta.title.contains("龙龙同游"),
        "{}",
        rendered.meta.title
    );
}

#[test]
fn subtitle_placeholder_file_skipped() {
    // A known placeholder subtitle (lone '.') renders to None.
    let repo = require_repo!();
    let scope = Scope::default();
    assert!(
        subtitle::process(repo, &scope, "Subtitle/CHS/Cs_Sumeru_AQ302009_MOTM_CHS.srt")
            .unwrap()
            .is_none()
    );
}

#[test]
fn subtitle_titles_resolve_owning_quest() {
    // Subtitle titles resolve to the owning quest's name (issue #74).
    let repo = require_repo!();
    let scope = Scope::default();
    for (stem, expected) in [
        // Cutscene binding via videoName / subtitleId.
        (
            "Cs_Inazuma_LQ1204205_IntoTheVoid_Boy_CHS",
            "熠熠生辉之樱 (Cs_Inazuma_LQ1204205_IntoTheVoid_Boy)",
        ),
        // Shared no-variant subtitle, matched through the localization path.
        (
            "Cs_MDAQ019_DragonInCity_CHS",
            "龙灾 (Cs_MDAQ019_DragonInCity)",
        ),
        // No id token in the stem: only resolvable through its cutscene binding.
        ("Ambor_Readings_CHS", "风之翼随风而起 (Ambor_Readings)"),
        // No cutscene file in AGD: quest id token decoded from the filename.
        (
            "Cs_NK_AQ603605_Boss_Boy_CHS",
            "虚空劫灰往世书 (Cs_NK_AQ603605_Boss_Boy)",
        ),
        // System video with no owning quest: bare stem.
        ("Title_CHS", "Title"),
    ] {
        let rendered = subtitle::process(repo, &scope, &format!("Subtitle/CHS/{stem}.srt"))
            .unwrap()
            .unwrap();
        assert_eq!(rendered.meta.title, expected, "{stem}");
    }
}

#[test]
fn subtitle_title_resolution_coverage() {
    // Nearly all subtitles resolve a quest title; guards against a future AGD
    // build silently breaking the cutscene scan (e.g. newly obfuscated keys).
    let repo = require_repo!();
    let scope = Scope::default();
    let mut unresolved: Vec<String> = Vec::new();
    for path in subtitle::discover(repo).unwrap() {
        if let Some(rendered) = subtitle::process(repo, &scope, &path).unwrap()
            && !rendered.meta.title.contains(" (")
        {
            unresolved.push(path);
        }
    }
    assert!(unresolved.len() <= 12, "{unresolved:?}");
}

#[test]
fn hangout_yunjin_rendered_structure() {
    // Hangout 19017 (Yunjin) resolves its primary character and title, and the
    // rendered output has the expected section structure.
    let repo = require_repo!();
    let scope = Scope::default();
    let rendered = hangout::process(repo, &scope, 19017).unwrap().unwrap();

    assert_eq!(rendered.meta.title, "云堇 - 郊野觅芳踪");
    let content = &rendered.content;
    let count_lines = |prefix: &str| content.lines().filter(|l| l.starts_with(prefix)).count();

    // Yunjin has 4 stories (1901701–1901704), one ### Talk: header each, plus
    // one fork in conversation 3 with 2 branches and 5 save-point endings.
    assert_eq!(count_lines("### Talk:"), 4, "{content}");
    assert_eq!(count_lines("### Choice "), 1, "{content}");
    assert_eq!(count_lines("#### Branch "), 2, "{content}");
    assert_eq!(content.matches("*→ Ending (save point ").count(), 5);
    assert_eq!(content.matches("*→ Next: Choice ").count(), 0);
    assert_eq!(content.matches("*→ End of conversation*").count(), 0);
    assert_eq!(count_lines("*Condition:"), 0);
}

// --- hierarchy assembly ---

fn find_node<'a>(nodes: &'a [HierarchyNode], key: &str) -> &'a HierarchyNode {
    nodes
        .iter()
        .find(|n| n.key == key)
        .unwrap_or_else(|| panic!("no node with key {key}"))
}

fn leaf_ids(node: &HierarchyNode) -> Vec<i64> {
    node.children
        .as_ref()
        .unwrap()
        .iter()
        .map(|leaf| leaf.file_id.unwrap())
        .collect()
}

#[test]
fn quest_hierarchy_places_74078() {
    // Quest 74078 lands under WQ -> series 10152 -> chapter 10155, and the
    // series is titled by the common prefix of its chapters' titles
    // (水仙的追迹·第N幕 ...), not the first-chapter-title fallback.
    let repo = require_repo!();
    let built =
        hierarchy::build_quest_hierarchy(repo, &[(74078, "溪舟的尾波".to_string())]).unwrap();

    let wq = find_node(&built.nodes, "WQ");
    let series = find_node(wq.children.as_ref().unwrap(), "s10152");
    let chapter = find_node(series.children.as_ref().unwrap(), "c10155");
    assert_eq!(leaf_ids(chapter), vec![74078]);
    assert_eq!(series.title.as_deref(), Some("水仙的追迹"));
}

#[test]
fn quest_hierarchy_groupless_chapter_stays_loose() {
    // A groupId-less chapter (山中好长日) sits directly under its type, no series.
    let repo = require_repo!();
    let built = hierarchy::build_quest_hierarchy(repo, &[(76095, "天堂".to_string())]).unwrap();

    let wq = find_node(&built.nodes, "WQ");
    let chapter = find_node(wq.children.as_ref().unwrap(), "c10094");
    assert_eq!(leaf_ids(chapter), vec![76095]);
}

#[test]
fn quest_hierarchy_orders_chapter_10130_by_narrative() {
    // Chapter 10130's quests follow narrative order, not ascending id order:
    // 73287 is the begin quest yet has the highest id; the suggestTrack chain
    // places it first instead of last (cf. plain id sort).
    let repo = require_repo!();
    let items: Vec<(i64, String)> = [73103, 73186, 73187, 73219, 73220, 73287]
        .into_iter()
        .map(|quest_id| (quest_id, quest_id.to_string()))
        .collect();
    let built = hierarchy::build_quest_hierarchy(repo, &items).unwrap();

    let wq = find_node(&built.nodes, "WQ");
    let series = find_node(wq.children.as_ref().unwrap(), "s10130");
    let chapter = find_node(series.children.as_ref().unwrap(), "c10130");
    assert_eq!(
        leaf_ids(chapter),
        vec![73287, 73219, 73186, 73187, 73103, 73220]
    );
}

#[test]
fn quest_hierarchy_standalone_bucket() {
    // A quest with no chapter falls into its type's synthetic standalone group.
    let repo = require_repo!();
    let (quest_id, quest_type) = repo
        .excel
        .main_quest
        .iter()
        .find_map(|(quest_id, mq)| {
            let quest_type = mq.get_s("type").filter(|t| !t.is_empty())?;
            (mq.get_i("chapterId") == Some(0)).then(|| (*quest_id, quest_type.to_string()))
        })
        .unwrap();

    let built =
        hierarchy::build_quest_hierarchy(repo, &[(quest_id, "standalone".to_string())]).unwrap();
    let type_node = find_node(&built.nodes, &quest_type);

    // The only child is the standalone group holding the lone quest leaf.
    let children = type_node.children.as_ref().unwrap();
    assert_eq!(children.len(), 1);
    let standalone = &children[0];
    assert_eq!(standalone.key, "standalone");
    assert_eq!(standalone.title.as_deref(), Some("独立任务"));
    assert_eq!(leaf_ids(standalone), vec![quest_id]);
}

#[test]
fn coop_hierarchy_character_chapter_quest() {
    // The hierarchy groups hangout quests under character -> chapter -> quest.
    let repo = require_repo!();
    let coop_items: Vec<(i64, String)> = repo
        .hangout_quest_to_stories
        .keys()
        .map(|&quest_id| (quest_id, String::new()))
        .collect();
    let built = hierarchy::build_coop_hierarchy(repo, &coop_items).unwrap();

    // Yunjin has a single act, so its quest leaves hang directly off the character.
    let yunjin = built
        .nodes
        .iter()
        .find(|c| c.title.as_deref() == Some("云堇"))
        .unwrap();
    let leaves = yunjin.children.as_ref().unwrap();
    assert!(leaves.iter().all(|leaf| leaf.file_id.is_some()));
    assert!(
        leaves
            .iter()
            .any(|leaf| leaf.file_id == Some(19017) && leaf.title.as_deref() == Some("郊野觅芳踪"))
    );

    // Noelle is the one character split across two hangout chapters (acts), so
    // her children are chapter groups rather than bare quest leaves.
    let noelle = built
        .nodes
        .iter()
        .find(|c| c.title.as_deref() == Some("诺艾尔"))
        .unwrap();
    let chapters = noelle.children.as_ref().unwrap();
    assert_eq!(chapters.len(), 2);
    assert!(
        chapters
            .iter()
            .all(|ch| ch.children.is_some() && ch.file_id.is_none())
    );
}

// --- weapon story paging (depends on the CUSTOM_addlLocalID deobfuscation) ---

#[test]
fn weapon_11431_multi_page_story() {
    // 息燧之笛's second story page resolves through CUSTOM_addlLocalID; both
    // pages render into one document separated by ---.
    let repo = require_repo!();
    let scope = Scope::default();
    let rendered = weapon::process(repo, &scope, "11431").unwrap().unwrap();

    assert_eq!(rendered.meta.title, "息燧之笛");
    assert!(
        rendered.content.contains("\n\n---\n\n"),
        "{}",
        rendered.content
    );
}
