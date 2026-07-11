//! Port of istaroth.agd.repo.DataRepo (CHS build): eager loading of all AGD
//! inputs plus every derived mapping generate-all consumes.

use crate::coop::CoopStoryGraph;
use crate::firstseen::FirstSeenIndex;
use crate::lang::Language;
use crate::talkparse::TalkParseResult;
use crate::textmap::TextMaps;
use crate::vh::{ValueExt, int_array};
use crate::{coop, deob, talkparse, util};
use anyhow::{Context, Result, anyhow, bail};
use indexmap::IndexMap;
use rayon::prelude::*;
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;
use std::cell::RefCell;
use std::path::{Path, PathBuf};

/// Non-fatal parsing gap categories (port of issues.IssueType).
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum IssueType {
    MissingTalk,
    MissingDialog,
    MissingText,
    UnknownRole,
    MissingQuestTitle,
    MissingStoryContent,
    MissingMaterialName,
    MissingMaterialDesc,
    MissingReadableTitle,
}

impl IssueType {
    pub fn name(self) -> &'static str {
        match self {
            IssueType::MissingTalk => "MISSING_TALK",
            IssueType::MissingDialog => "MISSING_DIALOG",
            IssueType::MissingText => "MISSING_TEXT",
            IssueType::UnknownRole => "UNKNOWN_ROLE",
            IssueType::MissingQuestTitle => "MISSING_QUEST_TITLE",
            IssueType::MissingStoryContent => "MISSING_STORY_CONTENT",
            IssueType::MissingMaterialName => "MISSING_MATERIAL_NAME",
            IssueType::MissingMaterialDesc => "MISSING_MATERIAL_DESC",
            IssueType::MissingReadableTitle => "MISSING_READABLE_TITLE",
        }
    }
}

/// A single recorded non-fatal parsing gap (item identity stamped by the caller).
pub struct Issue {
    pub issue_type: IssueType,
    pub detail: String,
}

/// Per-item access-tracking scope: ids feeding cross-pass exclusion (talk ids,
/// readable filenames), text-map hashes (unused-stats only), and non-fatal
/// parsing issues recorded inline.
#[derive(Default)]
pub struct Scope {
    pub talks: RefCell<FxHashSet<i64>>,
    pub readables: RefCell<FxHashSet<String>>,
    pub text_map: RefCell<FxHashSet<i64>>,
    pub issues: RefCell<Vec<Issue>>,
}

impl Scope {
    pub fn record_issue(&self, issue_type: IssueType, detail: String) {
        self.issues.borrow_mut().push(Issue { issue_type, detail });
    }
}

pub struct Repo {
    pub agd_path: PathBuf,
    pub language: Language,
    pub tm: TextMaps,
    pub first_seen: FirstSeenIndex,

    pub talk_excel: Vec<Value>,
    pub talk_ids_all: FxHashSet<i64>,
    pub talk_files: FxHashMap<String, Value>,
    pub quest_files: FxHashMap<String, Value>,
    pub quest_mapping: FxHashMap<i64, String>,

    pub parse: TalkParseResult,

    // Raw excels (only those consumed as lists / keyed maps).
    pub localization_excel: Vec<Value>,
    pub document: IndexMap<i64, Value>,
    pub book_suit: FxHashMap<i64, Value>,
    pub material: IndexMap<i64, Value>,
    pub anecdote: IndexMap<i64, Value>,
    pub blossom_talk: Vec<Value>,
    pub blossom_refresh: FxHashMap<i64, Value>,
    pub city_config: FxHashMap<i64, Value>,
    pub coop_chapter: Vec<Value>,
    pub avatar_excel: Vec<Value>,
    pub skill_depot: FxHashMap<i64, Value>,
    pub talent: FxHashMap<i64, Value>,
    pub skill: FxHashMap<i64, Value>,
    pub fetter_story: Vec<Value>,
    pub fetters: Vec<Value>,
    pub animal_codex: IndexMap<i64, Value>,
    pub monster_describe: FxHashMap<i64, Value>,
    pub monster_title: FxHashMap<i64, Value>,
    pub monster_special_name: Vec<Value>,
    pub animal_describe: FxHashMap<i64, Value>,
    pub main_quest: IndexMap<i64, Value>,
    pub chapter: IndexMap<i64, Value>,
    pub reliquary_set: Vec<Value>,
    pub reliquary: Vec<Value>,
    pub equip_affix: Vec<Value>,
    pub weapon_excel: IndexMap<i64, Value>,

    // Derived mappings.
    pub readable_stem_to_loc_id: FxHashMap<String, i64>,
    pub loc_id_to_readable_filename: FxHashMap<i64, String>,
    pub loc_id_to_title_hash: FxHashMap<i64, i64>,
    pub book_series: IndexMap<i64, Vec<String>>,
    pub achievement_sections: IndexMap<i64, (Value, Vec<Value>)>,
    pub storyboard_quest_to_talk_ids: FxHashMap<i64, Vec<i64>>,
    pub coop_graphs: FxHashMap<i64, CoopStoryGraph>,
    pub hangout_quest_to_stories: FxHashMap<i64, Vec<i64>>,
    pub coop_chapter_to_avatar: FxHashMap<i64, i64>,
    pub avatar_id_to_name: FxHashMap<i64, String>,
    pub dialog_id_to_content_hash: FxHashMap<i64, i64>,
    pub dialog_id_to_role_hash: FxHashMap<i64, i64>,
    pub sub_quest_to_main: FxHashMap<i64, i64>,
    pub talk_to_quest: FxHashMap<i64, i64>,
    pub subtitle_stem_to_cutscenes: FxHashMap<String, Vec<i64>>,
    pub npc_id_to_name: FxHashMap<i64, String>,
    pub activity_id_to_name: FxHashMap<i64, String>,
    pub npc_id_to_game_mode: FxHashMap<i64, &'static str>,

