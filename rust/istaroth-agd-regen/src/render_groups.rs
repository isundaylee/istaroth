//! Ports of renderables/{talk_group,hangout,anecdote,blossom,activity}.py.

use crate::coop::{ChoiceBranch, PlayStep};
use crate::firstseen::Domain;
use crate::meta::RenderedItem;
use crate::repo::{IssueType, Repo, Scope};
use crate::talk::{self, TalkInfo, TalkNotFound};
use crate::util;
use crate::vh::{ValueExt, int_array, truthy};
use anyhow::{Result, anyhow, bail};
use indexmap::IndexMap;
use regex::Regex;
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;
use std::sync::LazyLock;

// --- talk groups ---

const SPEAKER_TITLE_LIMIT: usize = 3;
static COMPOSITE_ROLE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^(.+) \((.+)\)$").unwrap());

pub struct TalkGroupInfo {
    pub talks: Vec<(TalkInfo, Vec<TalkInfo>)>,
    pub talk_ids: Vec<i64>,
}

pub fn get_talk_group_info(
    repo: &Repo,
    scope: &Scope,
    group_type: &str,
    group_id: &str,
) -> Result<TalkGroupInfo> {
    let path = repo
        .parse
        .talk_group_id_to_path
        .get(&(group_type.to_string(), group_id.to_string()))
        .ok_or_else(|| anyhow!("unknown talk group {group_type} {group_id}"))?;
    let data = repo
        .talk_files
        .get(path)
        .ok_or_else(|| anyhow!("talk file not loaded: {path}"))?;

    let mut talks = Vec::new();
    let mut talk_ids: Vec<i64> = Vec::new();
    for talk_entry in data.arr("talks")? {
        let talk_id = entry_int(talk_entry.f("id")?)?;
        let talk_info = match talk::get_talk_info_by_id(repo, scope, talk_id) {
            Ok(info) => info,
            Err(e) if e.is::<TalkNotFound>() => {
                scope.record_issue(IssueType::MissingTalk, talk_id.to_string());
                continue;
            }
            Err(e) => return Err(e),
        };
        let mut next_talks = Vec::new();
        let mut next_talk_ids = Vec::new();
        let next_talk_entries: &[Value] = match talk_entry.get("nextTalks") {
            None => &[],
            Some(v) => v
                .as_array()
                .ok_or_else(|| anyhow!("nextTalks must be an array"))?,
        };
        for next_talk_id in next_talk_entries {
            let next_talk_id = entry_int(next_talk_id)?;
            let next_info = match talk::get_talk_info_by_id(repo, scope, next_talk_id) {
                Ok(info) => info,
                Err(e) if e.is::<TalkNotFound>() => {
                    scope.record_issue(IssueType::MissingTalk, next_talk_id.to_string());
                    continue;
                }
                Err(e) => return Err(e),
            };
            if !next_info.text.is_empty() {
                next_talks.push(next_info);
                next_talk_ids.push(next_talk_id);
            }
        }
        if !talk_info.text.is_empty() {
            talks.push((talk_info, next_talks));
            talk_ids.push(talk_id);
            talk_ids.extend(next_talk_ids);
        }
    }
    Ok(TalkGroupInfo { talks, talk_ids })
}

fn entry_int(v: &Value) -> Result<i64> {
    match v {
        Value::Number(_) => crate::vh::as_i64(v),
        Value::String(s) => util::py_int(s),
        other => bail!("cannot int() {other:?}"),
    }
}

const GENERIC_SPEAKERS: [&str; 7] = [
    talk::PLAYER,
    talk::MATE_AVATAR,
    talk::BLACK_SCREEN,
    talk::PAIMON,
    talk::MISSING_TALK_ROLE,
    "???",
    "？？？",
];

