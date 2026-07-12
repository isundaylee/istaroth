//! Port of renderables/anecdote.py: Anecdote (Odd Encounter) blurbs and
//! storyboard talks.

use crate::firstseen::Domain;
use crate::issues::{IssueType, Scope};
use crate::renderables::talk::{self, TalkInfo, TalkNotFound};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::{ValueExt, int_array};
use anyhow::{Result, anyhow};

/// Anecdotes pass discovery: sorted anecdote ids.
pub fn discover(repo: &Repo) -> Result<Vec<i64>> {
    let mut ids: Vec<i64> = repo.excel.anecdote.keys().copied().collect();
    ids.sort();
    Ok(ids)
}

/// Assemble an anecdote's blurbs and storyboard talks, or None if talk-less.
/// `has_non_skip_text` is required: skip-flagged (dev/test) lines are dropped
/// at render time, so an all-skip talk would emit an empty section.
pub fn process(repo: &Repo, scope: &Scope, anecdote_id: i64) -> Result<Option<RenderedItem>> {
    let entry = repo
        .excel
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
        content_lines.extend(talk::render_talk_content(talk_info, repo.language, scope)?);
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