    pub readable_filenames: FxHashSet<String>,
    pub readable_contents: FxHashMap<String, String>,
    pub readable_filenames_sorted: Vec<String>,
    pub subtitle_names: Vec<String>,
}

fn parse_json(path: &Path) -> Result<Value> {
    let bytes = std::fs::read(path).with_context(|| format!("read {path:?}"))?;
    serde_json::from_slice(&bytes).with_context(|| format!("parse {path:?}"))
}

/// Typed parse of the (huge) DialogExcelConfigData: only the id -> content-hash
/// and id -> role-name-hash maps survive it, so skip building Value trees.
/// Matches Python's deobfuscate-then-strict-index semantics (missing field ->
/// error; duplicate ids -> last wins).
fn parse_dialog_excel(path: &Path) -> Result<(FxHashMap<i64, i64>, FxHashMap<i64, i64>)> {
    use serde::de::{Deserializer, IgnoredAny, MapAccess, SeqAccess, Visitor};

    struct Row {
        id: Option<i64>,
        content: Option<i64>,
        role: Option<i64>,
    }
    struct RowVisitor;
    impl<'de> Visitor<'de> for RowVisitor {
        type Value = Row;
        fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
            f.write_str("dialog excel row")
        }
        fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Row, A::Error> {
            let mut row = Row {
                id: None,
                content: None,
                role: None,
            };
            while let Some(key) = map.next_key::<std::borrow::Cow<str>>()? {
                let name = crate::deob::resolve_field_name(&key);
                match name {
                    "id" => row.id = Some(map.next_value::<i64>()?),
                    "talkContentTextMapHash" => row.content = Some(map.next_value::<i64>()?),
                    "talkRoleNameTextMapHash" => row.role = Some(map.next_value::<i64>()?),
                    _ => {
                        map.next_value::<IgnoredAny>()?;
                    }
                }
            }
            Ok(row)
        }
    }
    impl<'de> serde::Deserialize<'de> for Row {
        fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Row, D::Error> {
            d.deserialize_map(RowVisitor)
        }
    }

    struct Rows(FxHashMap<i64, i64>, FxHashMap<i64, i64>);
    struct RowsVisitor;
    impl<'de> Visitor<'de> for RowsVisitor {
        type Value = Rows;
        fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
            f.write_str("dialog excel list")
        }
        fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Rows, A::Error> {
            let mut content_map = FxHashMap::default();
            let mut role_map = FxHashMap::default();
            while let Some(row) = seq.next_element::<Row>()? {
                let id = row
                    .id
                    .ok_or_else(|| serde::de::Error::custom("dialog row missing id"))?;
                let content = row.content.ok_or_else(|| {
                    serde::de::Error::custom("dialog row missing talkContentTextMapHash")
                })?;
                let role = row.role.ok_or_else(|| {
                    serde::de::Error::custom("dialog row missing talkRoleNameTextMapHash")
                })?;
                content_map.insert(id, content);
                role_map.insert(id, role);
            }
            Ok(Rows(content_map, role_map))
        }
    }

    let bytes = std::fs::read(path).with_context(|| format!("read {path:?}"))?;
    let mut de = serde_json::Deserializer::from_slice(&bytes);
    let rows = de
        .deserialize_seq(RowsVisitor)
        .with_context(|| format!("parse {path:?}"))?;
    de.end()?;
    Ok((rows.0, rows.1))
}

fn index_unique(
    data: Vec<Value>,
    key: impl Fn(&Value) -> Result<i64>,
    what: &str,
) -> Result<IndexMap<i64, Value>> {
    let mut map = IndexMap::with_capacity(data.len());
    for item in data {
        let k = key(&item)?;
        if map.contains_key(&k) {
            bail!("Duplicate {what}: {k}");
        }
        map.insert(k, item);
    }
    Ok(map)
}

fn to_fx(map: IndexMap<i64, Value>) -> FxHashMap<i64, Value> {
    map.into_iter().collect()
}

/// File names directly under `dir` (empty for a missing dir, like Python's
/// `_list_file_names`); any other read error propagates instead of silently
/// yielding an empty (and thus quietly truncated) corpus section.
fn list_dir_files(dir: &Path) -> Result<Vec<String>> {
    let entries = match std::fs::read_dir(dir) {
        Ok(entries) => entries,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e).with_context(|| format!("list {dir:?}")),
    };
    let mut names = Vec::new();
    for entry in entries {
        let entry = entry.with_context(|| format!("list {dir:?}"))?;
        if entry.file_type()?.is_file() {
            names.push(
                entry
                    .file_name()
                    .into_string()
                    .map_err(|n| anyhow!("non-UTF-8 file name {n:?} in {dir:?}"))?,
            );
        }
    }
    names.sort();
    Ok(names)
}

fn walk_json_files(dir: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    for entry in std::fs::read_dir(dir).with_context(|| format!("walk {dir:?}"))? {
        let path = entry.with_context(|| format!("walk {dir:?}"))?.path();
        if path.is_dir() {
            walk_json_files(&path, out)?;
        } else if path.extension().is_some_and(|e| e == "json") {
            out.push(path);
        }
    }
    Ok(())
}

