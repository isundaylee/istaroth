//! Port of renderables/character.py: character stories (with constellations)
//! and voicelines.

use crate::firstseen::Domain;
use crate::issues::{IssueType, Scope};
use crate::lang::Language;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::{ValueExt, int_array};
use anyhow::{Result, anyhow, bail};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;

/// (CHS, non-CHS) per-pass error limits (see e.g. `artifact::ERROR_LIMITS`).
pub const STORY_ERROR_LIMITS: (usize, usize) = (0, 0);
pub const VOICELINE_ERROR_LIMITS: (usize, usize) = (0, 0);

const ELEMENT_NAMES: [(&str, &str, &str); 7] = [
    ("Fire", "火", "Pyro"),
    ("Water", "水", "Hydro"),
    ("Wind", "风", "Anemo"),
    ("Rock", "岩", "Geo"),
    ("Electric", "雷", "Electro"),
    ("Grass", "草", "Dendro"),
    ("Ice", "冰", "Cryo"),
];

fn element_name(cost_elem_type: &str, language: Language) -> Result<&'static str> {
    ELEMENT_NAMES
        .iter()
        .find(|(k, _, _)| *k == cost_elem_type)
        .map(|(_, chs, eng)| match language {
            Language::Chs => *chs,
            Language::Eng => *eng,
        })
        .ok_or_else(|| anyhow!("unknown element {cost_elem_type}"))
}

struct Constellation {
    name: String,
    description: String,
    element: Option<&'static str>,
}

/// Resolve the 6 constellations for a single skill depot, in talents-array
/// order. Strict: every depot that owns constellations must have exactly 6
/// talents that all resolve to a name and description, else error.
fn resolve_constellations(
    repo: &Repo,
    scope: &Scope,
    depot: &Value,
    element: Option<&'static str>,
) -> Result<Vec<Constellation>> {
    let talent_ids: Vec<i64> = int_array(depot.f("talents")?)?
        .into_iter()
        .filter(|&t| t != 0)
        .collect();
    if talent_ids.len() != 6 {
        bail!(
            "Expected 6 constellation talents in depot {}, got {}",
            depot.i("id")?,
            talent_ids.len()
        );
    }
    let mut constellations = Vec::new();
    for talent_id in talent_ids {
        let talent = repo
            .excel
            .talent
            .get(&talent_id)
            .ok_or_else(|| anyhow!("Unknown talent {talent_id}"))?;
        constellations.push(Constellation {
            name: repo.tm.get_required(talent.i("nameTextMapHash")?, scope)?,
            description: repo.tm.get_required(talent.i("descTextMapHash")?, scope)?,
            element,
        });
    }
    Ok(constellations)
}

/// Resolve a character's constellations.
///
/// Regular characters carry all six constellations on their primary
/// `skillDepotId` and render without an element. Only the Travelers populate
/// `candSkillDepotIds`; their per-element sets live there (skipping empty
/// placeholder depots) and are tagged with each depot's element.
fn get_constellations(repo: &Repo, scope: &Scope, avatar: &Value) -> Result<Vec<Constellation>> {
    let cand = avatar.f("candSkillDepotIds")?;
    let cand_ids = int_array(cand)?;
    let per_element = !cand_ids.is_empty();
    let depot_ids: Vec<i64> = if per_element {
        cand_ids
    } else {
        vec![avatar.i("skillDepotId")?]
    };
    let mut constellations = Vec::new();
    for depot_id in depot_ids {
        let depot = repo
            .excel
            .skill_depot
            .get(&depot_id)
            .ok_or_else(|| anyhow!("unknown depot {depot_id}"))?;
        if !int_array(depot.f("talents")?)?.iter().any(|&t| t != 0) {
            continue;
        }
        let element = if per_element {
            let energy_skill = depot.i("energySkill")?;
            let skill = repo
                .excel
                .skill
                .get(&energy_skill)
                .ok_or_else(|| anyhow!("Unknown energy skill {energy_skill} for {depot_id}"))?;
            Some(element_name(skill.s("costElemType")?, repo.language)?)
        } else {
            None
        };
        constellations.extend(resolve_constellations(repo, scope, depot, element)?);
    }
    Ok(constellations)
}

/// CharacterStories pass discovery: avatar ids with fetter stories.
pub fn discover_stories(repo: &Repo) -> Result<Vec<i64>> {
    let mut ids: FxHashSet<i64> = FxHashSet::default();
    for story in &repo.excel.fetter_story {
        if let Some(avatar_id) = story.get_i("avatarId")
            && avatar_id != 0
        {
            ids.insert(avatar_id);
        }
    }
    let mut v: Vec<i64> = ids.into_iter().collect();
    v.sort();
    Ok(v)
}

