//! Port of istaroth.agd.repo.DataRepo: eager loading of all AGD inputs plus
//! every derived mapping generate-all consumes.

use crate::coop::CoopStoryGraph;
use crate::firstseen::FirstSeenIndex;
use crate::issues::Scope;
use crate::lang::Language;
use crate::talkparse::TalkParseResult;
use crate::textmap::TextMaps;
use crate::vh::{ValueExt, int_array};
use crate::{coop, deob, talkparse, util};
use anyhow::{Context, Result, anyhow, bail};
use rayon::prelude::*;
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;
use std::path::{Path, PathBuf};

/// Dialog id -> content-hash and dialog id -> role-name-hash maps.
type DialogMaps = (FxHashMap<i64, i64>, FxHashMap<i64, i64>);

/// Raw excel tables loaded directly from ExcelBinOutput files (exposed as
/// `Repo::excel`); derived mappings stay flat on `Repo`.
#[derive(Default)]
pub struct Excels {
    pub talk: Vec<Value>,
    pub npc: Vec<Value>,
    pub localization: Vec<Value>,
    pub document: FxHashMap<i64, Value>,
    pub book_suit: FxHashMap<i64, Value>,
    pub books_codex: Vec<Value>,
    pub material: FxHashMap<i64, Value>,
    /// Consumed (taken) by the achievement-sections builder during load;
    /// empty on the finished Repo.
    pub achievement: Vec<Value>,
    /// See `achievement`.
    pub achievement_goal: Vec<Value>,
    pub anecdote: FxHashMap<i64, Value>,
    pub blossom_talk: Vec<Value>,
    pub blossom_refresh: FxHashMap<i64, Value>,
    pub city_config: FxHashMap<i64, Value>,
    pub coop_interaction: Vec<Value>,
    pub coop_chapter: Vec<Value>,
    pub avatar: FxHashMap<i64, Value>,
    pub skill_depot: FxHashMap<i64, Value>,
    pub talent: FxHashMap<i64, Value>,
    pub skill: FxHashMap<i64, Value>,
    pub fetter_story: Vec<Value>,
    pub fetters: Vec<Value>,
    pub animal_codex: FxHashMap<i64, Value>,
    pub monster_describe: FxHashMap<i64, Value>,
    pub monster_title: FxHashMap<i64, Value>,
    /// Keyed by specialNameLabID; several rows may share a lab id.
    pub monster_special_name: FxHashMap<i64, Vec<Value>>,
    pub animal_describe: FxHashMap<i64, Value>,
    pub main_quest: FxHashMap<i64, Value>,
    pub chapter: FxHashMap<i64, Value>,
    pub new_activity: FxHashMap<i64, Value>,
    /// Kept as a list: ArtifactSets discovery order is file order.
    pub reliquary_set: Vec<Value>,
    pub reliquary: FxHashMap<i64, Value>,
    /// Keyed by id; per-level rows share an id and the first row wins.
    pub equip_affix: FxHashMap<i64, Value>,
    pub weapon: FxHashMap<i64, Value>,
    pub quest: Vec<Value>,
    pub home_world_npc: Vec<Value>,
    pub role_combat_tarot: Vec<Value>,
    pub gcg_week_level: Vec<Value>,
}

#[derive(Default)]
pub struct Repo {
    pub agd_path: PathBuf,
    pub language: Language,
    pub tm: TextMaps,
    /// The CHS (source) text maps when the output language is not CHS; None
    /// when source == output. Dev/test markers ($HIDDEN, (test), beta测试任务)
    /// exist only in CHS text, so hidden filtering consults these via the
    /// `source_*` accessors regardless of the output language.
    pub(crate) tm_chs: Option<TextMaps>,
    pub first_seen: FirstSeenIndex,

    /// Raw excel tables.
    pub excel: Excels,

    pub talk_ids_all: FxHashSet<i64>,
    pub talk_files: FxHashMap<String, Value>,
    pub quest_files: FxHashMap<String, Value>,
    pub quest_mapping: FxHashMap<i64, String>,

    pub parse: TalkParseResult,

