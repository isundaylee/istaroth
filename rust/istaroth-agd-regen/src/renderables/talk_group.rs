//! Port of renderables/talk_group.py.

use crate::firstseen::Domain;
use crate::issues::{IssueType, Scope};
use crate::lang::Language;
use crate::renderables::talk::{self, TalkInfo, TalkNotFound};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::talkparse::GroupType;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow, bail};
use regex::Regex;
use rustc_hash::FxHashMap;
use serde_json::Value;
use std::sync::LazyLock;

/// (CHS, non-CHS) per-pass error limits (see e.g. `artifact::ERROR_LIMITS`).
pub const ERROR_LIMITS: (usize, usize) = (120, 120);

const SPEAKER_TITLE_LIMIT: usize = 3;
static COMPOSITE_ROLE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^(.+) \((.+)\)$").unwrap());

pub struct TalkGroupInfo {
    pub talks: Vec<(TalkInfo, Vec<TalkInfo>)>,
    pub talk_ids: Vec<i64>,
}

pub fn get_talk_group_info(
    repo: &Repo,
    scope: &Scope,
    group_type: GroupType,
    group_id: &str,
) -> Result<TalkGroupInfo> {
    let path = repo
        .parse
        .talk_group_id_to_path
        .get(&(group_type, group_id.to_string()))
        .ok_or_else(|| anyhow!("unknown talk group {} {group_id}", group_type.name()))?;
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
        Value::String(s) => util::parse_i64(s),
        other => bail!("cannot int() {other:?}"),
    }
}

/// Title from the group's most talkative named speakers, or None if none.
///
/// Generic speakers (player, Paimon, black-screen text, `???`,
/// unresolved-role and missing-talk placeholders) carry no title signal and
/// are dropped; dev/test-named roles arrive already skip-flagged. The top
/// `SPEAKER_TITLE_LIMIT` names by line count are joined with ` / `, with a
/// trailing `...` when more named speakers exist.
pub fn derive_speaker_group_name(info: &TalkGroupInfo, language: Language) -> Option<String> {
    let roles = language.role_names();
    let generic_speakers: [&str; 7] = [
        roles.player,
        roles.mate_avatar,
        roles.black_screen,
        roles.paimon,
        talk::MISSING_TALK_ROLE,
        "???",
        "？？？",
    ];
    // name -> (first-seen sequence, line count); the sequence breaks count
    // ties so equally-talkative speakers list in first-appearance order.
    let mut speakers: FxHashMap<String, (usize, usize)> = FxHashMap::default();
    for (talk_info, next_talks) in &info.talks {
        for t in std::iter::once(talk_info).chain(next_talks.iter()) {
            for talk_text in &t.text {
                if talk_text.skip {
                    continue;
                }
                let Some(name) = &talk_text.role else {
                    continue;
                };
                let mut name = name.as_str();
                // A role rendered as "X (Y)" is the talk renderer's
                // by-role/by-name-hash mismatch composite; count its more
                // specific half so e.g. "旅行者 (观察花卉)" titles as
                // "观察花卉" and "遗迹的铭文 (铭文)" dedups with a plain
                // "遗迹的铭文".
                if let Some(m) = COMPOSITE_ROLE.captures(name) {
                    let g1 = m.get(1).unwrap().as_str();
                    let g2 = m.get(2).unwrap().as_str();
                    name = if generic_speakers.contains(&g1) {
                        g2
                    } else {
                        g1
                    };
                }
                if generic_speakers.contains(&name) || name.starts_with(roles.unknown_role) {
                    continue;
                }
                match speakers.get_mut(name) {
                    Some(v) => v.1 += 1,
                    None => {
                        let next_seq = speakers.len();
                        speakers.insert(name.to_string(), (next_seq, 1));
                    }
                }
            }
        }
    }
    if speakers.is_empty() {
        return None;
    }
    // Descending by count, first-appearance order on ties.
    let num_speakers = speakers.len();
    let mut items: Vec<(String, (usize, usize))> = speakers.into_iter().collect();
    items.sort_by_key(|(_, (seq, count))| (std::cmp::Reverse(*count), *seq));
    let mut top: Vec<String> = items
        .into_iter()
        .take(SPEAKER_TITLE_LIMIT)
        .map(|(name, _)| name)
        .collect();
    if num_speakers > SPEAKER_TITLE_LIMIT {
        top.push("...".to_string());
    }
    Some(top.join(" / "))
}

// GadgetGroupId always ships as a 9-digit int (min 111101079), so
// `configId * 10^GADGET_GROUP_ID_DIGITS + groupId` is collision-free and fits
// both the metadata id and JS Number.MAX_SAFE_INTEGER (max composite ~8.4e14
// vs ~9.0e15). Used to derive a stable int id for the rendered file.
const GADGET_GROUP_ID_DIGITS: u32 = 9;
// ActivityGroup activity ids overlap NpcGroup npc ids (issue #294) — e.g.
// 2001 is both an activity and an NPC — so ActivityGroup rendered files
// offset their metadata id above the NpcGroup range (max ~2e6) and below the
// GadgetGroup composite range (min ~1e12). NpcGroup, the vast majority, keeps
// the raw id.
const ACTIVITY_GROUP_METADATA_ID_OFFSET: i64 = 1_000_000_000;

