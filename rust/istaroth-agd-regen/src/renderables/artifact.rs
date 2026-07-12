//! Port of renderables/artifact.py.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::{ValueExt, int_array};
use anyhow::{Result, anyhow};

/// (CHS, non-CHS) per-pass error limits: non-CHS output legitimately hits
/// per-item failures (untranslated text), so its ceiling is higher.
pub const ERROR_LIMITS: (usize, usize) = (0, 0);

/// Resolve a reliquary piece's relic story from its storyId.
///
/// Follows storyId -> DocumentExcelConfigData -> questIDList ->
/// LocalizationExcelConfigData -> readable file, returning None when the
/// piece has no story (storyId 0, no document, or no readable on disk).
fn relic_story_by_story_id(repo: &Repo, scope: &Scope, story_id: i64) -> Result<Option<String>> {
    if story_id == 0 {
        return Ok(None);
    }
    let Some(doc_item) = repo.excel.document.get(&story_id) else {
        return Ok(None);
    };
    let localization_ids: rustc_hash::FxHashSet<i64> =
        int_array(doc_item.f("questIDList")?)?.into_iter().collect();
    for entry in &repo.excel.localization {
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

/// ArtifactSets pass discovery: set ids in file order.
pub fn discover(repo: &Repo) -> Result<Vec<i64>> {
    repo.excel
        .reliquary_set
        .iter()
        .map(|s| s.i("setId"))
        .collect()
}

/// ArtifactSets.
pub fn process(repo: &Repo, scope: &Scope, set_id: i64) -> Result<Option<RenderedItem>> {
    let mut set_config = None;
    for set_entry in &repo.excel.reliquary_set {
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
        for reliquary in &repo.excel.reliquary {
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
    for affix in &repo.excel.equip_affix {
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
        content_lines.join("\n").trim_end().to_string(),
    )))
}