pub fn derive_speaker_group_name(info: &TalkGroupInfo) -> Option<String> {
    let mut speakers: IndexMap<String, usize> = IndexMap::new();
    for (talk_info, next_talks) in &info.talks {
        for t in std::iter::once(talk_info).chain(next_talks.iter()) {
            for talk_text in &t.text {
                if talk_text.skip {
                    continue;
                }
                let Some(name) = &talk_text.role else {
                    continue;
                };
                let mut name = name.clone();
                if let Some(m) = COMPOSITE_ROLE.captures(&name) {
                    let g1 = m.get(1).unwrap().as_str();
                    let g2 = m.get(2).unwrap().as_str();
                    name = if GENERIC_SPEAKERS.contains(&g1) {
                        g2.to_string()
                    } else {
                        g1.to_string()
                    };
                }
                if GENERIC_SPEAKERS.contains(&name.as_str()) || name.starts_with(talk::UNKNOWN_ROLE)
                {
                    continue;
                }
                *speakers.entry(name).or_insert(0) += 1;
            }
        }
    }
    if speakers.is_empty() {
        return None;
    }
    // Counter.most_common: stable sort descending by count.
    let mut items: Vec<(&String, usize)> = speakers.iter().map(|(k, v)| (k, *v)).collect();
    items.sort_by_key(|item| std::cmp::Reverse(item.1));
    let mut top: Vec<String> = items
        .iter()
        .take(SPEAKER_TITLE_LIMIT)
        .map(|(name, _)| (*name).clone())
        .collect();
    if speakers.len() > SPEAKER_TITLE_LIMIT {
        top.push("...".to_string());
    }
    Some(top.join(" / "))
}

const GADGET_GROUP_ID_DIGITS: u32 = 9;
const ACTIVITY_GROUP_METADATA_ID_OFFSET: i64 = 1_000_000_000;

pub fn render_talk_group(
    repo: &Repo,
    scope: &Scope,
    group_type: &str,
    group_id: &str,
    info: &TalkGroupInfo,
    group_name: Option<String>,
) -> Result<RenderedItem> {
    let safe_type = util::make_safe_filename_part(group_type);
    let filename = format!("{group_id}_{safe_type}.txt");
    let title = match &group_name {
        Some(name) => format!("{name} ({group_type} {group_id})"),
        None => format!("{group_type} - {group_id}"),
    };

    let mut content_lines = vec![format!("# Talk Group: {title}\n")];
    for (i, (talk_info, next_talks)) in info.talks.iter().enumerate() {
        content_lines.push(format!("## Talk {i}\n"));
        content_lines.extend(talk::render_talk_content(talk_info, scope)?);
        content_lines.push(String::new());
        for (j, next_talk) in next_talks.iter().enumerate() {
            content_lines.push(format!("### Talk {i} related talk {j}\n"));
            content_lines.extend(talk::render_talk_content(next_talk, scope)?);
            content_lines.push(String::new());
        }
    }
    let content = util::py_rstrip(&content_lines.join("\n")).to_string();

    let metadata_id = match group_type {
        "GadgetGroup" => {
            let (config_str, group_str) = group_id
                .split_once('_')
                .ok_or_else(|| anyhow!("bad gadget composite id {group_id}"))?;
            let config_id: i64 = config_str.parse()?;
            let gadget_group_id: i64 = group_str.parse()?;
            config_id * 10i64.pow(GADGET_GROUP_ID_DIGITS) + gadget_group_id
        }
        "ActivityGroup" => ACTIVITY_GROUP_METADATA_ID_OFFSET + util::py_int(group_id)?,
        "NpcGroup" => util::py_int(group_id)?,
        other => bail!("unsupported talk group type {other}"),
    };

    let versions = repo
        .first_seen
        .resolve_ints(Domain::Talk, info.talk_ids.iter().copied())?;
    Ok(RenderedItem::new(
        "agd_talk_group",
        title,
        metadata_id,
        filename,
        versions,
        content,
    ))
}