    // Derived mappings.
    pub readable_stem_to_loc_id: FxHashMap<String, i64>,
    pub loc_id_to_readable_filename: FxHashMap<i64, String>,
    pub loc_id_to_title_hash: FxHashMap<i64, i64>,
    pub book_series: FxHashMap<i64, Vec<String>>,
    pub achievement_sections: FxHashMap<i64, (Value, Vec<Value>)>,
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
    /// NPC id -> CHS (source) name when the output language is not CHS; None
    /// when source == output (see `npc_chs_name`).
    pub(crate) npc_id_to_chs_name: Option<FxHashMap<i64, String>>,
    pub activity_id_to_name: FxHashMap<i64, String>,
    pub npc_id_to_game_mode: FxHashMap<i64, &'static str>,

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
/// Keys are deobfuscated then indexed strictly (missing field -> error;
/// duplicate ids -> last wins).
fn parse_dialog_excel(path: &Path) -> Result<DialogMaps> {
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
) -> Result<FxHashMap<i64, Value>> {
    let mut map = FxHashMap::with_capacity_and_hasher(data.len(), Default::default());
    for item in data {
        let k = key(&item)?;
        if map.insert(k, item).is_some() {
            bail!("Duplicate {what}: {k}");
        }
    }
    Ok(map)
}

/// File names directly under `dir` (empty for a missing dir); any other read
/// error propagates instead of silently yielding an empty (and thus quietly
/// truncated) corpus section.
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

fn log_elapsed(verbose: bool, name: &str, t: std::time::Instant) {
    if verbose {
        eprintln!("  [load] {name}: {:.2}s", t.elapsed().as_secs_f64());
    }
}

fn run_timed<T>(verbose: bool, name: &str, f: impl FnOnce() -> T) -> T {
    let t = std::time::Instant::now();
    let result = f();
    log_elapsed(verbose, name, t);
    result
}

// --- derived-mapping builders (one per mapping) ---

/// Quest id -> BinOutput/Quest file path. AGD retains stale hash-named
/// duplicates of quests across builds, so when several files share an ID the
/// canonically-named `{id}.json` wins.
fn build_quest_mapping(quest_files: &FxHashMap<String, Value>) -> Result<FxHashMap<i64, String>> {
    let mut quest_mapping: FxHashMap<i64, String> = FxHashMap::default();
    let mut entries: Vec<(&String, &Value)> = quest_files.iter().collect();
    entries.sort_by_key(|(rel, _)| *rel);
    for (rel, quest_data) in entries {
        let quest_id = quest_data.i("id").context("quest file id")?;
        let canonical = format!("BinOutput/Quest/{quest_id}.json");
        if let Some(existing) = quest_mapping.get(&quest_id)
            && (*existing == canonical || *rel != canonical)
        {
            continue;
        }
        quest_mapping.insert(quest_id, rel.clone());
    }
    Ok(quest_mapping)
}

/// Language-scoped readable path values of one localization entry (sorted
/// field order): paths ending in `_<lang>` or containing a `<lang>` path
/// component.
fn localization_readable_paths<'a>(
    entry: &'a Value,
    language_short: &'a str,
    language_suffix: &'a str,
) -> impl Iterator<Item = &'a str> {
    entry
        .as_object()
        .into_iter()
        .flat_map(|o| o.values())
        .filter_map(|v| v.as_str())
        .filter(move |p| {
            p.ends_with(language_suffix) || p.split('/').any(|part| part == language_short)
        })
}

/// Localization-derived maps (single pass, sorted field order per entry):
/// readable stem -> localization id, and localization id -> readable
/// filename. First match wins for each key.
fn build_readable_localization_maps(
    localization: &[Value],
    language_short: &str,
) -> Result<(FxHashMap<String, i64>, FxHashMap<i64, String>)> {
    let mut readable_stem_to_loc_id = FxHashMap::default();
    let mut loc_id_to_readable_filename = FxHashMap::default();
    let language_suffix = format!("_{language_short}");
    for entry in localization {
        let id = entry.i("id")?;
        for path_str in localization_readable_paths(entry, language_short, &language_suffix) {
            let name = util::path_name(path_str);
            readable_stem_to_loc_id
                .entry(name.to_string())
                .or_insert(id);
            loc_id_to_readable_filename
                .entry(id)
                .or_insert_with(|| format!("{name}.txt"));
        }
    }
    Ok((readable_stem_to_loc_id, loc_id_to_readable_filename))
}

