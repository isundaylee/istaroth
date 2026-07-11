//! Renderables without dialogue graphs: readables/books/wings/costumes,
//! weapons, character stories, voicelines, subtitles, materials, achievements,
//! artifacts, creatures.

use crate::firstseen::Domain;
use crate::meta::RenderedItem;
use crate::repo::{IssueType, Repo, Scope};
use crate::util;
use crate::vh::{ValueExt, int_array};
use anyhow::{Context, Result, anyhow, bail};
use indexmap::IndexMap;
use regex::Regex;
use serde_json::Value;
use std::sync::LazyLock;

pub struct ReadableMetadata {
    pub localization_id: i64,
    pub title: String,
}

/// Port of readable.get_readable_metadata.
pub fn get_readable_metadata(
    repo: &Repo,
    scope: &Scope,
    readable_filename: &str,
) -> Result<ReadableMetadata> {
    let readable_stem = util::path_stem(readable_filename);
    let readable_id = readable_stem
        .strip_suffix(&format!("_{}", repo.language.short()))
        .unwrap_or(readable_stem);
    let localization_id = *repo
        .readable_stem_to_loc_id
        .get(readable_stem)
        .ok_or_else(|| anyhow!("Localization ID not found for readable: {readable_id}"))?;
    let title = match repo.loc_id_to_title_hash.get(&localization_id) {
        None => None,
        Some(&h) => repo.tm.get_optional(h, scope)?,
    };
    let title = match title {
        Some(title) => title,
        None => {
            scope.record_issue(IssueType::MissingReadableTitle, readable_id.to_string());
            "Unknown Title".to_string()
        }
    };
    Ok(ReadableMetadata {
        localization_id,
        title,
    })
}

/// Port of readable.load_readable: cleaned content + metadata, or None to skip.
pub fn load_readable(
    repo: &Repo,
    scope: &Scope,
    readable_filename: &str,
) -> Result<Option<(String, ReadableMetadata)>> {
    let content = repo
        .readable_content(readable_filename, scope)
        .ok_or_else(|| anyhow!("Readable not found: {readable_filename}"))?;
    let content = repo.tm.clean_text(content)?;
    if util::should_skip_readable_content(&content) {
        return Ok(None);
    }
    let metadata = get_readable_metadata(repo, scope, readable_filename)?;
    if util::should_skip_text(&metadata.title) {
        return Ok(None);
    }
    Ok(Some((content, metadata)))
}

/// Port of readable.render_readable_like (readable/wings/costume + standalone book).
pub fn render_readable_like(
    repo: &Repo,
    content: &str,
    metadata: &ReadableMetadata,
    readable_filename: &str,
    category: &'static str,
) -> Result<RenderedItem> {
    let safe_title = util::make_safe_filename_part(&metadata.title);
    let versions = repo
        .first_seen
        .resolve_stem(Domain::Readable, readable_filename)?;
    Ok(RenderedItem::new(
        category,
        metadata.title.clone(),
        metadata.localization_id,
        format!("{}_{safe_title}.txt", metadata.localization_id),
        versions,
        format!("# {}\n\n{content}", metadata.title),
    ))
}