impl Repo {
    /// `load_scope` collects text-map accesses made while building the derived
    /// name mappings (Python: the run-level parent scope active during
    /// `precompute_for_workers`); the caller folds it into the run's usage
    /// stats after all passes.
    pub fn load(
        agd_path: &Path,
        first_seen_dir: &Path,
        language: Language,
        verbose: bool,
        load_scope: &Scope,
    ) -> Result<Repo> {
        let excel = agd_path.join("ExcelBinOutput");
        let language_short = language.short();

        // Talk excel: split files or the single one.
        let load_talk_excel = || -> Result<Vec<Value>> {
            let split: Vec<String> = list_dir_files(&excel)?
                .into_iter()
                .filter(|n| n.starts_with("TalkExcelConfigData_") && n.ends_with(".json"))
                .collect();
            let names = if split.is_empty() {
                vec!["TalkExcelConfigData.json".to_string()]
            } else {
                split
            };
            let mut data = Vec::new();
            for name in names {
                let v = parse_json(&excel.join(&name))?;
                let Value::Array(items) = v else {
                    bail!("{name} must be a list");
                };
                data.extend(items);
            }
            Ok(data)
        };

        // All independent loads run on the rayon pool.
        let t0 = std::time::Instant::now();
        let timed = |name: &str, t: std::time::Instant| {
            if verbose {
                eprintln!("  [load] {name}: {:.2}s", t.elapsed().as_secs_f64());
            }
        };
        let (tm, (talk_files_res, (quest_files_res, (excels_res, misc_res)))) = rayon::join(
            || {
                let t = std::time::Instant::now();
                let r = TextMaps::load(agd_path, language_short);
                timed("text maps", t);
                r
            },
            || {
                rayon::join(
                    || {
                        let t = std::time::Instant::now();
                        let r = Self::load_talk_files(agd_path);
                        timed("talk files", t);
                        r
                    },
                    || {
                        rayon::join(
                            || {
                                let t = std::time::Instant::now();
                                let r = Self::load_quest_files(agd_path);
                                timed("quest files", t);
                                r
                            },
                            || {
                                rayon::join(
                                    || {
                                        let t = std::time::Instant::now();
                                        let r = Self::load_excels(&excel, load_talk_excel);
                                        timed("excels", t);
                                        r
                                    },
                                    || {
                                        let t = std::time::Instant::now();
                                        let r = Self::load_misc(
                                            agd_path,
                                            first_seen_dir,
                                            language_short,
                                        );
                                        timed("misc", t);
                                        r
                                    },
                                )
                            },
                        )
                    },
                )
            },
        );
        timed("phase A total", t0);
        let tm = tm?;
        let (talk_files, talk_file_rels) = talk_files_res?;
        let quest_files = quest_files_res?;
        let ex = excels_res?;
        let misc = misc_res?;

        let talk_excel = ex.talk_excel;
        let talk_ids_all: FxHashSet<i64> = talk_excel
            .iter()
            .map(|t| t.i("id"))
            .collect::<Result<_>>()?;

        // Talk parser (needs talk files + text map + talk excel init dialogs).
        let mut init_dialogs = FxHashMap::default();
        for entry in &talk_excel {
            let init = entry.i("initDialog")?;
            if init != 0 {
                init_dialogs.insert(entry.i("id")?, init);
            }
        }
        let t_parse = std::time::Instant::now();
        let parse = talkparse::parse_talks(&talk_files, &talk_file_rels, &tm, &init_dialogs)?;
        timed("talk parser", t_parse);
        let t_rest = std::time::Instant::now();

        // Quest mapping (BinOutput/Quest id -> path, canonical-name preference).
        let mut quest_mapping: FxHashMap<i64, String> = FxHashMap::default();
        {
            let mut rels: Vec<&String> = quest_files.keys().collect();
            rels.sort();
            for rel in rels {
                let quest_data = &quest_files[rel];
                let quest_id = quest_data.i("id").context("quest file id")?;
                let canonical = format!("BinOutput/Quest/{quest_id}.json");
                if let Some(existing) = quest_mapping.get(&quest_id)
                    && (*existing == canonical || *rel != canonical)
                {
                    continue;
                }
                quest_mapping.insert(quest_id, rel.clone());
            }
        }

        // Localization-derived maps (single pass, JSON key order).
        let mut readable_stem_to_loc_id = FxHashMap::default();
        let mut loc_id_to_readable_filename = FxHashMap::default();
        for entry in &ex.localization {
            let id = entry.i("id")?;
            for path_value in entry.as_object().into_iter().flat_map(|o| o.values()) {
                let Some(path_str) = path_value.as_str() else {
                    continue;
                };
                let name = util::path_name(path_str);
                if path_str.ends_with(&format!("_{language_short}"))
                    || path_str.split('/').any(|p| p == language_short)
                {
                    readable_stem_to_loc_id
                        .entry(name.to_string())
                        .or_insert(id);
                    loc_id_to_readable_filename
                        .entry(id)
                        .or_insert_with(|| format!("{name}.txt"));
                }
            }
        }

        let mut loc_id_to_title_hash = FxHashMap::default();
        for doc in ex.document.values() {
            let title_hash = doc.i("titleTextMapHash")?;
            let mut ids: Vec<i64> = Vec::new();
            if let Some(addl) = doc.get("CUSTOM_addlLocalID") {
                ids.extend(int_array(addl).context("CUSTOM_addlLocalID")?);
            }
            ids.extend(int_array(doc.f("questContentLocalizedId")?)?);
            ids.extend(int_array(doc.f("questIDList")?)?);
            for loc_id in ids {
                loc_id_to_title_hash.entry(loc_id).or_insert(title_hash);
            }
        }

        // Book series mapping.
        let mut book_series_grouped: IndexMap<i64, Vec<String>> = IndexMap::new();
        {
            let mut codexes: Vec<(i64, &Value)> = ex
                .books_codex
                .iter()
                .map(|c| Ok((c.i("sortOrder")?, c)))
                .collect::<Result<_>>()?;
            codexes.sort_by_key(|(sort_order, _)| *sort_order);
            for (_, codex) in codexes {
                if codex.b("isDisuse")? {
                    continue;
                }
                let material_id = codex.i("materialId")?;
                let material = ex.material.get(&material_id).ok_or_else(|| {
                    anyhow!("Book codex references unknown material {material_id}")
                })?;
                let suit_id = material.i("setID")?;
                if suit_id == 0 {
                    continue;
                }
                if !ex.book_suit.contains_key(&suit_id) {
                    bail!("Book material {material_id} claims unknown suit {suit_id}");
                }
                let document = ex
                    .document
                    .get(&material_id)
                    .ok_or_else(|| anyhow!("Book material {material_id} has no document"))?;
                let mut chain: Vec<i64> = int_array(document.f("questIDList")?)?;
                chain.extend(int_array(document.f("questContentLocalizedId")?)?);
                if let Some(addl) = document.get("CUSTOM_addlLocalID") {
                    chain.extend(int_array(addl).context("CUSTOM_addlLocalID")?);
                }
                let filename = chain
                    .iter()
                    .find_map(|loc_id| loc_id_to_readable_filename.get(loc_id))
                    .ok_or_else(|| anyhow!("Book material {material_id} has no readable file"))?;
                book_series_grouped
                    .entry(suit_id)
                    .or_default()
                    .push(filename.clone());
            }
        }
        let book_series: IndexMap<i64, Vec<String>> = book_series_grouped
            .into_iter()
            .filter(|(_, filenames)| filenames.len() >= 2)
            .collect();

        // Achievement sections.
        let mut achievement_sections: IndexMap<i64, (Value, Vec<Value>)> = IndexMap::new();
        for section in &ex.achievement_goal {
            let id = section.i("id")?;
            if achievement_sections
                .insert(id, (section.clone(), Vec::new()))
                .is_some()
            {
                bail!("Duplicate achievement section ID");
            }
        }
        for achievement in &ex.achievement_excel {
            if achievement.b("isDisuse")? {
                continue;
            }
            let goal_id = achievement.i("goalId")?;
            let section = achievement_sections
                .get_mut(&goal_id)
                .ok_or_else(|| anyhow!("Achievement references unknown section {goal_id}"))?;
            section.1.push(achievement.clone());
        }
        for (_, achievements) in achievement_sections.values_mut() {
            let mut keyed: Vec<(i64, i64, Value)> = achievements
                .drain(..)
                .map(|a| Ok((a.i("orderId")?, a.i("id")?, a)))
                .collect::<Result<_>>()?;
            keyed.sort_by_key(|(order_id, id, _)| (*order_id, *id));
            achievements.extend(keyed.into_iter().map(|(_, _, a)| a));
        }

        // Storyboard quest -> talk ids.
        let mut storyboard_quest_to_talk_ids: FxHashMap<i64, Vec<i64>> = FxHashMap::default();
        for entry in &talk_excel {
            if entry.s("loadType")? == "TALK_STORYBOARD" {
                storyboard_quest_to_talk_ids
                    .entry(entry.i("questId")?)
                    .or_default()
                    .push(entry.i("id")?);
            }
        }
        for ids in storyboard_quest_to_talk_ids.values_mut() {
            ids.sort();
        }

        // Coop story graphs.
        let mut coop_graphs: FxHashMap<i64, CoopStoryGraph> = FxHashMap::default();
        for data in misc.coop_graph_files {
            let data = deob::deobfuscate_coop_graph_data(data)?;
            for story in data.f("coopInteractionMap")?.as_object().unwrap().values() {
                let graph = coop::build_story_graph(story)?;
                coop_graphs.insert(graph.coop_story_id, graph);
            }
        }

        // Hangout quest -> coop stories with talk files.
        let mut hangout_quest_to_stories: FxHashMap<i64, Vec<i64>> = FxHashMap::default();
        for entry in &ex.coop_interaction {
            let coop_story_id = entry.i("id")?;
            if parse.coop_story_to_paths.contains_key(&coop_story_id) {
                hangout_quest_to_stories
                    .entry(entry.i("mainQuestId")?)
                    .or_default()
                    .push(coop_story_id);
            }
        }
        for stories in hangout_quest_to_stories.values_mut() {
            stories.sort();
        }

        let mut coop_chapter_to_avatar = FxHashMap::default();
        for chapter in &ex.coop_chapter {
            coop_chapter_to_avatar.insert(chapter.i("id")?, chapter.i("avatarId")?);
        }

        let mut avatar_id_to_name = FxHashMap::default();
        for avatar in &ex.avatar_excel {
            if let Some(name) = tm.get_optional(avatar.i("nameTextMapHash")?, load_scope)? {
                avatar_id_to_name.insert(avatar.i("id")?, name);
            }
        }

        let mut npc_id_to_name = FxHashMap::default();
        for npc in &ex.npc_excel {
            if let Some(name) = tm.get_optional(npc.i("nameTextMapHash")?, load_scope)? {
                npc_id_to_name.insert(npc.i("id")?, name);
            }
        }

        let mut activity_id_to_name = FxHashMap::default();
        for (activity_id, entry) in &ex.new_activity {
            if let Some(name) = tm.get_optional(entry.i("nameTextMapHash")?, load_scope)? {
                activity_id_to_name.insert(*activity_id, name);
            }
        }

        let mut npc_id_to_game_mode: FxHashMap<i64, &'static str> = FxHashMap::default();
        let mode_lists: [(&'static str, Vec<i64>); 3] = [
            (
                "尘歌壶",
                ex.home_world_npc
                    .iter()
                    .map(|e| e.i("npcID"))
                    .collect::<Result<_>>()?,
            ),
            (
                "幻想真境剧诗",
                ex.role_combat_tarot
                    .iter()
                    .map(|e| e.i("npcId"))
                    .collect::<Result<_>>()?,
            ),
            (
                "七圣召唤",
                ex.gcg_week_level
                    .iter()
                    .map(|e| e.i("npcId"))
                    .collect::<Result<_>>()?,
            ),
        ];
        for (mode, npc_ids) in mode_lists {
            for npc_id in npc_ids {
                if npc_id == 0 {
                    continue;
                }
                if let Some(existing) = npc_id_to_game_mode.get(&npc_id)
                    && *existing != mode
                {
                    bail!("NPC {npc_id} claimed by two game modes");
                }
                npc_id_to_game_mode.insert(npc_id, mode);
            }
        }

        let mut sub_quest_to_main = FxHashMap::default();
        for quest in &ex.quest_excel {
            sub_quest_to_main.insert(quest.i("subId")?, quest.i("mainId")?);
        }

        let mut talk_to_quest = FxHashMap::default();
        for talk_item in &talk_excel {
            let quest_id = talk_item.i("questId")?;
            if quest_id != 0 {
                talk_to_quest.insert(talk_item.i("id")?, quest_id);
            }
        }

        // Subtitle stem -> cutscene ids.
        let mut localization_id_to_stems: FxHashMap<i64, Vec<String>> = FxHashMap::default();
        for entry in &ex.localization {
            let id = entry.i("id")?;
            for path_value in entry.as_object().into_iter().flat_map(|o| o.values()) {
                let Some(path_str) = path_value.as_str() else {
                    continue;
                };
                let stem = util::path_stem(path_str);
                if stem.ends_with(&format!("_{language_short}")) {
                    localization_id_to_stems
                        .entry(id)
                        .or_default()
                        .push(stem.to_string());
                }
            }
        }
        let mut subtitle_stem_sets: FxHashMap<String, FxHashSet<i64>> = FxHashMap::default();
        for (path, data) in &misc.cutscene_files {
            let cutscene_id: i64 = util::path_stem(path).parse().context("cutscene stem")?;
            let variants = data
                .as_object()
                .ok_or_else(|| anyhow!("cutscene file {path} must be an object"))?;
            for variant in variants.values() {
                if !variant.is_object() {
                    bail!("cutscene variant in {path} must be an object");
                }
                let Some(video_config) = variant.get("videoConfig") else {
                    continue;
                };
                for key in ["videoName", "videoNameOther"] {
                    let video_name = video_config.s(key)?;
                    if !video_name.is_empty() {
                        let stem = format!("{}_{language_short}", util::path_stem(video_name));
                        subtitle_stem_sets
                            .entry(stem)
                            .or_default()
                            .insert(cutscene_id);
                    }
                }
                for key in ["subtitleId", "subtitleIdOther"] {
                    let Some(loc_id) = video_config.get_i(key) else {
                        continue;
                    };
                    for stem in localization_id_to_stems.get(&loc_id).into_iter().flatten() {
                        subtitle_stem_sets
                            .entry(stem.clone())
                            .or_default()
                            .insert(cutscene_id);
                    }
                }
            }
        }
        let subtitle_stem_to_cutscenes: FxHashMap<String, Vec<i64>> = subtitle_stem_sets
            .into_iter()
            .map(|(stem, ids)| {
                let mut v: Vec<i64> = ids.into_iter().collect();
                v.sort();
                (stem, v)
            })
            .collect();

        let (dialog_id_to_content_hash, dialog_id_to_role_hash) = ex.dialog_maps;

        let readable_filenames: FxHashSet<String> =
            misc.readable_contents.keys().cloned().collect();
        let mut readable_filenames_sorted: Vec<String> =
            readable_filenames.iter().cloned().collect();
        readable_filenames_sorted.sort();

        timed("derived mappings", t_rest);
        Ok(Repo {
            agd_path: agd_path.to_path_buf(),
            language,
            tm,
            first_seen: misc.first_seen,
            talk_excel,
            talk_ids_all,
            talk_files,
            quest_files,
            quest_mapping,
            parse,
            localization_excel: ex.localization,
            document: ex.document,
            book_suit: ex.book_suit,
            material: ex.material,
            anecdote: ex.anecdote,
            blossom_talk: ex.blossom_talk,
            blossom_refresh: ex.blossom_refresh,
            city_config: ex.city_config,
            coop_chapter: ex.coop_chapter,
            avatar_excel: ex.avatar_excel,
            skill_depot: ex.skill_depot,
            talent: ex.talent,
            skill: ex.skill,
            fetter_story: ex.fetter_story,
            fetters: ex.fetters,
            animal_codex: ex.animal_codex,
            monster_describe: ex.monster_describe,
            monster_title: ex.monster_title,
            monster_special_name: ex.monster_special_name,
            animal_describe: ex.animal_describe,
            main_quest: ex.main_quest,
            chapter: ex.chapter,
            reliquary_set: ex.reliquary_set,
            reliquary: ex.reliquary,
            equip_affix: ex.equip_affix,
            weapon_excel: ex.weapon_excel,
            readable_stem_to_loc_id,
            loc_id_to_readable_filename,
            loc_id_to_title_hash,
            book_series,
            achievement_sections,
            storyboard_quest_to_talk_ids,
            coop_graphs,
            hangout_quest_to_stories,
            coop_chapter_to_avatar,
            avatar_id_to_name,
            dialog_id_to_content_hash,
            dialog_id_to_role_hash,
            sub_quest_to_main,
            talk_to_quest,
            subtitle_stem_to_cutscenes,
            npc_id_to_name,
            activity_id_to_name,
            npc_id_to_game_mode,
            readable_filenames,
            readable_contents: misc.readable_contents,
            readable_filenames_sorted,
            subtitle_names: misc.subtitle_names,
        })
    }

    fn load_talk_files(agd_path: &Path) -> Result<(FxHashMap<String, Value>, Vec<String>)> {
        let talk_dir = agd_path.join("BinOutput").join("Talk");
        let mut files = Vec::new();
        walk_json_files(&talk_dir, &mut files)?;
        let mut rels: Vec<String> = files
            .iter()
            .map(|p| {
                p.strip_prefix(agd_path)
                    .unwrap()
                    .to_str()
                    .unwrap()
                    .to_string()
            })
            .collect();
        rels.sort();
        let parsed: Vec<Option<(String, Value)>> = rels
            .par_iter()
            .map(|rel| {
                if talkparse::BAD_TALK_PATHS.contains(&rel.as_str()) {
                    return Ok(None);
                }
                let parts: Vec<&str> = rel.split('/').collect();
                let subdir = parts[2];
                if subdir == "BlossomGroup" {
                    return Ok(None);
                }
                let mut data = serde_json::from_slice(&std::fs::read(agd_path.join(rel))?)
                    .with_context(|| format!("parse {rel}"))?;
                data = deob::deobfuscate_talk_file(data)?;
                // load_talk_group_data's stem-derived id injection.
                let inject = match subdir {
                    "NpcGroup" => Some("npcId"),
                    "ActivityGroup" => Some("activityId"),
                    "StoryboardGroup" => Some("storyboardId"),
                    _ => None,
                };
                if let Some(field) = inject {
                    let stem = util::path_stem(rel);
                    if util::py_isdigit(stem)
                        && let Some(obj) = data.as_object_mut()
                        && !obj.contains_key(field)
                    {
                        obj.insert(field.to_string(), Value::from(stem.parse::<i64>().unwrap()));
                    }
                }
                Ok(Some((rel.clone(), data)))
            })
            .collect::<Result<_>>()?;
        Ok((parsed.into_iter().flatten().collect(), rels))
    }

    fn load_quest_files(agd_path: &Path) -> Result<FxHashMap<String, Value>> {
        let quest_dir = agd_path.join("BinOutput").join("Quest");
        let mut names = list_dir_files(&quest_dir)?;
        names.retain(|n| n.ends_with(".json"));
        names
            .par_iter()
            .map(|name| {
                let rel = format!("BinOutput/Quest/{name}");
                let data = serde_json::from_slice(&std::fs::read(quest_dir.join(name))?)
                    .with_context(|| format!("parse {rel}"))?;
                Ok((rel, deob::deobfuscate_quest_data(data)?))
            })
            .collect()
    }

    fn load_excels(
        excel: &Path,
        load_talk_excel: impl Fn() -> Result<Vec<Value>> + Sync,
    ) -> Result<Excels> {
        // Prefetch every excel list in parallel (the dialog excel gets a typed
        // low-allocation parse since only two id->hash maps survive it).
        const EXCEL_NAMES: [&str; 29] = [
            "LocalizationExcelConfigData.json",
            "MaterialExcelConfigData.json",
            "NpcExcelConfigData.json",
            "DocumentExcelConfigData.json",
            "BookSuitExcelConfigData.json",
            "BooksCodexExcelConfigData.json",
            "AchievementExcelConfigData.json",
            "AchievementGoalExcelConfigData.json",
            "AnecdoteExcelConfigData.json",
            "BlossomTalkExcelConfigData.json",
            "BlossomRefreshExcelConfigData.json",
            "CityConfigData.json",
            "CoopInteractionExcelConfigData.json",
            "CoopChapterExcelConfigData.json",
            "AvatarExcelConfigData.json",
            "AvatarSkillDepotExcelConfigData.json",
            "AvatarTalentExcelConfigData.json",
            "AvatarSkillExcelConfigData.json",
            "FetterStoryExcelConfigData.json",
            "FettersExcelConfigData.json",
            "AnimalCodexExcelConfigData.json",
            "MonsterDescribeExcelConfigData.json",
            "MonsterTitleExcelConfigData.json",
            "MonsterSpecialNameExcelConfigData.json",
            "AnimalDescribeExcelConfigData.json",
            "MainQuestExcelConfigData.json",
            "ChapterExcelConfigData.json",
            "NewActivityExcelConfigData.json",
            "QuestExcelConfigData.json",
        ];
        // ReliquarySet/Reliquary/EquipAffix/Weapon/HomeWorld/RoleCombat/GCG too.
        const EXCEL_NAMES2: [&str; 7] = [
            "ReliquarySetExcelConfigData.json",
            "ReliquaryExcelConfigData.json",
            "EquipAffixExcelConfigData.json",
            "WeaponExcelConfigData.json",
            "HomeWorldNPCExcelConfigData.json",
            "RoleCombatTarotAvatarExcelConfigData.json",
            "GCGWeekLevelExcelConfigData.json",
        ];
        let (talk_excel, (dialog_maps, prefetched)) = rayon::join(&load_talk_excel, || {
            rayon::join(
                || parse_dialog_excel(&excel.join("DialogExcelConfigData.json")),
                || -> Result<FxHashMap<&'static str, Vec<Value>>> {
                    EXCEL_NAMES
                        .iter()
                        .chain(EXCEL_NAMES2.iter())
                        .collect::<Vec<_>>()
                        .par_iter()
                        .map(|name| {
                            let v = parse_json(&excel.join(name))?;
                            match v {
                                Value::Array(items) => Ok((**name, items)),
                                _ => bail!("{name} must be a list"),
                            }
                        })
                        .collect()
                },
            )
        });
        let mut prefetched = prefetched?;
        let mut list = |name: &str| -> Result<Vec<Value>> {
            prefetched
                .remove(name)
                .ok_or_else(|| anyhow!("excel {name} not prefetched"))
        };
        let dialog_maps = dialog_maps?;
        let document = index_unique(
            deob::deobfuscate_document_excel_config_data(list("DocumentExcelConfigData.json")?)?,
            |d| d.i("id"),
            "document ID",
        )?;
        // MaterialTracker: dict comprehension keyed by id — last wins, first position.
        let mut material: IndexMap<i64, Value> = IndexMap::new();
        for m in list("MaterialExcelConfigData.json")? {
            let id = m.i("id")?;
            material.insert(id, m);
        }
        let localization = list("LocalizationExcelConfigData.json")?;
        let anecdote = index_unique(
            deob::deobfuscate_anecdote_excel_config_data(list("AnecdoteExcelConfigData.json")?)?,
            |d| d.i("id"),
            "anecdote ID",
        )?;
        Ok(Excels {
            talk_excel: talk_excel?,
            npc_excel: list("NpcExcelConfigData.json")?,
            dialog_maps,
            localization,
            document,
            book_suit: to_fx(index_unique(
                list("BookSuitExcelConfigData.json")?,
                |d| d.i("id"),
                "book suit ID",
            )?),
            books_codex: list("BooksCodexExcelConfigData.json")?,
            material,
            achievement_excel: list("AchievementExcelConfigData.json")?,
            achievement_goal: list("AchievementGoalExcelConfigData.json")?,
            anecdote,
            blossom_talk: list("BlossomTalkExcelConfigData.json")?,
            blossom_refresh: to_fx(index_unique(
                list("BlossomRefreshExcelConfigData.json")?,
                |d| d.i("id"),
                "blossom refresh ID",
            )?),
            city_config: to_fx(index_unique(
                list("CityConfigData.json")?,
                |d| d.i("cityId"),
                "city ID",
            )?),
            coop_interaction: list("CoopInteractionExcelConfigData.json")?,
            coop_chapter: list("CoopChapterExcelConfigData.json")?,
            avatar_excel: list("AvatarExcelConfigData.json")?,
            skill_depot: to_fx(index_unique(
                list("AvatarSkillDepotExcelConfigData.json")?,
                |d| d.i("id"),
                "skill depot ID",
            )?),
            talent: to_fx(index_unique(
                list("AvatarTalentExcelConfigData.json")?,
                |d| d.i("talentId"),
                "talent ID",
            )?),
            skill: to_fx(index_unique(
                list("AvatarSkillExcelConfigData.json")?,
                |d| d.i("id"),
                "skill ID",
            )?),
            fetter_story: list("FetterStoryExcelConfigData.json")?,
            fetters: list("FettersExcelConfigData.json")?,
            animal_codex: index_unique(
                list("AnimalCodexExcelConfigData.json")?,
                |d| d.i("id"),
                "animal codex ID",
            )?,
            monster_describe: to_fx(index_unique(
                list("MonsterDescribeExcelConfigData.json")?,
                |d| d.i("id"),
                "monster describe ID",
            )?),
            monster_title: to_fx(index_unique(
                list("MonsterTitleExcelConfigData.json")?,
                |d| d.i("titleID"),
                "monster title ID",
            )?),
            monster_special_name: list("MonsterSpecialNameExcelConfigData.json")?,
            animal_describe: to_fx(index_unique(
                list("AnimalDescribeExcelConfigData.json")?,
                |d| d.i("id"),
                "animal describe ID",
            )?),
            main_quest: index_unique(
                list("MainQuestExcelConfigData.json")?,
                |d| d.i("id"),
                "main quest ID",
            )?,
            chapter: index_unique(
                list("ChapterExcelConfigData.json")?,
                |d| d.i("id"),
                "chapter ID",
            )?,
            new_activity: index_unique(
                list("NewActivityExcelConfigData.json")?,
                |d| d.i("activityId"),
                "activity ID",
            )?,
            reliquary_set: list("ReliquarySetExcelConfigData.json")?,
            reliquary: list("ReliquaryExcelConfigData.json")?,
            equip_affix: list("EquipAffixExcelConfigData.json")?,
            weapon_excel: index_unique(
                list("WeaponExcelConfigData.json")?,
                |d| d.i("id"),
                "weapon ID",
            )?,
            quest_excel: list("QuestExcelConfigData.json")?,
            home_world_npc: list("HomeWorldNPCExcelConfigData.json")?,
            role_combat_tarot: list("RoleCombatTarotAvatarExcelConfigData.json")?,
            gcg_week_level: list("GCGWeekLevelExcelConfigData.json")?,
        })
    }