/// CharacterStories.
pub fn process_story(repo: &Repo, scope: &Scope, avatar_id: i64) -> Result<Option<RenderedItem>> {
    let avatar = repo
        .excel
        .avatar
        .get(&avatar_id)
        .ok_or_else(|| anyhow!("Unknown character for avatar ID {avatar_id}"))?;
    let character_name = repo
        .tm
        .get_optional(avatar.i("nameTextMapHash")?, scope)?
        .ok_or_else(|| anyhow!("Unknown character for avatar ID {avatar_id}"))?;

    let constellations = get_constellations(repo, scope, avatar)?;

    struct Story {
        title: String,
        content: String,
    }
    let mut stories = Vec::new();
    for story in &repo.excel.fetter_story {
        if story.i("avatarId")? != avatar_id {
            continue;
        }
        // A title hash of 0 and an absent field both mean "no title".
        let title_hash = story.get_i("storyTitleTextMapHash").filter(|&h| h != 0);
        let title = match title_hash {
            Some(h) => repo.tm.get_optional(h, scope)?,
            None => None,
        };
        let Some(title) = title else {
            bail!("Missing story title for avatar ID {avatar_id}");
        };
        // The recorded issue detail is the raw field's string form ("None"
        // when the field is absent).
        let context_hash_raw = story.get_i("storyContextTextMapHash");
        let content = match context_hash_raw.filter(|&h| h != 0) {
            Some(h) => repo.tm.get_optional(h, scope)?,
            None => None,
        };
        let content = match content {
            Some(content) => content,
            None => {
                scope.record_issue(
                    IssueType::MissingStoryContent,
                    context_hash_raw.map_or_else(|| "None".to_string(), |h| h.to_string()),
                );
                "Story content not found".to_string()
            }
        };
        stories.push(Story { title, content });
    }

    let safe_name = util::make_safe_filename_part(&character_name);
    let mut content_lines = vec![
        format!("# {character_name} - Character Stories\n"),
        format!("*{} stories for this character*\n", stories.len()),
    ];
    for (i, story) in stories.iter().enumerate() {
        content_lines.push(format!("## {}. {}\n", i + 1, story.title));
        content_lines.push(story.content.clone());
        content_lines.push(String::new());
    }
    // Constellations as a flat list. No Cn prefix: the source data does not
    // give a reliable constellation index (the talents array order and
    // openConfig disagree), so we list them in talents-array order without
    // asserting a number. The Travelers' per-element sets are grouped under
    // ### element subsections.
    if !constellations.is_empty() {
        content_lines.push("## Constellations\n".to_string());
        // The outer Option is a sentinel distinct from any real element value
        // (including "no element"), so the first constellation always starts
        // a group.
        let mut current_element: Option<Option<&'static str>> = None;
        let mut first_group = true;
        for constellation in &constellations {
            if current_element != Some(constellation.element) {
                current_element = Some(constellation.element);
                if let Some(element) = constellation.element {
                    if !first_group {
                        content_lines.push(String::new());
                    }
                    content_lines.push(format!("### {element}\n"));
                }
                first_group = false;
            }
            let description = constellation
                .description
                .split_whitespace()
                .collect::<Vec<_>>()
                .join(" ");
            content_lines.push(format!("{}: {description}", constellation.name));
        }
        content_lines.push(String::new());
    }

    let versions = repo.first_seen.resolve_int(Domain::Avatar, avatar_id)?;
    Ok(Some(RenderedItem::new(
        "agd_character_story",
        character_name,
        avatar_id,
        format!("{avatar_id}_{safe_name}.txt"),
        versions,
        content_lines.join("\n"),
    )))
}

/// Voicelines pass discovery: avatar ids with fetter voicelines.
pub fn discover_voicelines(repo: &Repo) -> Result<Vec<i64>> {
    let mut ids: FxHashSet<i64> = FxHashSet::default();
    for fetter in &repo.excel.fetters {
        ids.insert(fetter.i("avatarId")?);
    }
    let mut v: Vec<i64> = ids.into_iter().collect();
    v.sort();
    Ok(v)
}

/// Voicelines.
pub fn process_voiceline(
    repo: &Repo,
    scope: &Scope,
    avatar_id: i64,
) -> Result<Option<RenderedItem>> {
    let character_name = match repo.excel.avatar.get(&avatar_id) {
        Some(avatar) => repo.tm.get_optional(avatar.i("nameTextMapHash")?, scope)?,
        None => None,
    }
    .ok_or_else(|| anyhow!("Unknown character for avatar ID {avatar_id}"))?;

    // Voicelines in file order; a repeated title keeps its first position but
    // the latest content.
    let mut voicelines: Vec<(String, String)> = Vec::new();
    let mut title_index: FxHashMap<String, usize> = FxHashMap::default();
    for fetter in &repo.excel.fetters {
        if fetter.i("avatarId")? != avatar_id {
            continue;
        }
        let title = repo
            .tm
            .get_required(fetter.i("voiceTitleTextMapHash")?, scope)?;
        let content = repo
            .tm
            .get_or(fetter.i("voiceFileTextTextMapHash")?, "", scope)?;
        if !content.is_empty() {
            match title_index.get(&title) {
                Some(&i) => voicelines[i].1 = content,
                None => {
                    title_index.insert(title.clone(), voicelines.len());
                    voicelines.push((title, content));
                }
            }
        }
    }
    if voicelines.is_empty() {
        return Ok(None);
    }

    let safe_name = util::make_safe_filename_part(&character_name);
    let mut content_lines = vec![format!("# {character_name} Voicelines\n")];
    for (title, content) in &voicelines {
        content_lines.push(format!("## {title}"));
        content_lines.push(content.clone());
        content_lines.push(String::new());
    }
    let content = content_lines.join("\n").trim_end().to_string();
    let versions = repo.first_seen.resolve_int(Domain::Avatar, avatar_id)?;
    Ok(Some(RenderedItem::new(
        "agd_voiceline",
        character_name,
        avatar_id,
        format!("{avatar_id}_{safe_name}.txt"),
        versions,
        content,
    )))
}
