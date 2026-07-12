//! Port of renderables/blossom.py: Blossom (Rich Ore Reserve) intel talks.

use crate::firstseen::Domain;
use crate::issues::{IssueType, Scope};
use crate::renderables::talk::{self, TalkInfo, TalkNotFound};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::{ValueExt, int_array};
use anyhow::{Result, anyhow, bail};
use indexmap::IndexMap;
use rustc_hash::FxHashSet;
use serde_json::Value;

/// (CHS, non-CHS) per-pass error limits (see e.g. `artifact::ERROR_LIMITS`).
pub const ERROR_LIMITS: (usize, usize) = (5, 10);

/// (refresh, talk ids) pairs for the NPC-intel blossom talk pools.
fn intel_rows(repo: &Repo) -> Result<Vec<(&Value, Vec<i64>)>> {
    let mut rows = Vec::new();
    for row in &repo.excel.blossom_talk {
        let refresh_id = row.i("refreshId")?;
        let refresh = repo
            .excel
            .blossom_refresh
            .get(&refresh_id)
            .ok_or_else(|| anyhow!("unknown blossom refresh {refresh_id}"))?;
        if refresh.s("clientShowType")? == "BLOSSOM_SHOWTYPE_NPCTALK" {
            rows.push((refresh, int_array(row.f("talkId")?)?));
        }
    }
    Ok(rows)
}

/// Blossoms pass discovery: sorted city ids with NPC-intel pools.
pub fn discover(repo: &Repo) -> Result<Vec<i64>> {
    let mut ids: Vec<i64> = intel_rows(repo)?
        .iter()
        .map(|(refresh, _)| refresh.i("cityId"))
        .collect::<Result<FxHashSet<i64>>>()?
        .into_iter()
        .collect();
    ids.sort();
    Ok(ids)
}

/// Assemble a region's blossom intel talks, sectioned by ore-type blurb.
pub fn process(repo: &Repo, scope: &Scope, city_id: i64) -> Result<Option<RenderedItem>> {
    let mut names: FxHashSet<String> = FxHashSet::default();
    // Sections key on the resolved blurb text (not its hash): several
    // refreshes share one blurb (e.g. crystal pools at different unlock
    // levels), and even same-text blurbs ship under distinct hashes.
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
    // All intel refreshes share the one Rich Ore Reserve name.
    if names.len() != 1 {
        bail!("expected exactly one blossom name, got {}", names.len());
    }
    let name = names.into_iter().next().unwrap();
    let city_name = repo.tm.get_required(
        repo.excel
            .city_config
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
    // Sections ordered by lowest refresh id; the sort must be stable by
    // insertion order on ties.
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
            // Require a non-skip line: skip-flagged (dev/test) lines are
            // dropped at render time, so an all-skip talk would emit an empty
            // section. The same intel dialogue repeats verbatim under many
            // talk ids (one per map spawn spot), so keep only the first copy
            // of each script.
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
            content_lines.extend(talk::render_talk_content(talk_info, repo.language, scope)?);
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