/// TalkGroups.process.
pub fn process_talk_group(
    repo: &Repo,
    scope: &Scope,
    group_type: &str,
    group_id: &str,
) -> Result<Option<RenderedItem>> {
    let info = get_talk_group_info(repo, scope, group_type, group_id)?;
    if info.talks.is_empty() {
        return Ok(None);
    }
    let group_name: Option<String> = match group_type {
        "NpcGroup" => {
            let npc_id = util::py_int(group_id)?;
            match repo.npc_source_name(npc_id) {
                Some(source_name) => {
                    if util::should_skip_text(source_name) {
                        return Ok(None);
                    }
                    let mut name = repo
                        .npc_id_to_name
                        .get(&npc_id)
                        .ok_or_else(|| anyhow!("npc {npc_id} has no name"))?
                        .clone();
                    if let Some(mode) = repo.npc_id_to_game_mode.get(&npc_id) {
                        name = format!("{name} - {mode}");
                    }
                    Some(name)
                }
                None => None,
            }
        }
        "ActivityGroup" => repo
            .activity_id_to_name
            .get(&util::py_int(group_id)?)
            .cloned(),
        "GadgetGroup" => derive_speaker_group_name(&info),
        other => bail!("unsupported talk group type {other}"),
    };
    Ok(Some(render_talk_group(
        repo, scope, group_type, group_id, &info, group_name,
    )?))
}

// --- hangouts ---

pub struct CondGrp {
    logic: String,
    conds: Vec<(String, Vec<i64>)>,
}

fn parse_cond_grp(raw: &Value) -> Result<CondGrp> {
    let mut conds = Vec::new();
    for e in raw.arr("coopCondList")? {
        conds.push((e.s("type")?.to_string(), int_array(e.f("param")?)?));
    }
    Ok(CondGrp {
        logic: raw.s("condCombType")?.to_string(),
        conds,
    })
}

fn render_cond(cond: &CondGrp) -> String {
    let joiner = match cond.logic.as_str() {
        "LOGIC_AND" => " and ",
        "LOGIC_OR" => " or ",
        _ => ", ",
    };
    cond.conds
        .iter()
        .map(|(t, param)| {
            let params: Vec<String> = param.iter().map(|p| p.to_string()).collect();
            format!("{t} [{}]", params.join(", "))
        })
        .collect::<Vec<_>>()
        .join(joiner)
}

pub enum CoopStep {
    Talk(TalkInfo),
    Choice { id: usize, options: Vec<CoopOption> },
    Ending { save_point_id: i64 },
}

pub struct CoopOption {
    prompt: Option<String>,
    steps: Vec<CoopStep>,
    cond: Option<CondGrp>,
    show_cond: Option<CondGrp>,
}

fn resolve_coop_steps(
    repo: &Repo,
    scope: &Scope,
    play_steps: &[PlayStep],
    local_map: &FxHashMap<i64, String>,
    seen: &mut FxHashSet<i64>,
    next_choice_id: &mut usize,
) -> Result<Vec<CoopStep>> {
    let mut steps = Vec::new();
    for play_step in play_steps {
        match play_step {
            PlayStep::Talk { local_talk_id } => {
                let Some(path) = local_map.get(local_talk_id) else {
                    continue;
                };
                seen.insert(*local_talk_id);
                let talk_info = talk::get_talk_info(repo, scope, path)?;
                if !talk_info.text.is_empty() {
                    steps.push(CoopStep::Talk(talk_info));
                }
            }
            PlayStep::Choice { branches } => {
                let mut options = Vec::new();
                for branch in branches {
                    options.push(resolve_coop_option(
                        repo,
                        scope,
                        branch,
                        local_map,
                        seen,
                        next_choice_id,
                    )?);
                }
                if !options.is_empty() {
                    let id = *next_choice_id;
                    *next_choice_id += 1;
                    steps.push(CoopStep::Choice { id, options });
                }
            }
            PlayStep::End { save_point_id } => {
                steps.push(CoopStep::Ending {
                    save_point_id: *save_point_id,
                });
            }
        }
    }
    Ok(steps)
}

