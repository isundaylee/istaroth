//! Port of renderables/hangout.py (including the coop-step resolution and
//! choice/fork rendering).

use crate::coop::{ChoiceBranch, PlayStep};
use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::lang::Language;
use crate::renderables::talk::{self, TalkInfo};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::{ValueExt, int_array, truthy};
use anyhow::{Result, anyhow, bail};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;

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
    // A content hash of 0 yields no prompt (falsy, not just absent).
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
    // enableCondGrp is parsed for strict-shape validation but never rendered.
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

/// Assemble a hangout quest's play-ordered Coop story dialogue, or None if
/// empty. `quest_id` is always a hangout quest (the Hangouts pass discovers
/// them from `hangout_quest_to_stories`), so its stories and main-quest entry
/// are indexed strictly.
pub fn get_hangout_info(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<HangoutInfo>> {
    let stories = repo
        .hangout_quest_to_stories
        .get(&quest_id)
        .ok_or_else(|| anyhow!("hangout quest {quest_id} has no coop stories"))?;
    let main_quest = repo
        .excel
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

/// Depth-first numbering of all choice steps into `mapping` (choice id ->
/// fork number).
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

/// Render a `### Choice N:` section and return (lines, nested_sections).
///
/// `nested_sections` contains fully-rendered `### Choice N:` sections for
/// choices nested inside branches (to be appended after the current level).
/// The nested sections are rendered as separate top-level `### Choice` blocks
/// that the `*→ Next: Choice N*` markers at the end of each branch reference.
fn render_choice_section(
    step: &CoopStep,
    fork_num: i64,
    fork_map: &FxHashMap<usize, i64>,
    language: Language,
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
                    lines.extend(talk::render_talk_content(talk_info, language, scope)?);
                }
                CoopStep::Choice { id, .. } => {
                    let nested_fork_num = *fork_map
                        .get(id)
                        .ok_or_else(|| anyhow!("choice {id} missing fork number"))?;
                    next_marker = format!("*→ Next: Choice {nested_fork_num}*");
                    let (section_lines, new_nested) =
                        render_choice_section(step, nested_fork_num, fork_map, language, scope)?;
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

/// Render a hangout story's play-ordered steps with explicit branch routing.
/// `fork_map` is the output of `assign_fork_numbers`.
fn render_coop_steps(
    steps: &[CoopStep],
    fork_map: &FxHashMap<usize, i64>,
    language: Language,
    scope: &Scope,
) -> Result<Vec<String>> {
    let mut lines: Vec<String> = Vec::new();
    let mut nested_sections: Vec<Vec<String>> = Vec::new();
    for step in steps {
        match step {
            CoopStep::Talk(talk_info) => {
                let talk_lines = talk::render_talk_content(talk_info, language, scope)?;
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
                    render_choice_section(step, fork_num, fork_map, language, scope)?;
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
        content_lines.extend(render_coop_steps(story, &fork_map, repo.language, scope)?);
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

/// Hangouts pass discovery: sorted hangout quest ids with coop stories.
pub fn discover(repo: &Repo) -> Result<Vec<i64>> {
    let mut ids: Vec<i64> = repo.hangout_quest_to_stories.keys().copied().collect();
    ids.sort();
    Ok(ids)
}

/// Hangouts pass process.
pub fn process(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<RenderedItem>> {
    let Some(info) = get_hangout_info(repo, scope, quest_id)? else {
        return Ok(None);
    };
    Ok(Some(render_hangout(repo, scope, &info)?))
}