/// Books: one series document (suit) or a standalone book file.
pub fn process_book_series(
    repo: &Repo,
    scope: &Scope,
    suit_id: i64,
) -> Result<Option<RenderedItem>> {
    let filenames = repo
        .book_series
        .get(&suit_id)
        .ok_or_else(|| anyhow!("Book suit {suit_id} is not a multi-volume series"))?;
    let suit = repo
        .book_suit
        .get(&suit_id)
        .ok_or_else(|| anyhow!("unknown book suit {suit_id}"))?;
    let series_name = repo
        .tm
        .get_optional(suit.i("suitNameTextMapHash")?, scope)?
        .ok_or_else(|| anyhow!("Missing series name for book suit {suit_id}"))?;

    struct Volume {
        title: String,
        content: String,
        filename: String,
    }
    let mut volumes: Vec<Volume> = Vec::new();
    for filename in filenames {
        if let Some((content, metadata)) = load_readable(repo, scope, filename)? {
            volumes.push(Volume {
                title: metadata.title,
                content,
                filename: filename.clone(),
            });
        }
    }
    if volumes.is_empty() {
        return Ok(None);
    }

    let safe_name = util::make_safe_filename_part(&series_name);
    let total = volumes.len();
    let mut content_parts = vec![format!("# {series_name}")];
    for (index, volume) in volumes.iter().enumerate() {
        let annotation = format!("*{series_name}·第 {} 卷，共 {total} 卷*", index + 1);
        content_parts.push(format!(
            "## {}\n\n{annotation}\n\n{}",
            volume.title, volume.content
        ));
    }
    let keys: Vec<crate::firstseen::SourceKey> = volumes
        .iter()
        .map(|v| {
            crate::firstseen::SourceKey::Str(
                util::strip_language_suffix(util::path_stem(&v.filename)).to_string(),
            )
        })
        .collect();
    let versions = repo
        .first_seen
        .resolve(keys.iter().map(|k| (Domain::Readable, k)))?;
    Ok(Some(RenderedItem::new(
        "agd_book",
        series_name,
        suit_id,
        format!("{suit_id}_{safe_name}.txt"),
        versions,
        content_parts.join("\n\n"),
    )))
}

/// Weapons.
pub fn process_weapon(
    repo: &Repo,
    scope: &Scope,
    weapon_id_str: &str,
) -> Result<Option<RenderedItem>> {
    let weapon_id = util::py_int(weapon_id_str)?;
    let weapon = repo
        .weapon_excel
        .get(&weapon_id)
        .ok_or_else(|| anyhow!("Weapon configuration not found for weapon ID: {weapon_id_str}"))?;
    let story_id = weapon.i("storyId")?;
    if story_id == 0 {
        return Ok(None);
    }
    let Some(doc_item) = repo.document.get(&story_id) else {
        return Ok(None);
    };
    // dict.fromkeys over questContentLocalizedId + questIDList + CUSTOM_addlLocalID.
    let mut ordered: IndexMap<i64, ()> = IndexMap::new();
    for id in int_array(doc_item.f("questContentLocalizedId")?)? {
        ordered.entry(id).or_insert(());
    }
    for id in int_array(doc_item.f("questIDList")?)? {
        ordered.entry(id).or_insert(());
    }
    if let Some(addl) = doc_item.get("CUSTOM_addlLocalID") {
        for id in int_array(addl).context("CUSTOM_addlLocalID")? {
            ordered.entry(id).or_insert(());
        }
    }
    let mut story_pages: Vec<String> = Vec::new();
    for loc_id in ordered.keys() {
        if let Some(filename) = repo.loc_id_to_readable_filename.get(loc_id)
            && let Some(content) = repo.readable_content(filename, scope)
            && !content.is_empty()
        {
            story_pages.push(content.clone());
        }
    }
    if story_pages.is_empty() {
        return Ok(None);
    }

    let name = repo.tm.get_required(weapon.i("nameTextMapHash")?, scope)?;
    let description = repo.tm.get_or(weapon.i("descTextMapHash")?, "", scope)?;

    let safe_name = util::make_safe_filename_part(&name);
    let mut content_lines = vec![format!("# {name}\n")];
    if !description.is_empty() {
        content_lines.push(format!("{description}\n"));
    }
    content_lines.push(story_pages.join("\n\n---\n\n"));
    let versions = repo.first_seen.resolve_int(Domain::Weapon, weapon_id)?;
    Ok(Some(RenderedItem::new(
        "agd_weapon",
        name,
        weapon_id,
        format!("{weapon_id_str}_{safe_name}.txt"),
        versions,
        content_lines.join("\n"),
    )))
}

const ELEMENT_NAMES: [(&str, &str); 7] = [
    ("Fire", "火"),
    ("Water", "水"),
    ("Wind", "风"),
    ("Rock", "岩"),
    ("Electric", "雷"),
    ("Grass", "草"),
    ("Ice", "冰"),
];

fn element_name(cost_elem_type: &str) -> Result<&'static str> {
    ELEMENT_NAMES
        .iter()
        .find(|(k, _)| *k == cost_elem_type)
        .map(|(_, v)| *v)
        .ok_or_else(|| anyhow!("unknown element {cost_elem_type}"))
}