fn resolve_coop_option(
    repo: &Repo,
    scope: &Scope,
    branch: &ChoiceBranch,
    local_map: &FxHashMap<i64, String>,
    seen: &mut FxHashSet<i64>,
    next_choice_id: &mut usize,
) -> Result<CoopOption> {
    // Python walrus truthiness: a content hash of 0 yields no prompt.
    let prompt = match branch.dialog_id {
        Some(dialog_id) => match repo.dialog_id_to_content_hash.get(&dialog_id) {
            Some(&h) if h != 0 => repo.tm.get_optional(h, scope)?,
            _ => None,
        },
        None => None,
    };
    let steps = resolve_coop_steps(repo, scope, &branch.steps, local_map, seen, next_choice_id)?;
    let cond = match &branch.cond_grp {
        Some(v) if truthy(v) => Some(parse_cond_grp(v)?),
        _ => None,
    };
    let show_cond = match &branch.show_cond {
        Some(v) if truthy(v) => Some(parse_cond_grp(v)?),
        _ => None,
    };
    // enableCondGrp is parsed for strict-shape validation (Python stores it
    // too) but never rendered.
    if let Some(v) = &branch.enable_cond
        && truthy(v)
    {
        parse_cond_grp(v)?;
    }
    Ok(CoopOption {
        prompt,
        steps,
        cond,
        show_cond,
    })
}

pub struct HangoutInfo {
    quest_id: i64,
    quest_title: String,
    primary_character: Option<String>,
    stories: Vec<Vec<CoopStep>>,
}