pub fn render_talk_group(
    repo: &Repo,
    scope: &Scope,
    group_type: GroupType,
    group_id: &str,
    info: &TalkGroupInfo,
    group_name: Option<String>,
) -> Result<RenderedItem> {
    let type_name = group_type.name();
    let safe_type = util::make_safe_filename_part(type_name);
    let filename = format!("{group_id}_{safe_type}.txt");
    let title = match &group_name {
        Some(name) => format!("{name} ({type_name} {group_id})"),
        None => format!("{type_name} - {group_id}"),
    };

    let mut content_lines = vec![format!("# Talk Group: {title}\n")];
    for (i, (talk_info, next_talks)) in info.talks.iter().enumerate() {
        content_lines.push(format!("## Talk {i}\n"));
        content_lines.extend(talk::render_talk_content(talk_info, repo.language, scope)?);
        content_lines.push(String::new());
        for (j, next_talk) in next_talks.iter().enumerate() {
            content_lines.push(format!("### Talk {i} related talk {j}\n"));
            content_lines.extend(talk::render_talk_content(next_talk, repo.language, scope)?);
            content_lines.push(String::new());
        }
    }
    let content = content_lines.join("\n").trim_end().to_string();

    let metadata_id = match group_type {
        GroupType::Gadget => {
            let (config_str, group_str) = group_id
                .split_once('_')
                .ok_or_else(|| anyhow!("bad gadget composite id {group_id}"))?;
            let config_id: i64 = config_str.parse()?;
            let gadget_group_id: i64 = group_str.parse()?;
            config_id * 10i64.pow(GADGET_GROUP_ID_DIGITS) + gadget_group_id
        }
        GroupType::Activity => ACTIVITY_GROUP_METADATA_ID_OFFSET + util::parse_i64(group_id)?,
        GroupType::Npc => util::parse_i64(group_id)?,
        GroupType::Storyboard => bail!("unsupported talk group type StoryboardGroup"),
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

/// TalkGroups pass discovery: sorted (group type, group id) keys.
pub fn discover(repo: &Repo) -> Result<Vec<(GroupType, String)>> {
    let mut keys: Vec<(GroupType, String)> =
        repo.parse.talk_group_id_to_path.keys().cloned().collect();
    keys.sort();
    Ok(keys)
}

/// TalkGroups.process.
pub fn process(
    repo: &Repo,
    scope: &Scope,
    group_type: GroupType,
    group_id: &str,
) -> Result<Option<RenderedItem>> {
    let info = get_talk_group_info(repo, scope, group_type, group_id)?;
    if info.talks.is_empty() {
        return Ok(None);
    }
    let group_name: Option<String> = match group_type {
        GroupType::Npc => {
            let npc_id = util::parse_i64(group_id)?;
            match repo.npc_chs_name(npc_id) {
                Some(chs_name) => {
                    if util::should_skip_text(chs_name, Language::Chs) {
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
        GroupType::Activity => repo
            .activity_id_to_name
            .get(&util::parse_i64(group_id)?)
            .cloned(),
        GroupType::Gadget => derive_speaker_group_name(&info, repo.language),
        GroupType::Storyboard => bail!("unsupported talk group type StoryboardGroup"),
    };
    Ok(Some(render_talk_group(
        repo, scope, group_type, group_id, &info, group_name,
    )?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::renderables::talk::TalkText;

    /// One-line-per-role TalkGroupInfo for speaker-name derivation tests.
    fn group(roles: &[Option<&str>], skip_roles: &[&str]) -> TalkGroupInfo {
        let text = roles
            .iter()
            .enumerate()
            .map(|(i, role)| TalkText {
                role: role.map(str::to_string),
                message: "msg".to_string(),
                next_dialog_ids: vec![],
                dialog_id: i as i64,
                skip: role.is_some_and(|r| skip_roles.contains(&r)),
            })
            .collect();
        TalkGroupInfo {
            talks: vec![(TalkInfo { text }, vec![])],
            talk_ids: vec![1],
        }
    }

    #[test]
    fn derive_speaker_group_name_cases() {
        // Generic-only speakers give no name.
        assert_eq!(
            derive_speaker_group_name(
                &group(&[Some("旅行者"), Some("派蒙"), Some("???"), None], &[],),
                Language::Chs
            ),
            None
        );
        assert_eq!(
            derive_speaker_group_name(&group(&[Some("告示板")], &[]), Language::Chs),
            Some("告示板".to_string())
        );
        // Most talkative first; more than three named speakers get an ellipsis.
        assert_eq!(
            derive_speaker_group_name(
                &group(
                    &[Some("甲"), Some("乙"), Some("乙"), Some("丙"), Some("丁")],
                    &[],
                ),
                Language::Chs
            ),
            Some("乙 / 甲 / 丙 / ...".to_string())
        );
        // A generic-half composite counts as its specific half; a named-half
        // composite dedups with the plain name.
        assert_eq!(
            derive_speaker_group_name(&group(&[Some("旅行者 (观察花卉)")], &[]), Language::Chs),
            Some("观察花卉".to_string())
        );
        assert_eq!(
            derive_speaker_group_name(
                &group(&[Some("遗迹的铭文 (铭文)"), Some("遗迹的铭文")], &[],),
                Language::Chs
            ),
            Some("遗迹的铭文".to_string())
        );
        // Placeholder roles and skip-flagged (dev/test) lines are dropped.
        assert_eq!(
            derive_speaker_group_name(
                &group(&[Some("Unknown Role (TALK_ROLE_GADGET)")], &[]),
                Language::Chs
            ),
            None
        );
        assert_eq!(
            derive_speaker_group_name(&group(&[Some("[Missing Talk]")], &[]), Language::Chs),
            None
        );
        assert_eq!(
            derive_speaker_group_name(
                &group(
                    &[Some("（test）阿圆 (阿圆)"), Some("阿圆")],
                    &["（test）阿圆 (阿圆)"],
                ),
                Language::Chs
            ),
            Some("阿圆".to_string())
        );
    }
}