/// Localization id -> document title hash; the lowest-id document wins per
/// loc id (documents are visited in id order, so first-wins is deterministic).
fn build_loc_id_to_title_hash(document: &FxHashMap<i64, Value>) -> Result<FxHashMap<i64, i64>> {
    let mut loc_id_to_title_hash = FxHashMap::default();
    let mut docs: Vec<(&i64, &Value)> = document.iter().collect();
    docs.sort_by_key(|(id, _)| *id);
    for (_, doc) in docs {
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
    Ok(loc_id_to_title_hash)
}

/// Group multi-volume book series to their ordered volume readable filenames.
///
/// Active book-codex entries are grouped by their material's suit (`setID`)
/// and ordered by `sortOrder`; only suits with two or more volumes count as a
/// series (single-volume and non-codex books stay standalone). Each volume
/// resolves material id -> document -> localization -> readable filename (the
/// material id and document id coincide for books). Errors if a volume claims
/// a suit or readable that can't be resolved, surfacing the data gap rather
/// than silently dropping the grouping.
fn build_book_series(
    excel: &Excels,
    loc_id_to_readable_filename: &FxHashMap<i64, String>,
) -> Result<FxHashMap<i64, Vec<String>>> {
    let mut book_series_grouped: FxHashMap<i64, Vec<String>> = FxHashMap::default();
    let mut codexes: Vec<(i64, &Value)> = excel
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
        let material = excel
            .material
            .get(&material_id)
            .ok_or_else(|| anyhow!("Book codex references unknown material {material_id}"))?;
        let suit_id = material.i("setID")?;
        if suit_id == 0 {
            continue;
        }
        if !excel.book_suit.contains_key(&suit_id) {
            bail!("Book material {material_id} claims unknown suit {suit_id}");
        }
        let document = excel
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
    Ok(book_series_grouped
        .into_iter()
        .filter(|(_, filenames)| filenames.len() >= 2)
        .collect())
}

/// Achievement sections: goal entry plus its (orderId, id)-sorted achievements.
/// Takes both tables by value: nothing reads them after this builder.
fn build_achievement_sections(
    achievement_goal: Vec<Value>,
    achievement: Vec<Value>,
) -> Result<FxHashMap<i64, (Value, Vec<Value>)>> {
    let mut achievement_sections: FxHashMap<i64, (Value, Vec<Value>)> = FxHashMap::default();
    for section in achievement_goal {
        let id = section.i("id")?;
        if achievement_sections
            .insert(id, (section, Vec::new()))
            .is_some()
        {
            bail!("Duplicate achievement section ID");
        }
    }
    for achievement in achievement {
        if achievement.b("isDisuse")? {
            continue;
        }
        let goal_id = achievement.i("goalId")?;
        let section = achievement_sections
            .get_mut(&goal_id)
            .ok_or_else(|| anyhow!("Achievement references unknown section {goal_id}"))?;
        section.1.push(achievement);
    }
    for (_, achievements) in achievement_sections.values_mut() {
        let mut keyed: Vec<(i64, i64, Value)> = achievements
            .drain(..)
            .map(|a| Ok((a.i("orderId")?, a.i("id")?, a)))
            .collect::<Result<_>>()?;
        keyed.sort_by_key(|(order_id, id, _)| (*order_id, *id));
        achievements.extend(keyed.into_iter().map(|(_, _, a)| a));
    }
    Ok(achievement_sections)
}

/// Storyboard quest -> talk ids.
fn build_storyboard_quest_to_talk_ids(talk_excel: &[Value]) -> Result<FxHashMap<i64, Vec<i64>>> {
    let mut storyboard_quest_to_talk_ids: FxHashMap<i64, Vec<i64>> = FxHashMap::default();
    for entry in talk_excel {
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
    Ok(storyboard_quest_to_talk_ids)
}

/// Coop story graphs.
fn build_coop_graphs(coop_graph_files: Vec<Value>) -> Result<FxHashMap<i64, CoopStoryGraph>> {
    let mut coop_graphs: FxHashMap<i64, CoopStoryGraph> = FxHashMap::default();
    for data in coop_graph_files {
        let data = deob::deobfuscate_coop_graph_data(data)?;
        let stories = data
            .f("coopInteractionMap")?
            .as_object()
            .ok_or_else(|| anyhow!("coopInteractionMap must be an object"))?;
        for story in stories.values() {
            let graph = coop::build_story_graph(story)?;
            coop_graphs.insert(graph.coop_story_id, graph);
        }
    }
    Ok(coop_graphs)
}

/// Hangout quest -> coop stories with talk files.
fn build_hangout_quest_to_stories(
    coop_interaction: &[Value],
    parse: &TalkParseResult,
) -> Result<FxHashMap<i64, Vec<i64>>> {
    let mut hangout_quest_to_stories: FxHashMap<i64, Vec<i64>> = FxHashMap::default();
    for entry in coop_interaction {
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
    Ok(hangout_quest_to_stories)
}

fn build_coop_chapter_to_avatar(coop_chapter: &[Value]) -> Result<FxHashMap<i64, i64>> {
    let mut coop_chapter_to_avatar = FxHashMap::default();
    for chapter in coop_chapter {
        coop_chapter_to_avatar.insert(chapter.i("id")?, chapter.i("avatarId")?);
    }
    Ok(coop_chapter_to_avatar)
}

/// `id` -> resolvable `nameTextMapHash` text (shared by avatar and npc excels).
fn build_id_to_name<'a>(
    entries: impl IntoIterator<Item = &'a Value>,
    tm: &TextMaps,
    scope: &Scope,
) -> Result<FxHashMap<i64, String>> {
    let mut id_to_name = FxHashMap::default();
    for entry in entries {
        if let Some(name) = tm.get_optional(entry.i("nameTextMapHash")?, scope)? {
            id_to_name.insert(entry.i("id")?, name);
        }
    }
    Ok(id_to_name)
}

/// Like `build_id_to_name` against the CHS source map, untracked: source-map
/// lookups never count toward text-map usage stats.
fn build_id_to_chs_name(entries: &[Value], tm_chs: &TextMaps) -> Result<FxHashMap<i64, String>> {
    let mut id_to_name = FxHashMap::default();
    for entry in entries {
        if let Some(name) = tm_chs.get_optional_untracked(entry.i("nameTextMapHash")?)? {
            id_to_name.insert(entry.i("id")?, name);
        }
    }
    Ok(id_to_name)
}

fn build_activity_id_to_name(
    new_activity: &FxHashMap<i64, Value>,
    tm: &TextMaps,
    scope: &Scope,
) -> Result<FxHashMap<i64, String>> {
    let mut activity_id_to_name = FxHashMap::default();
    for (activity_id, entry) in new_activity {
        if let Some(name) = tm.get_optional(entry.i("nameTextMapHash")?, scope)? {
            activity_id_to_name.insert(*activity_id, name);
        }
    }
    Ok(activity_id_to_name)
}

fn build_npc_id_to_game_mode(
    excel: &Excels,
    language: Language,
) -> Result<FxHashMap<i64, &'static str>> {
    let mut npc_id_to_game_mode: FxHashMap<i64, &'static str> = FxHashMap::default();
    let mode_lists: [(&'static str, Vec<i64>); 3] = [
        (
            match language {
                Language::Chs => "尘歌壶",
                Language::Eng => "Serenitea Pot",
            },
            excel
                .home_world_npc
                .iter()
                .map(|e| e.i("npcID"))
                .collect::<Result<_>>()?,
        ),
        (
            match language {
                Language::Chs => "幻想真境剧诗",
                Language::Eng => "Imaginarium Theater",
            },
            excel
                .role_combat_tarot
                .iter()
                .map(|e| e.i("npcId"))
                .collect::<Result<_>>()?,
        ),
        (
            match language {
                Language::Chs => "七圣召唤",
                Language::Eng => "Genius Invokation TCG",
            },
            excel
                .gcg_week_level
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
    Ok(npc_id_to_game_mode)
}

fn build_sub_quest_to_main(quest_excel: &[Value]) -> Result<FxHashMap<i64, i64>> {
    let mut sub_quest_to_main = FxHashMap::default();
    for quest in quest_excel {
        sub_quest_to_main.insert(quest.i("subId")?, quest.i("mainId")?);
    }
    Ok(sub_quest_to_main)
}

/// Talk id -> owning quest id (`TalkExcelConfigData.questId`). Checked against
/// the quest BinOutput files' own talk lists: TalkExcel is a strict superset
/// with no disagreements, so it is the single source.
fn build_talk_to_quest(talk_excel: &[Value]) -> Result<FxHashMap<i64, i64>> {
    let mut talk_to_quest = FxHashMap::default();
    for talk_item in talk_excel {
        let quest_id = talk_item.i("questId")?;
        if quest_id != 0 {
            talk_to_quest.insert(talk_item.i("id")?, quest_id);
        }
    }
    Ok(talk_to_quest)
}

/// Localization id -> language-suffixed subtitle stems.
fn build_localization_id_to_stems(
    localization: &[Value],
    language_short: &str,
) -> Result<FxHashMap<i64, Vec<String>>> {
    let mut localization_id_to_stems: FxHashMap<i64, Vec<String>> = FxHashMap::default();
    let language_suffix = format!("_{language_short}");
    for entry in localization {
        let id = entry.i("id")?;
        for path_value in entry.as_object().into_iter().flat_map(|o| o.values()) {
            let Some(path_str) = path_value.as_str() else {
                continue;
            };
            let stem = util::path_stem(path_str);
            if stem.ends_with(&language_suffix) {
                localization_id_to_stems
                    .entry(id)
                    .or_default()
                    .push(stem.to_string());
            }
        }
    }
    Ok(localization_id_to_stems)
}

/// Fold one cutscene variant's video/subtitle references into the stem sets.
fn collect_cutscene_variant_stems(
    variant: &Value,
    cutscene_id: i64,
    language_short: &str,
    localization_id_to_stems: &FxHashMap<i64, Vec<String>>,
    subtitle_stem_sets: &mut FxHashMap<String, FxHashSet<i64>>,
) -> Result<()> {
    let Some(video_config) = variant.get("videoConfig") else {
        return Ok(());
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
    Ok(())
}

/// Subtitle file stem -> ids of the cutscenes that play it.
///
/// A video cutscene binds its subtitle track by `subtitleId` into
/// LocalizationExcelConfigData, whose per-language path stem equals the
/// `Subtitle/<lang>` file stem, and names its videos after the stem minus the
/// language suffix (per traveler variant). Both links are indexed: the
/// localization one also covers subtitle files shared by both traveler
/// variants, whose stems carry no `_Boy`/`_Girl` marker.
fn build_subtitle_stem_map(
    localization: &[Value],
    cutscene_files: &[(String, Value)],
    language_short: &str,
) -> Result<FxHashMap<String, Vec<i64>>> {
    let localization_id_to_stems = build_localization_id_to_stems(localization, language_short)?;
    let mut subtitle_stem_sets: FxHashMap<String, FxHashSet<i64>> = FxHashMap::default();
    for (path, data) in cutscene_files {
        let cutscene_id: i64 = util::path_stem(path).parse().context("cutscene stem")?;
        let variants = data
            .as_object()
            .ok_or_else(|| anyhow!("cutscene file {path} must be an object"))?;
        for variant in variants.values() {
            if !variant.is_object() {
                bail!("cutscene variant in {path} must be an object");
            }
            collect_cutscene_variant_stems(
                variant,
                cutscene_id,
                language_short,
                &localization_id_to_stems,
                &mut subtitle_stem_sets,
            )?;
        }
    }
    Ok(subtitle_stem_sets
        .into_iter()
        .map(|(stem, ids)| {
            let mut v: Vec<i64> = ids.into_iter().collect();
            v.sort();
            (stem, v)
        })
        .collect())
}

/// Everything phase A loads in parallel before the derived mappings.
struct Inputs {
    tm: TextMaps,
    tm_chs: Option<TextMaps>,
    talk_files: FxHashMap<String, Value>,
    talk_file_rels: Vec<String>,
    quest_files: FxHashMap<String, Value>,
    excel: Excels,
    dialog_maps: DialogMaps,
    misc: Misc,
}

impl Repo {
    /// `load_scope` collects text-map accesses made while building the derived
    /// name mappings; the caller folds it into the run's usage stats after all
    /// passes.
    pub fn load(
        agd_path: &Path,
        first_seen_dir: &Path,
        language: Language,
        verbose: bool,
        load_scope: &Scope,
    ) -> Result<Repo> {
        let language_short = language.short();
        let Inputs {
            tm,
            tm_chs,
            talk_files,
            talk_file_rels,
            quest_files,
            mut excel,
            dialog_maps,
            misc,
        } = Self::load_inputs(agd_path, first_seen_dir, language, verbose)?;

        let talk_ids_all: FxHashSet<i64> = excel
            .talk
            .iter()
            .map(|t| t.i("id"))
            .collect::<Result<_>>()?;

        // Talk parser (needs talk files + text map + talk excel init dialogs).
        let mut init_dialogs = FxHashMap::default();
        for entry in &excel.talk {
            let init = entry.i("initDialog")?;
            if init != 0 {
                init_dialogs.insert(entry.i("id")?, init);
            }
        }
        let parse = run_timed(verbose, "talk parser", || {
            talkparse::parse_talks(&talk_files, &talk_file_rels, &tm, &init_dialogs)
        })?;
        let t_rest = std::time::Instant::now();

        let quest_mapping = build_quest_mapping(&quest_files)?;
        let (readable_stem_to_loc_id, loc_id_to_readable_filename) =
            build_readable_localization_maps(&excel.localization, language_short)?;
        let loc_id_to_title_hash = build_loc_id_to_title_hash(&excel.document)?;
        let book_series = build_book_series(&excel, &loc_id_to_readable_filename)?;
        let achievement_sections = build_achievement_sections(
            std::mem::take(&mut excel.achievement_goal),
            std::mem::take(&mut excel.achievement),
        )?;
        let storyboard_quest_to_talk_ids = build_storyboard_quest_to_talk_ids(&excel.talk)?;
        let coop_graphs = build_coop_graphs(misc.coop_graph_files)?;
        let hangout_quest_to_stories =
            build_hangout_quest_to_stories(&excel.coop_interaction, &parse)?;
        let coop_chapter_to_avatar = build_coop_chapter_to_avatar(&excel.coop_chapter)?;
        let avatar_id_to_name = build_id_to_name(excel.avatar.values(), &tm, load_scope)?;
        let npc_id_to_name = build_id_to_name(&excel.npc, &tm, load_scope)?;
        let npc_id_to_chs_name = tm_chs
            .as_ref()
            .map(|src| build_id_to_chs_name(&excel.npc, src))
            .transpose()?;
        let activity_id_to_name = build_activity_id_to_name(&excel.new_activity, &tm, load_scope)?;
        let npc_id_to_game_mode = build_npc_id_to_game_mode(&excel, language)?;
        let sub_quest_to_main = build_sub_quest_to_main(&excel.quest)?;
        let talk_to_quest = build_talk_to_quest(&excel.talk)?;
        let subtitle_stem_to_cutscenes =
            build_subtitle_stem_map(&excel.localization, &misc.cutscene_files, language_short)?;

        let (dialog_id_to_content_hash, dialog_id_to_role_hash) = dialog_maps;

        let mut readable_filenames_sorted: Vec<String> =
            misc.readable_contents.keys().cloned().collect();
        readable_filenames_sorted.sort();

        log_elapsed(verbose, "derived mappings", t_rest);
        Ok(Repo {
            agd_path: agd_path.to_path_buf(),
            language,
            tm,
            tm_chs,
            first_seen: misc.first_seen,
            excel,
            talk_ids_all,
            talk_files,
            quest_files,
            quest_mapping,
            parse,
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
            npc_id_to_chs_name,
            activity_id_to_name,
            npc_id_to_game_mode,
            readable_contents: misc.readable_contents,
            readable_filenames_sorted,
            subtitle_names: misc.subtitle_names,
        })
    }

    /// All independent loads run on the rayon pool.
    fn load_inputs(
        agd_path: &Path,
        first_seen_dir: &Path,
        language: Language,
        verbose: bool,
    ) -> Result<Inputs> {
        let language_short = language.short();
        let excel_dir = agd_path.join("ExcelBinOutput");

        // Talk excel: split files or the single one.
        let load_talk_excel = || -> Result<Vec<Value>> {
            let split: Vec<String> = list_dir_files(&excel_dir)?
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
                let v = parse_json(&excel_dir.join(&name))?;
                let Value::Array(items) = v else {
                    bail!("{name} must be a list");
                };
                data.extend(items);
            }
            Ok(data)
        };

        let t0 = std::time::Instant::now();
        let ((tm, tm_chs), (talk_files_res, (quest_files_res, (excels_res, misc_res)))) =
            rayon::join(
                || {
                    run_timed(verbose, "text maps", || {
                        rayon::join(
                            || TextMaps::load(agd_path, language),
                            || {
                                (language != Language::Chs)
                                    .then(|| TextMaps::load(agd_path, Language::Chs))
                                    .transpose()
                            },
                        )
                    })
                },
                || {
                    rayon::join(
                        || run_timed(verbose, "talk files", || Self::load_talk_files(agd_path)),
                        || {
                            rayon::join(
                                || {
                                    run_timed(verbose, "quest files", || {
                                        Self::load_quest_files(agd_path)
                                    })
                                },
                                || {
                                    rayon::join(
                                        || {
                                            run_timed(verbose, "excels", || {
                                                Self::load_excels(&excel_dir, load_talk_excel)
                                            })
                                        },
                                        || {
                                            run_timed(verbose, "misc", || {
                                                Self::load_misc(
                                                    agd_path,
                                                    first_seen_dir,
                                                    language_short,
                                                )
                                            })
                                        },
                                    )
                                },
                            )
                        },
                    )
                },
            );
        log_elapsed(verbose, "phase A total", t0);
        let (talk_files, talk_file_rels) = talk_files_res?;
        let (excel, dialog_maps) = excels_res?;
        Ok(Inputs {
            tm: tm?,
            tm_chs: tm_chs?,
            talk_files,
            talk_file_rels,
            quest_files: quest_files_res?,
            excel,
            dialog_maps,
            misc: misc_res?,
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
                let subdir = rel
                    .split('/')
                    .nth(2)
                    .ok_or_else(|| anyhow!("talk path too shallow: {rel}"))?;
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
                    if util::is_ascii_digits(stem)
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
    ) -> Result<(Excels, DialogMaps)> {
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
        // Materials keyed by id: duplicates keep the LAST value.
        let mut material: FxHashMap<i64, Value> = FxHashMap::default();
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
        let excels = Excels {
            talk: talk_excel?,
            npc: list("NpcExcelConfigData.json")?,
            localization,
            document,
            book_suit: index_unique(
                list("BookSuitExcelConfigData.json")?,
                |d| d.i("id"),
                "book suit ID",
            )?,
            books_codex: list("BooksCodexExcelConfigData.json")?,
            material,
            achievement: list("AchievementExcelConfigData.json")?,
            achievement_goal: list("AchievementGoalExcelConfigData.json")?,
            anecdote,
            blossom_talk: list("BlossomTalkExcelConfigData.json")?,
            blossom_refresh: index_unique(
                list("BlossomRefreshExcelConfigData.json")?,
                |d| d.i("id"),
                "blossom refresh ID",
            )?,
            city_config: index_unique(list("CityConfigData.json")?, |d| d.i("cityId"), "city ID")?,
            coop_interaction: list("CoopInteractionExcelConfigData.json")?,
            coop_chapter: list("CoopChapterExcelConfigData.json")?,
            avatar: index_unique(
                list("AvatarExcelConfigData.json")?,
                |d| d.i("id"),
                "avatar ID",
            )?,
            skill_depot: index_unique(
                list("AvatarSkillDepotExcelConfigData.json")?,
                |d| d.i("id"),
                "skill depot ID",
            )?,
            talent: index_unique(
                list("AvatarTalentExcelConfigData.json")?,
                |d| d.i("talentId"),
                "talent ID",
            )?,
            skill: index_unique(
                list("AvatarSkillExcelConfigData.json")?,
                |d| d.i("id"),
                "skill ID",
            )?,
            fetter_story: list("FetterStoryExcelConfigData.json")?,
            fetters: list("FettersExcelConfigData.json")?,
            animal_codex: index_unique(
                list("AnimalCodexExcelConfigData.json")?,
                |d| d.i("id"),
                "animal codex ID",
            )?,
            monster_describe: index_unique(
                list("MonsterDescribeExcelConfigData.json")?,
                |d| d.i("id"),
                "monster describe ID",
            )?,
            monster_title: index_unique(
                list("MonsterTitleExcelConfigData.json")?,
                |d| d.i("titleID"),
                "monster title ID",
            )?,
            monster_special_name: {
                let mut by_lab_id: FxHashMap<i64, Vec<Value>> = FxHashMap::default();
                for entry in list("MonsterSpecialNameExcelConfigData.json")? {
                    by_lab_id
                        .entry(entry.i("specialNameLabID")?)
                        .or_default()
                        .push(entry);
                }
                by_lab_id
            },
            animal_describe: index_unique(
                list("AnimalDescribeExcelConfigData.json")?,
                |d| d.i("id"),
                "animal describe ID",
            )?,
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
            reliquary: index_unique(
                list("ReliquaryExcelConfigData.json")?,
                |d| d.i("id"),
                "reliquary ID",
            )?,
            equip_affix: {
                let mut by_id: FxHashMap<i64, Value> = FxHashMap::default();
                for affix in list("EquipAffixExcelConfigData.json")? {
                    by_id.entry(affix.i("id")?).or_insert(affix);
                }
                by_id
            },
            weapon: index_unique(
                list("WeaponExcelConfigData.json")?,
                |d| d.i("id"),
                "weapon ID",
            )?,
            quest: list("QuestExcelConfigData.json")?,
            home_world_npc: list("HomeWorldNPCExcelConfigData.json")?,
            role_combat_tarot: list("RoleCombatTarotAvatarExcelConfigData.json")?,
            gcg_week_level: list("GCGWeekLevelExcelConfigData.json")?,
        };
        Ok((excels, dialog_maps))
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
                Ok((name.clone(), content.trim().to_string()))
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
        let content = self.readable_contents.get(filename)?;
        scope.readables.borrow_mut().insert(filename.to_string());
        Some(content)
    }

    pub fn npc_chs_name(&self, npc_id: i64) -> Option<&String> {
        // CHS build: the source (CHS) map IS the output map, so the dedicated
        // source-name mapping exists only for other output languages.
        self.npc_id_to_chs_name
            .as_ref()
            .unwrap_or(&self.npc_id_to_name)
            .get(&npc_id)
    }

    // --- CHS (source) text map accessors ---
    //
    // Dev/test markers resolve against the CHS source map, which counts
    // toward usage stats only when it IS the output map (CHS run). So CHS-run
    // lookups track into the scope while non-CHS-run source lookups never do;
    // the tracked/untracked split below encodes that.

    pub fn chs_get_optional(&self, key: i64, scope: &Scope) -> Result<Option<String>> {
        match &self.tm_chs {
            None => self.tm.get_optional(key, scope),
            Some(src) => src.get_optional_untracked(key),
        }
    }

    pub fn chs_get_current_optional(&self, key: i64, scope: &Scope) -> Result<Option<String>> {
        match &self.tm_chs {
            None => self.tm.get_current_optional(key, scope),
            Some(src) => src.get_current_optional_untracked(key),
        }
    }

    pub fn chs_get_optional_untracked(&self, key: i64) -> Result<Option<String>> {
        self.tm_chs
            .as_ref()
            .unwrap_or(&self.tm)
            .get_optional_untracked(key)
    }
}

struct Misc {
    readable_contents: FxHashMap<String, String>,
    subtitle_names: Vec<String>,
    cutscene_files: Vec<(String, Value)>,
    coop_graph_files: Vec<Value>,
    first_seen: FirstSeenIndex,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn book_series_filters_and_orders() {
        let mut excel = Excels {
            book_suit: [(7, json!({"id": 7})), (8, json!({"id": 8}))]
                .into_iter()
                .collect(),
            ..Default::default()
        };
        for (id, suit) in [(101, 7), (102, 7), (103, 8), (104, 0), (105, 7)] {
            excel.material.insert(id, json!({"setID": suit}));
            excel.document.insert(
                id,
                json!({"questIDList": [id], "questContentLocalizedId": []}),
            );
        }
        excel.books_codex = vec![
            json!({"materialId": 102, "sortOrder": 20, "isDisuse": false}),
            json!({"materialId": 101, "sortOrder": 10, "isDisuse": false}),
            json!({"materialId": 103, "sortOrder": 30, "isDisuse": false}),
            json!({"materialId": 104, "sortOrder": 40, "isDisuse": false}),
            json!({"materialId": 105, "sortOrder": 5, "isDisuse": true}),
        ];
        let filenames = (101..=105)
            .map(|id| (id, format!("Book{id}_EN.txt")))
            .collect();
        assert_eq!(
            build_book_series(&excel, &filenames).unwrap(),
            [(
                7,
                vec!["Book101_EN.txt".to_string(), "Book102_EN.txt".to_string()]
            )]
            .into_iter()
            .collect::<FxHashMap<_, _>>()
        );
    }

    #[test]
    fn achievement_sections_filter_only_disused() {
        let achievement_goal = vec![json!({"id": 7})];
        let achievement = vec![
            json!({"id": 3, "goalId": 7, "orderId": 2, "isDisuse": false, "showType": "SHOWTYPE_HIDE"}),
            json!({"id": 2, "goalId": 7, "orderId": 1, "isDisuse": true}),
            json!({"id": 1, "goalId": 7, "orderId": 1, "isDisuse": false}),
        ];
        assert_eq!(
            build_achievement_sections(achievement_goal, achievement).unwrap()[&7]
                .1
                .iter()
                .map(|a| a["id"].as_i64().unwrap())
                .collect::<Vec<_>>(),
            vec![1, 3]
        );
    }
}