pub fn get_hangout_info(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<HangoutInfo>> {
    let stories = repo
        .hangout_quest_to_stories
        .get(&quest_id)
        .ok_or_else(|| anyhow!("hangout quest {quest_id} has no coop stories"))?;
    let main_quest = repo
        .main_quest
        .get(&quest_id)
        .ok_or_else(|| anyhow!("hangout quest {quest_id} not in main quest table"))?;
    let quest_title = repo
        .tm
        .get_optional(main_quest.i("titleTextMapHash")?, scope)?
        .filter(|t| !t.is_empty())
        .unwrap_or_else(|| format!("Hangout {quest_id}"));

    let primary_character = repo
        .coop_chapter_to_avatar
        .get(&main_quest.i("chapterId")?)
        .and_then(|avatar_id| repo.avatar_id_to_name.get(avatar_id))
        .cloned();

    let mut story_infos: Vec<Vec<CoopStep>> = Vec::new();
    let mut next_choice_id = 0usize;
    for coop_story_id in stories {
        let mut local_map: FxHashMap<i64, String> = FxHashMap::default();
        for path in repo
            .parse
            .coop_story_to_paths
            .get(coop_story_id)
            .ok_or_else(|| anyhow!("coop story {coop_story_id} has no talk files"))?
        {
            let stem = util::path_stem(path);
            let local_id = stem
                .split_once('_')
                .ok_or_else(|| anyhow!("bad coop stem {stem}"))?
                .1;
            local_map.insert(util::py_int(local_id)?, path.clone());
        }
        let mut seen: FxHashSet<i64> = FxHashSet::default();
        let mut steps = match repo.coop_graphs.get(coop_story_id) {
            Some(graph) => {
                let play_order = crate::coop::walk_play_order(graph)?;
                resolve_coop_steps(
                    repo,
                    scope,
                    &play_order,
                    &local_map,
                    &mut seen,
                    &mut next_choice_id,
                )?
            }
            None => Vec::new(),
        };
        let mut sorted_locals: Vec<(&i64, &String)> = local_map.iter().collect();
        sorted_locals.sort();
        for (local_talk_id, path) in sorted_locals {
            if seen.contains(local_talk_id) {
                continue;
            }
            let talk_info = talk::get_talk_info(repo, scope, path)?;
            if !talk_info.text.is_empty() {
                steps.push(CoopStep::Talk(talk_info));
            }
        }
        if !steps.is_empty() {
            story_infos.push(steps);
        }
    }
    if story_infos.is_empty() {
        return Ok(None);
    }
    Ok(Some(HangoutInfo {
        quest_id,
        quest_title,
        primary_character,
        stories: story_infos,
    }))
}

fn assign_fork_numbers(steps: &[CoopStep], counter: &mut i64, mapping: &mut FxHashMap<usize, i64>) {
    for step in steps {
        if let CoopStep::Choice { id, options } = step {
            *counter += 1;
            mapping.insert(*id, *counter);
            for option in options {
                assign_fork_numbers(&option.steps, counter, mapping);
            }
        }
    }
}

fn render_choice_section(
    step: &CoopStep,
    fork_num: i64,
    fork_map: &FxHashMap<usize, i64>,
    scope: &Scope,
) -> Result<(Vec<String>, Vec<Vec<String>>)> {
    let CoopStep::Choice { options, .. } = step else {
        bail!("not a choice step");
    };
    let mut lines: Vec<String> = Vec::new();
    let mut nested: Vec<Vec<String>> = Vec::new();

    lines.push(format!("### Choice {fork_num}"));
    lines.push(String::new());

    for opt in options {
        if let Some(cond) = &opt.cond
            && !cond.conds.is_empty()
        {
            lines.push(format!("*Condition: {}*", render_cond(cond)));
            lines.push(String::new());
            break;
        }
    }

    for (i, option) in options.iter().enumerate() {
        let mut heading = format!("#### Branch {}", i + 1);
        if let Some(prompt) = &option.prompt
            && !prompt.is_empty()
        {
            heading.push_str(&format!(": {prompt}"));
        }
        if let Some(show_cond) = &option.show_cond
            && !show_cond.conds.is_empty()
        {
            heading.push_str(&format!(" (only shown if {})", render_cond(show_cond)));
        }
        if let Some(cond) = &option.cond
            && !cond.conds.is_empty()
        {
            heading.push_str(&format!(" (applies if {})", render_cond(cond)));
        }
        lines.push(heading);
        lines.push(String::new());

        let mut next_marker = "*→ End of conversation*".to_string();
        for step in &option.steps {
            match step {
                CoopStep::Talk(talk_info) => {
                    lines.extend(talk::render_talk_content(talk_info, scope)?);
                }
                CoopStep::Choice { id, .. } => {
                    let nested_fork_num = *fork_map
                        .get(id)
                        .ok_or_else(|| anyhow!("choice {id} missing fork number"))?;
                    next_marker = format!("*→ Next: Choice {nested_fork_num}*");
                    let (section_lines, new_nested) =
                        render_choice_section(step, nested_fork_num, fork_map, scope)?;
                    nested.push(section_lines);
                    nested.extend(new_nested);
                }
                CoopStep::Ending { save_point_id } => {
                    next_marker = format!("*→ Ending (save point {save_point_id})*");
                }
            }
        }
        lines.push(next_marker);
        lines.push(String::new());
    }

    Ok((lines, nested))
}

fn render_coop_steps(
    steps: &[CoopStep],
    fork_map: &FxHashMap<usize, i64>,
    scope: &Scope,
) -> Result<Vec<String>> {
    let mut lines: Vec<String> = Vec::new();
    let mut nested_sections: Vec<Vec<String>> = Vec::new();
    for step in steps {
        match step {
            CoopStep::Talk(talk_info) => {
                let talk_lines = talk::render_talk_content(talk_info, scope)?;
                if !talk_lines.is_empty() {
                    let title = util::py_rstrip(&talk_lines[0]).to_string();
                    lines.push(format!("### Talk: {title}"));
                    lines.push(String::new());
                    lines.extend(talk_lines);
                }
            }
            CoopStep::Choice { id, .. } => {
                let fork_num = *fork_map
                    .get(id)
                    .ok_or_else(|| anyhow!("choice {id} missing fork number"))?;
                let (section_lines, new_nested) =
                    render_choice_section(step, fork_num, fork_map, scope)?;
                lines.push(String::new());
                lines.extend(section_lines);
                nested_sections.extend(new_nested);
            }
            CoopStep::Ending { save_point_id } => {
                lines.push(String::new());
                lines.push(format!("*→ Ending (save point {save_point_id})*"));
            }
        }
    }
    for ns in nested_sections {
        lines.push(String::new());
        lines.extend(ns);
    }
    Ok(lines)
}

pub fn render_hangout(repo: &Repo, scope: &Scope, hangout: &HangoutInfo) -> Result<RenderedItem> {
    let title = match &hangout.primary_character {
        Some(pc) => format!("{pc} - {}", hangout.quest_title),
        None => hangout.quest_title.clone(),
    };
    let filename = format!(
        "{}_{}.txt",
        hangout.quest_id,
        util::make_safe_filename_part(&title)
    );
    let mut content_lines = vec![format!("# Hangout: {title}\n")];
    for (i, story) in hangout.stories.iter().enumerate() {
        content_lines.push(format!("## Conversation {}\n", i + 1));
        let mut counter = 0i64;
        let mut fork_map = FxHashMap::default();
        assign_fork_numbers(story, &mut counter, &mut fork_map);
        content_lines.extend(render_coop_steps(story, &fork_map, scope)?);
    }
    let versions = repo
        .first_seen
        .resolve_int(Domain::MainQuest, hangout.quest_id)?;
    Ok(RenderedItem::new(
        "agd_hangout",
        title,
        hangout.quest_id,
        filename,
        versions,
        util::py_rstrip(&content_lines.join("\n")).to_string(),
    ))
}

// --- anecdotes ---

pub fn process_anecdote(
    repo: &Repo,
    scope: &Scope,
    anecdote_id: i64,
) -> Result<Option<RenderedItem>> {
    let entry = repo
        .anecdote
        .get(&anecdote_id)
        .ok_or_else(|| anyhow!("unknown anecdote {anecdote_id}"))?;
    let mut talks: Vec<TalkInfo> = Vec::new();
    let mut talk_ids: Vec<i64> = Vec::new();
    for quest_id in int_array(entry.f("questIds")?)? {
        for talk_id in repo
            .storyboard_quest_to_talk_ids
            .get(&quest_id)
            .into_iter()
            .flatten()
        {
            let talk_info = match talk::get_talk_info_by_id(repo, scope, *talk_id) {
                Ok(info) => info,
                Err(e) if e.is::<TalkNotFound>() => {
                    scope.record_issue(IssueType::MissingTalk, talk_id.to_string());
                    continue;
                }
                Err(e) => return Err(e),
            };
            if talk_info.has_non_skip_text() {
                talks.push(talk_info);
                talk_ids.push(*talk_id);
            }
        }
    }
    if talks.is_empty() {
        return Ok(None);
    }

    let title = repo
        .tm
        .get_optional(entry.i("titleTextMapHash")?, scope)?
        .filter(|t| !t.is_empty())
        .unwrap_or_else(|| format!("Anecdote {anecdote_id}"));
    let teaser = repo.tm.get_optional(entry.i("teaserTextMapHash")?, scope)?;
    let description = repo.tm.get_optional(entry.i("descTextMapHash")?, scope)?;

    let filename = format!(
        "{anecdote_id}_{}.txt",
        util::make_safe_filename_part(&title)
    );
    let mut content_lines = vec![format!("# {title}\n")];
    for blurb in [&teaser, &description].into_iter().flatten() {
        content_lines.push(blurb.clone());
        content_lines.push(String::new());
    }
    for (i, talk_info) in talks.iter().enumerate() {
        content_lines.push(format!("## Talk {i}\n"));
        content_lines.extend(talk::render_talk_content(talk_info, scope)?);
        content_lines.push(String::new());
    }
    let versions = repo.first_seen.resolve_ints(Domain::Talk, talk_ids)?;
    Ok(Some(RenderedItem::new(
        "agd_anecdote",
        title,
        anecdote_id,
        filename,
        versions,
        util::py_rstrip(&content_lines.join("\n")).to_string(),
    )))
}

// --- blossoms ---

/// (refresh, talk ids) pairs for the NPC-intel blossom talk pools.
fn intel_rows(repo: &Repo) -> Result<Vec<(&Value, Vec<i64>)>> {
    let mut rows = Vec::new();
    for row in &repo.blossom_talk {
        let refresh_id = row.i("refreshId")?;
        let refresh = repo
            .blossom_refresh
            .get(&refresh_id)
            .ok_or_else(|| anyhow!("unknown blossom refresh {refresh_id}"))?;
        if refresh.s("clientShowType")? == "BLOSSOM_SHOWTYPE_NPCTALK" {
            rows.push((refresh, int_array(row.f("talkId")?)?));
        }
    }
    Ok(rows)
}

pub fn blossom_city_ids(repo: &Repo) -> Result<Vec<i64>> {
    let mut ids: Vec<i64> = intel_rows(repo)?
        .iter()
        .map(|(refresh, _)| refresh.i("cityId"))
        .collect::<Result<FxHashSet<i64>>>()?
        .into_iter()
        .collect();
    ids.sort();
    Ok(ids)
}

pub fn process_blossom_city(
    repo: &Repo,
    scope: &Scope,
    city_id: i64,
) -> Result<Option<RenderedItem>> {
    let mut names: FxHashSet<String> = FxHashSet::default();
    let mut section_order: IndexMap<String, i64> = IndexMap::new();
    let mut section_talk_ids: IndexMap<String, FxHashSet<i64>> = IndexMap::new();
    for (refresh, row_talk_ids) in intel_rows(repo)? {
        if refresh.i("cityId")? != city_id {
            continue;
        }
        names.insert(repo.tm.get_required(refresh.i("nameTextMapHash")?, scope)?);
        let desc = repo.tm.get_required(refresh.i("descTextMapHash")?, scope)?;
        let refresh_id = refresh.i("id")?;
        let current = section_order.get(&desc).copied().unwrap_or(refresh_id);
        section_order.insert(desc.clone(), current.min(refresh_id));
        section_talk_ids
            .entry(desc)
            .or_default()
            .extend(row_talk_ids);
    }
    if names.len() != 1 {
        bail!("expected exactly one blossom name, got {}", names.len());
    }
    let name = names.into_iter().next().unwrap();
    let city_name = repo.tm.get_required(
        repo.city_config
            .get(&city_id)
            .ok_or_else(|| anyhow!("unknown city {city_id}"))?
            .i("cityNameTextMapHash")?,
        scope,
    )?;

    struct Section {
        description: String,
        talks: Vec<TalkInfo>,
    }
    let mut sections: Vec<Section> = Vec::new();
    let mut talk_ids: Vec<i64> = Vec::new();
    // sorted(section_order, key=value) — stable by insertion order on ties.
    let mut descs: Vec<(&String, i64)> = section_order.iter().map(|(d, v)| (d, *v)).collect();
    descs.sort_by_key(|(_, v)| *v);
    for (desc, _) in descs {
        let mut talks: Vec<TalkInfo> = Vec::new();
        let mut seen_contents: FxHashSet<Vec<(Option<String>, String)>> = FxHashSet::default();
        let mut ids: Vec<i64> = section_talk_ids
            .get(desc)
            .ok_or_else(|| anyhow!("blossom section {desc:?} missing talk ids"))?
            .iter()
            .copied()
            .collect();
        ids.sort();
        for talk_id in ids {
            let talk_info = match talk::get_talk_info_by_id(repo, scope, talk_id) {
                Ok(info) => info,
                Err(e) if e.is::<TalkNotFound>() => {
                    scope.record_issue(IssueType::MissingTalk, talk_id.to_string());
                    continue;
                }
                Err(e) => return Err(e),
            };
            let content: Vec<(Option<String>, String)> = talk_info
                .text
                .iter()
                .filter(|t| !t.skip)
                .map(|t| (t.role.clone(), t.message.clone()))
                .collect();
            if !content.is_empty() && !seen_contents.contains(&content) {
                seen_contents.insert(content);
                talks.push(talk_info);
                talk_ids.push(talk_id);
            }
        }
        if !talks.is_empty() {
            sections.push(Section {
                description: desc.clone(),
                talks,
            });
        }
    }
    if sections.is_empty() {
        return Ok(None);
    }

    let title = format!("{name} - {city_name}");
    let filename = format!("{city_id}_{}.txt", util::make_safe_filename_part(&title));
    let mut content_lines = vec![format!("# {title}\n")];
    let mut talk_index = 0;
    for section in &sections {
        content_lines.push(format!("## {}\n", section.description));
        for talk_info in &section.talks {
            content_lines.push(format!("### Talk {talk_index}\n"));
            content_lines.extend(talk::render_talk_content(talk_info, scope)?);
            content_lines.push(String::new());
            talk_index += 1;
        }
    }
    let versions = repo.first_seen.resolve_ints(Domain::Talk, talk_ids)?;
    Ok(Some(RenderedItem::new(
        "agd_blossom",
        title,
        city_id,
        filename,
        versions,
        util::py_rstrip(&content_lines.join("\n")).to_string(),
    )))
}

// --- activities ---

pub fn loose_talk_ids_by_activity(
    repo: &Repo,
    used_talk_ids: &FxHashSet<i64>,
) -> Result<FxHashMap<i64, Vec<i64>>> {
    let mut grouped: FxHashMap<i64, Vec<i64>> = FxHashMap::default();
    for entry in &repo.talk_excel {
        if entry.s("loadType")? != "TALK_ACTIVITY" {
            continue;
        }
        let talk_id = entry.i("id")?;
        if repo.talk_ids_all.contains(&talk_id) && !used_talk_ids.contains(&talk_id) {
            grouped
                .entry(entry.i("questId")?)
                .or_default()
                .push(talk_id);
        }
    }
    for ids in grouped.values_mut() {
        ids.sort();
    }
    Ok(grouped)
}

pub fn process_activity(
    repo: &Repo,
    scope: &Scope,
    used_talk_ids: &FxHashSet<i64>,
    activity_id: i64,
) -> Result<Option<RenderedItem>> {
    let grouped = loose_talk_ids_by_activity(repo, used_talk_ids)?;
    let ids = grouped
        .get(&activity_id)
        .ok_or_else(|| anyhow!("activity {activity_id} has no loose talks"))?;
    let mut talks: Vec<TalkInfo> = Vec::new();
    let mut talk_ids: Vec<i64> = Vec::new();
    for &talk_id in ids {
        let talk_info = talk::get_talk_info_by_id(repo, scope, talk_id)?;
        if talk_info.has_non_skip_text() {
            talks.push(talk_info);
            talk_ids.push(talk_id);
        }
    }
    if talks.is_empty() {
        return Ok(None);
    }
    let title = repo
        .activity_id_to_name
        .get(&activity_id)
        .ok_or_else(|| anyhow!("activity {activity_id} has no name"))?
        .clone();
    let filename = format!(
        "{activity_id}_{}.txt",
        util::make_safe_filename_part(&title)
    );
    let mut content_lines = vec![format!("# {title}\n")];
    for (i, talk_info) in talks.iter().enumerate() {
        content_lines.push(format!("## Talk {i}\n"));
        content_lines.extend(talk::render_talk_content(talk_info, scope)?);
        content_lines.push(String::new());
    }
    let versions = repo.first_seen.resolve_ints(Domain::Talk, talk_ids)?;
    Ok(Some(RenderedItem::new(
        "agd_activity",
        title,
        activity_id,
        filename,
        versions,
        util::py_rstrip(&content_lines.join("\n")).to_string(),
    )))
}
