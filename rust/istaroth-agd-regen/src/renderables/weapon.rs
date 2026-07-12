//! Port of renderables/weapon.py.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::{ValueExt, int_array};
use anyhow::{Context, Result, anyhow};
use indexmap::IndexMap;

/// (CHS, non-CHS) per-pass error limits (see e.g. `artifact::ERROR_LIMITS`).
pub const ERROR_LIMITS: (usize, usize) = (50, 200);

/// Weapons pass discovery: ids sorted as strings.
pub fn discover(repo: &Repo) -> Result<Vec<String>> {
    let mut ids: Vec<String> = repo.excel.weapon.keys().map(|id| id.to_string()).collect();
    ids.sort();
    Ok(ids)
}

/// Assemble a weapon's story document from its authoritative weapon config.
///
/// Follows weapon storyId -> DocumentExcelConfigData -> ordered page
/// localization ids -> readable files, joining the pages into one document.
/// Returns None when the weapon has no story (storyId 0, no document, or no
/// page has on-disk content), mirroring the artifact-set discovery model.
/// Reading each page also marks it accessed, keeping rendered pages out of
/// the generic Readables catch-all; the unrendered base/placeholder files it
/// leaves behind are dropped there by the empty/placeholder content skip.
pub fn process(repo: &Repo, scope: &Scope, weapon_id_str: &str) -> Result<Option<RenderedItem>> {
    let weapon_id = util::py_int(weapon_id_str)?;
    let weapon =
        repo.excel.weapon.get(&weapon_id).ok_or_else(|| {
            anyhow!("Weapon configuration not found for weapon ID: {weapon_id_str}")
        })?;
    let story_id = weapon.i("storyId")?;
    if story_id == 0 {
        return Ok(None);
    }
    let Some(doc_item) = repo.excel.document.get(&story_id) else {
        return Ok(None);
    };
    // Ordered dedup of questContentLocalizedId + questIDList +
    // CUSTOM_addlLocalID: first occurrence keeps its position.
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