struct Constellation {
    name: String,
    description: String,
    element: Option<&'static str>,
}

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
            .skill_depot
            .get(&depot_id)
            .ok_or_else(|| anyhow!("unknown depot {depot_id}"))?;
        if !int_array(depot.f("talents")?)?.iter().any(|&t| t != 0) {
            continue;
        }
        let element = if per_element {
            let energy_skill = depot.i("energySkill")?;
            let skill = repo
                .skill
                .get(&energy_skill)
                .ok_or_else(|| anyhow!("Unknown energy skill {energy_skill} for {depot_id}"))?;
            Some(element_name(skill.s("costElemType")?)?)
        } else {
            None
        };
        constellations.extend(resolve_constellations(repo, scope, depot, element)?);
    }
    Ok(constellations)
}

/// CharacterStories.
pub fn process_character_story(
    repo: &Repo,
    scope: &Scope,
    avatar_id: i64,
) -> Result<Option<RenderedItem>> {
    let mut matched_avatar = None;
    for avatar in &repo.avatar_excel {
        if avatar.i("id")? == avatar_id {
            matched_avatar = Some(avatar);
            break;
        }
    }
    let character_name = match matched_avatar {
        None => None,
        Some(avatar) => repo.tm.get_optional(avatar.i("nameTextMapHash")?, scope)?,
    };
    let (Some(avatar), Some(character_name)) = (matched_avatar, character_name) else {
        bail!("Unknown character for avatar ID {avatar_id}");
    };

    let constellations = get_constellations(repo, scope, avatar)?;

    struct Story {
        title: String,
        content: String,
    }
    let mut stories = Vec::new();
    for story in &repo.fetter_story {
        if story.i("avatarId")? != avatar_id {
            continue;
        }
        // Python: .get(...) then `if title_hash else None` (0/absent both falsy).
        let title_hash = story.get_i("storyTitleTextMapHash").filter(|&h| h != 0);
        let title = match title_hash {
            Some(h) => repo.tm.get_optional(h, scope)?,
            None => None,
        };
        let Some(title) = title else {
            bail!("Missing story title for avatar ID {avatar_id}");
        };
        // Python's issue detail is str() of the raw field: "None" when absent.
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
    if !constellations.is_empty() {
        content_lines.push("## Constellations\n".to_string());
        // Python starts current_element at a unique sentinel object.
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

/// Voicelines.
pub fn process_voiceline(
    repo: &Repo,
    scope: &Scope,
    avatar_id: i64,
) -> Result<Option<RenderedItem>> {
    let mut character_name = None;
    for avatar in &repo.avatar_excel {
        if avatar.i("id")? == avatar_id {
            character_name = repo.tm.get_optional(avatar.i("nameTextMapHash")?, scope)?;
            break;
        }
    }
    let Some(character_name) = character_name else {
        bail!("Unknown character for avatar ID {avatar_id}");
    };

    let mut voicelines: IndexMap<String, String> = IndexMap::new();
    for fetter in &repo.fetters {
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
            voicelines.insert(title, content);
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
    let content = util::py_rstrip(&content_lines.join("\n")).to_string();
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

static QUEST_ID_TOKEN: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\d{4,9}").unwrap());

fn main_quest_title(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<String>> {
    let Some(main_quest) = repo.main_quest.get(&quest_id) else {
        return Ok(None);
    };
    let title_hash = main_quest.i("titleTextMapHash")?;
    let chs_title = repo.tm.get_optional(title_hash, scope)?;
    if let Some(chs) = &chs_title
        && util::should_skip_text(chs)
    {
        return Ok(None);
    }
    Ok(chs_title)
}

fn resolve_quest_title(repo: &Repo, scope: &Scope, number: i64) -> Result<Option<String>> {
    let candidates = [
        repo.sub_quest_to_main.get(&number).copied(),
        repo.talk_to_quest.get(&number).copied(),
        Some(number),
        repo.sub_quest_to_main.get(&(number / 100)).copied(),
        repo.talk_to_quest.get(&(number / 100)).copied(),
        Some(number / 100),
        Some(number / 10000),
    ];
    for quest_id in candidates.into_iter().flatten() {
        if let Some(title) = main_quest_title(repo, scope, quest_id)?
            && !title.is_empty()
        {
            return Ok(Some(title));
        }
    }
    Ok(None)
}

/// Subtitles: parse, filter, title, render.
pub fn process_subtitle(
    repo: &Repo,
    scope: &Scope,
    subtitle_path: &str,
) -> Result<Option<RenderedItem>> {
    let content = std::fs::read_to_string(repo.agd_path.join(subtitle_path))?;
    let mut text_lines: Vec<String> = Vec::new();
    for line in util::py_strip(&content).split('\n') {
        let line = util::py_strip(line);
        if !line.is_empty() && !util::py_isdigit(line) && !line.contains("-->") {
            text_lines.push(crate::cleanup::clean_text_markers(line)?);
        }
    }
    if !text_lines
        .iter()
        .any(|l| !l.trim_matches(|c| c == ' ' || c == '.').is_empty())
    {
        return Ok(None);
    }

    // Title.
    let stem = util::path_stem(subtitle_path);
    let display_stem = stem
        .strip_suffix(&format!("_{}", repo.language.short()))
        .unwrap_or(stem);
    let mut numbers: Vec<i64> = repo
        .subtitle_stem_to_cutscenes
        .get(stem)
        .cloned()
        .unwrap_or_default();
    let mut tokens: Vec<&str> = QUEST_ID_TOKEN
        .find_iter(display_stem)
        .map(|m| m.as_str())
        .collect();
    tokens.sort_by_key(|t| std::cmp::Reverse(t.len()));
    numbers.extend(tokens.iter().map(|t| t.parse::<i64>().unwrap()));
    let mut title = display_stem.to_string();
    for number in numbers {
        if let Some(t) = resolve_quest_title(repo, scope, number)? {
            title = format!("{t} ({display_stem})");
            break;
        }
    }

    let subtitle_id = util::sha256_id(subtitle_path);
    let safe_name = util::make_safe_filename_part(stem);
    let mut content_lines = vec![format!("# {title}\n")];
    content_lines.extend(text_lines);
    let versions = repo
        .first_seen
        .resolve_stem(Domain::Subtitle, subtitle_path)?;
    Ok(Some(RenderedItem::new(
        "agd_subtitle",
        title,
        subtitle_id,
        format!("{subtitle_id}_{safe_name}.txt"),
        versions,
        content_lines.join("\n"),
    )))
}

/// MaterialTypes: all same-type materials into one file.
pub fn process_material_type(
    repo: &Repo,
    scope: &Scope,
    material_type: &str,
) -> Result<Option<RenderedItem>> {
    struct MaterialInfo {
        material_id: i64,
        name: String,
        description: String,
    }
    let mut materials: Vec<MaterialInfo> = Vec::new();
    for material in repo.material.values() {
        if material.s("materialType")? != material_type {
            continue;
        }
        let material_id = material.i("id")?;
        let name_hash = material.i("nameTextMapHash")?;
        let name = match repo.tm.get_optional(name_hash, scope)? {
            Some(name) => name,
            None => {
                scope.record_issue(IssueType::MissingMaterialName, name_hash.to_string());
                "Unknown Material".to_string()
            }
        };
        let desc_hash = material.i("descTextMapHash")?;
        let description = match repo.tm.get_optional(desc_hash, scope)? {
            Some(desc) => desc,
            None => {
                scope.record_issue(IssueType::MissingMaterialDesc, desc_hash.to_string());
                "No description available".to_string()
            }
        };
        if util::should_skip_text(&name) || util::should_skip_text(&description) {
            continue;
        }
        materials.push(MaterialInfo {
            material_id,
            name,
            description,
        });
    }
    if materials.is_empty() {
        return Ok(None);
    }

    let material_type_id = util::sha256_id(material_type);
    let safe_type = util::make_safe_filename_part(material_type);
    let material_type_name = util::py_title_case(
        &material_type
            .strip_prefix("MATERIAL_")
            .unwrap_or(material_type)
            .replace('_', " "),
    );
    let mut content_lines = vec![format!("# Materials: {material_type_name}\n")];
    materials.sort_by_key(|m| m.material_id);
    for m in &materials {
        content_lines.push(format!("## {}", m.name));
        content_lines.push(String::new());
        content_lines.push(m.description.clone());
        content_lines.push(String::new());
    }
    let content = util::py_rstrip(&content_lines.join("\n")).to_string();
    let versions = repo
        .first_seen
        .resolve_ints(Domain::Material, materials.iter().map(|m| m.material_id))?;
    Ok(Some(RenderedItem::new(
        "agd_material_type",
        material_type_name,
        material_type_id,
        format!("{material_type_id}_{safe_type}.txt"),
        versions,
        content,
    )))
}

/// Achievements: one section per file.
pub fn process_achievement_section(
    repo: &Repo,
    scope: &Scope,
    section_id: i64,
) -> Result<Option<RenderedItem>> {
    let (section, achievement_configs) = repo
        .achievement_sections
        .get(&section_id)
        .ok_or_else(|| anyhow!("Achievement section not found for ID {section_id}"))?;
    let section_name = repo.tm.get_required(section.i("nameTextMapHash")?, scope)?;

    struct AchievementInfo {
        id: i64,
        name: String,
        description: String,
    }
    let achievements: Vec<AchievementInfo> = achievement_configs
        .iter()
        .map(|a| {
            Ok(AchievementInfo {
                id: a.i("id")?,
                name: repo.tm.get_required(a.i("titleTextMapHash")?, scope)?,
                description: repo.tm.get_required(a.i("descTextMapHash")?, scope)?,
            })
        })
        .collect::<Result<_>>()?;

    let filename = format!(
        "{section_id}_{}.txt",
        util::make_safe_filename_part(&section_name)
    );
    let mut content_lines = vec![format!("# {section_name}"), String::new()];
    for a in &achievements {
        content_lines.extend([
            format!("## {}", a.name),
            String::new(),
            a.description.clone(),
            String::new(),
        ]);
    }
    let versions = repo
        .first_seen
        .resolve_ints(Domain::Achievement, achievements.iter().map(|a| a.id))?;
    Ok(Some(RenderedItem::new(
        "agd_achievement",
        section_name,
        section_id,
        filename,
        versions,
        util::py_rstrip(&content_lines.join("\n")).to_string(),
    )))
}

fn relic_story_by_story_id(repo: &Repo, scope: &Scope, story_id: i64) -> Result<Option<String>> {
    if story_id == 0 {
        return Ok(None);
    }
    let Some(doc_item) = repo.document.get(&story_id) else {
        return Ok(None);
    };
    let localization_ids: rustc_hash::FxHashSet<i64> =
        int_array(doc_item.f("questIDList")?)?.into_iter().collect();
    for entry in &repo.localization_excel {
        if !localization_ids.contains(&entry.i("id")?) {
            continue;
        }
        for path_value in entry.as_object().into_iter().flat_map(|o| o.values()) {
            let Some(path_str) = path_value.as_str() else {
                continue;
            };
            if path_str.is_empty() {
                continue;
            }
            let lang = repo.language.short();
            if path_str.ends_with(&format!("_{lang}")) || path_str.split('/').any(|p| p == lang) {
                let name = util::path_name(path_str);
                if let Some(content) = repo.readable_content(&format!("{name}.txt"), scope) {
                    return Ok(Some(content.clone()));
                }
            }
        }
    }
    Ok(None)
}

/// ArtifactSets.
pub fn process_artifact_set(
    repo: &Repo,
    scope: &Scope,
    set_id: i64,
) -> Result<Option<RenderedItem>> {
    let mut set_config = None;
    for set_entry in &repo.reliquary_set {
        if set_entry.i("setId")? == set_id {
            set_config = Some(set_entry);
            break;
        }
    }
    let set_config = set_config
        .ok_or_else(|| anyhow!("Artifact set configuration not found for set ID: {set_id}"))?;
    let artifact_ids = int_array(set_config.f("containsList")?)?;

    struct ArtifactInfo {
        name: String,
        description: String,
        story: String,
    }
    let mut artifacts: Vec<ArtifactInfo> = Vec::new();
    for artifact_id in artifact_ids {
        let mut artifact_config = None;
        for reliquary in &repo.reliquary {
            if reliquary.i("id")? == artifact_id {
                artifact_config = Some(reliquary);
                break;
            }
        }
        let artifact_config = artifact_config.ok_or_else(|| {
            anyhow!(
                "Artifact configuration not found for artifact ID: {artifact_id} in set {set_id}"
            )
        })?;
        let name = repo
            .tm
            .get_required(artifact_config.i("nameTextMapHash")?, scope)?;
        let description = repo
            .tm
            .get_or(artifact_config.i("descTextMapHash")?, "", scope)?;
        let story = relic_story_by_story_id(repo, scope, artifact_config.i("storyId")?)?
            .unwrap_or_default();
        artifacts.push(ArtifactInfo {
            name,
            description,
            story,
        });
    }
    if !artifacts
        .iter()
        .any(|a| !a.story.is_empty() || !a.description.is_empty())
    {
        return Ok(None);
    }

    let affix_id = set_config.i("equipAffixId")?;
    let mut affix_name_hash = None;
    for affix in &repo.equip_affix {
        if affix.i("id")? == affix_id {
            affix_name_hash = Some(affix.i("nameTextMapHash")?);
            break;
        }
    }
    let affix_name_hash = affix_name_hash
        .ok_or_else(|| anyhow!("Equip affix {affix_id} not found for set {set_id}"))?;
    let set_name = repo.tm.get_required(affix_name_hash, scope)?;

    let safe_name = util::make_safe_filename_part(&set_name);
    let mut content_lines = vec![format!("# {set_name}\n")];
    for (i, artifact) in artifacts.iter().enumerate() {
        content_lines.push(format!("## Piece {}: {}", i + 1, artifact.name));
        content_lines.push(String::new());
        if !artifact.description.is_empty() {
            content_lines.push(format!("Description: {}", artifact.description));
        }
        if !artifact.story.is_empty() {
            content_lines.push("Story:".to_string());
            content_lines.push(String::new());
            content_lines.push(artifact.story.clone());
        }
        content_lines.push(String::new());
    }
    let versions = repo.first_seen.resolve_int(Domain::ArtifactSet, set_id)?;
    Ok(Some(RenderedItem::new(
        "agd_artifact_set",
        set_name,
        set_id,
        format!("{set_id}_{safe_name}.txt"),
        versions,
        util::py_rstrip(&content_lines.join("\n")).to_string(),
    )))
}

const CREATURE_TYPE_LABELS: [(&str, &str); 2] =
    [("CODEX_MONSTER", "魔物"), ("CODEX_ANIMAL", "野生生物")];
const CREATURE_SUBTYPE_LABELS: [(&str, &str); 12] = [
    ("CODEX_SUBTYPE_ELEMENTAL", "元素生命"),
    ("CODEX_SUBTYPE_HILICHURL", "丘丘部族"),
    ("CODEX_SUBTYPE_ABYSS", "深渊"),
    ("CODEX_SUBTYPE_FATUI", "愚人众"),
    ("CODEX_SUBTYPE_AUTOMATRON", "自律机关"),
    ("CODEX_SUBTYPE_HUMAN", "人类势力"),
    ("CODEX_SUBTYPE_BEAST", "异种魔兽"),
    ("CODEX_SUBTYPE_BOSS", "首领"),
    ("CODEX_SUBTYPE_ANIMAL", "走兽"),
    ("CODEX_SUBTYPE_AVIARY", "飞禽"),
    ("CODEX_SUBTYPE_FISH", "鱼类"),
    ("CODEX_SUBTYPE_CRITTER", "小型生物"),
];

fn label_of(table: &[(&str, &'static str)], key: &str) -> Result<&'static str> {
    table
        .iter()
        .find(|(k, _)| *k == key)
        .map(|(_, v)| *v)
        .ok_or_else(|| anyhow!("unknown codex label {key}"))
}

struct CreatureInfo {
    codex_id: i64,
    name: String,
    special_name: Option<String>,
    title: Option<String>,
    description: String,
}

fn creature_info(repo: &Repo, scope: &Scope, codex_id: i64) -> Result<CreatureInfo> {
    let entry = repo
        .animal_codex
        .get(&codex_id)
        .ok_or_else(|| anyhow!("unknown animal codex {codex_id}"))?;
    let description = repo.tm.get_required(entry.i("descTextMapHash")?, scope)?;
    let describe_id = entry.i("describeId")?;

    let mut title: Option<String> = None;
    let mut special_name: Option<String> = None;
    let name_hash: i64;
    match entry.s("type")? {
        "CODEX_MONSTER" => {
            let describe = repo
                .monster_describe
                .get(&describe_id)
                .ok_or_else(|| anyhow!("unknown monster describe {describe_id}"))?;
            let title_id = describe.i("titleID")?;
            let title_entry = repo
                .monster_title
                .get(&title_id)
                .ok_or_else(|| anyhow!("unknown monster title {title_id}"))?;
            title = repo
                .tm
                .get_optional(title_entry.i("titleNameTextMapHash")?, scope)?;
            let lab_id = describe.i("specialNameLabID")?;
            let mut matches: Vec<&Value> = Vec::new();
            for entry in &repo.monster_special_name {
                if entry.i("specialNameLabID")? == lab_id {
                    matches.push(entry);
                }
            }
            if matches.is_empty() {
                bail!("Missing monster special-name lab ID {lab_id}");
            }
            if matches.len() == 1 {
                special_name = repo
                    .tm
                    .get_optional(matches[0].i("specialNameTextMapHash")?, scope)?;
            }
            name_hash = describe.i("nameTextMapHash")?;
        }
        "CODEX_ANIMAL" => {
            name_hash = repo
                .animal_describe
                .get(&describe_id)
                .ok_or_else(|| anyhow!("unknown animal describe {describe_id}"))?
                .i("nameTextMapHash")?;
        }
        other => bail!("Unknown codex type {other:?} for creature {codex_id}"),
    }
    let name = repo.tm.get_required(name_hash, scope)?;
    let special_name = special_name.filter(|s| *s != name);
    let title = title
        .filter(|t| Some(t.as_str()) != Some(name.as_str()) && Some(t) != special_name.as_ref());
    Ok(CreatureInfo {
        codex_id,
        name,
        special_name,
        title,
        description,
    })
}

/// Creatures: one codex subType group per file.
pub fn process_creature_group(
    repo: &Repo,
    scope: &Scope,
    subtype: &str,
) -> Result<Option<RenderedItem>> {
    let mut entries: Vec<(i64, i64, &Value)> = Vec::new();
    for entry in repo.animal_codex.values() {
        if entry.s("subType")? == subtype && !entry.b("isDisuse")? {
            entries.push((entry.i("sortOrder")?, entry.i("id")?, entry));
        }
    }
    entries.sort_by_key(|(sort_order, id, _)| (*sort_order, *id));
    if entries.is_empty() {
        bail!("No creatures found for codex subType {subtype:?}");
    }
    let type_label = label_of(&CREATURE_TYPE_LABELS, entries[0].2.s("type")?)?;
    let subtype_label = label_of(&CREATURE_SUBTYPE_LABELS, subtype)?;
    let creatures: Vec<CreatureInfo> = entries
        .iter()
        .map(|(_, id, _)| creature_info(repo, scope, *id))
        .collect::<Result<_>>()?;

    let group_id = util::sha256_id(subtype);
    let filename = format!("{group_id}_{subtype}.txt");
    let title = subtype_label;
    let mut content_lines = vec![format!("# {title} ({type_label})\n")];
    for creature in &creatures {
        content_lines.push(format!("## {}", creature.name));
        if let Some(special_name) = &creature.special_name {
            content_lines.push(special_name.clone());
        }
        if let Some(t) = &creature.title {
            content_lines.push(format!("Also known as: {t}"));
        }
        content_lines.push(String::new());
        content_lines.push(creature.description.clone());
        content_lines.push(String::new());
    }
    let versions = repo
        .first_seen
        .resolve_ints(Domain::AnimalCodex, creatures.iter().map(|c| c.codex_id))?;
    Ok(Some(RenderedItem::new(
        "agd_creature",
        title.to_string(),
        group_id,
        filename,
        versions,
        util::py_rstrip(&content_lines.join("\n")).to_string(),
    )))
}
