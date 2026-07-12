//! Port of renderables/activity.py: loose TALK_ACTIVITY talks grouped by
//! activity id.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::renderables::talk::{self, TalkInfo};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow};
use rustc_hash::{FxHashMap, FxHashSet};

/// Leftover TALK_ACTIVITY talk ids grouped by their owning activity.
///
/// For TALK_ACTIVITY entries the excel `questId` field holds the owning
/// activity id (every current entry resolves in NewActivityExcelConfigData),
/// matching the activity referenced by their QUEST_COND_ACTIVITY_CLIENT_COND
/// begin conditions.
fn loose_talk_ids_by_activity(
    repo: &Repo,
    used_talk_ids: &FxHashSet<i64>,
) -> Result<FxHashMap<i64, Vec<i64>>> {
    let mut grouped: FxHashMap<i64, Vec<i64>> = FxHashMap::default();
    for entry in &repo.excel.talk {
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

/// Activities pass discovery: sorted activity ids with loose talks (relative
/// to the used-talk snapshot taken at pass creation).
pub fn discover(repo: &Repo, used_talk_ids: &FxHashSet<i64>) -> Result<Vec<i64>> {
    let mut ids: Vec<i64> = loose_talk_ids_by_activity(repo, used_talk_ids)?
        .keys()
        .copied()
        .collect();
    ids.sort();
    Ok(ids)
}

pub fn process(
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
        // Require a non-skip line: skip-flagged (dev/test) lines are dropped
        // at render time, so an all-skip talk would emit an empty section.
        // Loading the talk still claims its id, so dropped talks don't leak
        // back into the loose Talks pass.
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
        content_lines.extend(talk::render_talk_content(talk_info, repo.language, scope)?);
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