    fn load_misc(agd_path: &Path, first_seen_dir: &Path, language_short: &str) -> Result<Misc> {
        let readable_dir = agd_path.join("Readable").join(language_short);
        let readable_names: Vec<String> = list_dir_files(&readable_dir)?
            .into_iter()
            .filter(|n| n.ends_with(".txt"))
            .collect();
        let readable_contents: FxHashMap<String, String> = readable_names
            .par_iter()
            .map(|name| {
                let content = std::fs::read_to_string(readable_dir.join(name))
                    .with_context(|| format!("read readable {name}"))?;
                Ok((name.clone(), util::py_strip(&content).to_string()))
            })
            .collect::<Result<_>>()?;

        let subtitle_names = list_dir_files(&agd_path.join("Subtitle").join(language_short))?;

        let cutscene_dir = agd_path.join("BinOutput").join("Cutscene");
        let mut cutscene_names = list_dir_files(&cutscene_dir)?;
        cutscene_names.retain(|n| n.ends_with(".json"));
        let cutscene_files: Vec<(String, Value)> = cutscene_names
            .par_iter()
            .map(|name| Ok((name.clone(), parse_json(&cutscene_dir.join(name))?)))
            .collect::<Result<_>>()?;

        let coop_dir = agd_path.join("BinOutput").join("Coop");
        let mut coop_names = list_dir_files(&coop_dir)?;
        coop_names.retain(|n| n.ends_with(".json"));
        let coop_graph_files: Vec<Value> = coop_names
            .par_iter()
            .map(|name| parse_json(&coop_dir.join(name)))
            .collect::<Result<_>>()?;

        let first_seen = FirstSeenIndex::load(first_seen_dir)?;

        Ok(Misc {
            readable_contents,
            subtitle_names,
            cutscene_files,
            coop_graph_files,
            first_seen,
        })
    }

    // --- tracker-equivalent accessors ---

    /// TalkTracker.get_talk_file_path: tracks any excel-known talk id.
    pub fn get_talk_file_path(&self, talk_id: i64, scope: &Scope) -> Option<&String> {
        if !self.talk_ids_all.contains(&talk_id) {
            return None;
        }
        scope.talks.borrow_mut().insert(talk_id);
        self.parse.talk_id_to_path.get(&talk_id)
    }

    /// ReadablesTracker.get_content: tracks known filenames.
    pub fn readable_content(&self, filename: &str, scope: &Scope) -> Option<&String> {
        if !self.readable_filenames.contains(filename) {
            return None;
        }
        scope.readables.borrow_mut().insert(filename.to_string());
        Some(&self.readable_contents[filename])
    }

    pub fn npc_source_name(&self, npc_id: i64) -> Option<&String> {
        // CHS build: the source (CHS) map IS the output map.
        self.npc_id_to_name.get(&npc_id)
    }
}

struct Excels {
    talk_excel: Vec<Value>,
    npc_excel: Vec<Value>,
    dialog_maps: (FxHashMap<i64, i64>, FxHashMap<i64, i64>),
    localization: Vec<Value>,
    document: IndexMap<i64, Value>,
    book_suit: FxHashMap<i64, Value>,
    books_codex: Vec<Value>,
    material: IndexMap<i64, Value>,
    achievement_excel: Vec<Value>,
    achievement_goal: Vec<Value>,
    anecdote: IndexMap<i64, Value>,
    blossom_talk: Vec<Value>,
    blossom_refresh: FxHashMap<i64, Value>,
    city_config: FxHashMap<i64, Value>,
    coop_interaction: Vec<Value>,
    coop_chapter: Vec<Value>,
    avatar_excel: Vec<Value>,
    skill_depot: FxHashMap<i64, Value>,
    talent: FxHashMap<i64, Value>,
    skill: FxHashMap<i64, Value>,
    fetter_story: Vec<Value>,
    fetters: Vec<Value>,
    animal_codex: IndexMap<i64, Value>,
    monster_describe: FxHashMap<i64, Value>,
    monster_title: FxHashMap<i64, Value>,
    monster_special_name: Vec<Value>,
    animal_describe: FxHashMap<i64, Value>,
    main_quest: IndexMap<i64, Value>,
    chapter: IndexMap<i64, Value>,
    new_activity: IndexMap<i64, Value>,
    reliquary_set: Vec<Value>,
    reliquary: Vec<Value>,
    equip_affix: Vec<Value>,
    weapon_excel: IndexMap<i64, Value>,
    quest_excel: Vec<Value>,
    home_world_npc: Vec<Value>,
    role_combat_tarot: Vec<Value>,
    gcg_week_level: Vec<Value>,
}

struct Misc {
    readable_contents: FxHashMap<String, String>,
    subtitle_names: Vec<String>,
    cutscene_files: Vec<(String, Value)>,
    coop_graph_files: Vec<Value>,
    first_seen: FirstSeenIndex,
}
