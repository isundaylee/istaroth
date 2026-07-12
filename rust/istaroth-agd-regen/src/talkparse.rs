//! Port of istaroth.agd.talk_parsing: classify BinOutput/Talk files and
//! resolve talkId/talk-group collisions.
//!
//! Two subdirectories are special-cased rather than registered as resolvable
//! talkIds:
//! - `Coop` holds hangout dialogue named `<coopStoryId>_<localTalkId>.json`,
//!   whose local talkId collides across stories; the Hangouts renderable
//!   consumes them directly via the Coop story graph, grouped per coopStoryId.
//! - `FreeGroup` holds Lua-invoked "free talks" with no reference-graph
//!   linkage in the dump (and ids that collide with other talks); each is
//!   attached to its owning quest by the talkId-numbering heuristic and
//!   rendered in a separate quest section.

use crate::textmap::TextMaps;
use crate::util;
use crate::vh::{ValueExt, as_i64};
use anyhow::{Context, Result, anyhow, bail};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;
use std::collections::HashMap;

pub const BAD_TALK_PATHS: [&str; 9] = [
    "BinOutput/Talk/Gadget/6800002.json",
    "BinOutput/Talk/Gadget/80045.json",
    "BinOutput/Talk/Npc/7401203.json",
    "BinOutput/Talk/Npc/7401204.json",
    "BinOutput/Talk/Npc/7401205.json",
    "BinOutput/Talk/NpcOther/12634.json",
    "BinOutput/Talk/Quest/80046.json",
    "BinOutput/Talk/Quest/GlobalDialog.json",
    "BinOutput/Talk/BlossomGroup/5900009.json",
];

const GROUP_DIRECTORIES: [&str; 4] = [
    "ActivityGroup",
    "GadgetGroup",
    "NpcGroup",
    "StoryboardGroup",
];

#[derive(Default)]
pub struct TalkParseResult {
    pub talk_id_to_path: FxHashMap<i64, String>,
    pub talk_group_id_to_path: FxHashMap<(String, String), String>,
    pub coop_story_to_paths: FxHashMap<i64, Vec<String>>,
    pub free_group_quest_to_paths: FxHashMap<i64, Vec<String>>,
}

/// Owning quest id for a FreeGroup talk, inferred from its talkId numbering.
///
/// FreeGroup talkIds follow `<questId><index>`; dropping the trailing
/// two-digit index yields the quest id, except for the `<questId>99<index>`
/// ambient-talk bucket where two more digits are dropped. Returns None when
/// the id is too short to contain a quest id (degenerate FreeGroup files like
/// `7.json`).
fn free_group_quest_id(talk_id: &str) -> Option<i64> {
    let mut base = &talk_id[..talk_id.len().saturating_sub(2)];
    if base.len() >= 6 && base.ends_with("99") {
        base = &base[..base.len() - 2];
    }
    if base.is_empty() {
        None
    } else {
        base.parse().ok()
    }
}

/// Content fingerprint of a talk file used to resolve talkId collisions.
struct TalkSignature {
    /// The (dialog id, content hash) sequence, for exact-equality checks.
    dialogs: Vec<(i64, i64)>,
    /// The (dialog id, resolved text) sequence for hashes that resolve.
    dialog_texts: Vec<(i64, String)>,
    /// Resolved text multiplicities, independent of remapped dialog ids.
    text_counts: FxHashMap<String, usize>,
    /// (dialog id, content hash) pairs whose hash resolves to real text.
    text_dialogs: FxHashSet<(i64, i64)>,
    /// Dialog ids whose content hash resolves to real text.
    text_ids: FxHashSet<i64>,
}

/// Content signature of a candidate file, or None if it has no dialogList
/// (a present non-list value, including null, is a parse failure).
///
/// Resolves against the current build only (not the TextMap fallback): a
/// stale hash-named duplicate can carry a content hash that only the fallback
/// resolves, to a near-identical older-build variant of the canonical file's
/// text (e.g. differing punctuation), which would otherwise make two
/// candidates look like conflicting content and drop the talkId. Same
/// reasoning as role-name hash lookups staying current-only (see
/// `get_role_name` in renderables/talk.rs).
fn talk_signature(data: &Value, tm: &TextMaps) -> Result<Option<TalkSignature>> {
    let Some(raw) = data.get("dialogList") else {
        return Ok(None);
    };
    let dialogs = raw
        .as_array()
        .ok_or_else(|| anyhow!("dialogList must be an array"))?;
    let mut raw_dialogs = Vec::with_capacity(dialogs.len());
    for d in dialogs {
        raw_dialogs.push((d.i("id")?, d.get_i("talkContentTextMapHash").unwrap_or(0)));
    }
    let mut dialog_texts = Vec::new();
    let mut text_counts: FxHashMap<String, usize> = FxHashMap::default();
    let mut text_dialogs = FxHashSet::default();
    let mut text_ids = FxHashSet::default();
    for &(dialog_id, content_hash) in &raw_dialogs {
        if let Some(text) = tm.get_current_optional_untracked(content_hash)? {
            *text_counts.entry(text.clone()).or_insert(0) += 1;
            dialog_texts.push((dialog_id, text));
            text_dialogs.insert((dialog_id, content_hash));
            text_ids.insert(dialog_id);
        }
    }
    Ok(Some(TalkSignature {
        dialogs: raw_dialogs,
        dialog_texts,
        text_counts,
        text_dialogs,
        text_ids,
    }))
}

fn preference_key(group_id: &str, path: &str) -> (i64, i64, String) {
    let stem = util::path_stem(path);
    if stem == group_id {
        return (0, 0, path.to_string());
    }
    if let Some((prefix, suffix)) = stem.split_once('_')
        && prefix == group_id
        && util::is_ascii_digits(suffix)
    {
        return (1, -suffix.parse::<i64>().unwrap(), path.to_string());
    }
    (2, 0, path.to_string())
}

fn is_talk_file(data: &Value) -> bool {
    let Some(_) = data.as_object() else {
        return false;
    };
    let has_talk_id = data.has("talkId");
    let has_activity_id = data.has("activityId");
    let has_npc_id = data.has("npcId");
    let count = [has_talk_id, has_activity_id, has_npc_id]
        .iter()
        .filter(|&&b| b)
        .count();
    if count > 1 {
        return false;
    }
    has_talk_id
}

/// Counter multiset "<=" (every count in a bounded by b).
fn counter_le(a: &FxHashMap<String, usize>, b: &FxHashMap<String, usize>) -> bool {
    a.iter().all(|(k, v)| b.get(k).copied().unwrap_or(0) >= *v)
}

fn counter_eq(a: &FxHashMap<String, usize>, b: &FxHashMap<String, usize>) -> bool {
    a.len() == b.len() && a.iter().all(|(k, v)| b.get(k) == Some(v))
}

fn sorted_counter(a: &FxHashMap<String, usize>) -> Vec<(String, usize)> {
    let mut v: Vec<(String, usize)> = a.iter().map(|(k, c)| (k.clone(), *c)).collect();
    v.sort();
    v
}

/// Canonical-name tie-break: prefer the `<talkId>.json`-named path, then the
/// lexicographically smallest.
fn min_by_canonical<'a>(paths: impl Iterator<Item = &'a String>, talk_id_str: &str) -> String {
    paths
        .map(|p| ((util::path_stem(p) != talk_id_str, p.clone()), p))
        .min_by(|a, b| a.0.cmp(&b.0))
        .map(|(_, p)| p.clone())
        .unwrap()
}

pub fn parse_talks(
    talk_files: &FxHashMap<String, Value>,
    sorted_rels: &[String],
    tm: &TextMaps,
    init_dialogs: &FxHashMap<i64, i64>,
) -> Result<TalkParseResult> {
    let mut talk_group_candidates: FxHashMap<(String, String), Vec<String>> = FxHashMap::default();
    let mut coop_group: FxHashMap<i64, Vec<(i64, String)>> = FxHashMap::default();
    let mut talk_candidates: FxHashMap<i64, Vec<String>> = FxHashMap::default();
    let mut free_group: FxHashMap<i64, Vec<(i64, String)>> = FxHashMap::default();

    let handle_group = |group_type: &str,
                        rel: &str,
                        data: &Value,
                        candidates: &mut FxHashMap<(String, String), Vec<String>>|
     -> Result<()> {
        let talks = data.arr("talks").with_context(|| rel.to_string())?;
        if talks.is_empty() {
            return Ok(());
        }
        let key_id = match group_type {
            "ActivityGroup" | "NpcGroup" | "StoryboardGroup" => {
                // First nonzero of activityId/npcId/storyboardId; a present
                // non-int field is a schema change and errors.
                let mut chosen = None;
                for key in ["activityId", "npcId", "storyboardId"] {
                    if let Some(v) = data.get(key) {
                        let id = as_i64(v).with_context(|| format!("{key} in {rel}"))?;
                        if id != 0 {
                            chosen = Some(id);
                            break;
                        }
                    }
                }
                match chosen {
                    Some(id) => id.to_string(),
                    None => bail!("no int group id in {rel}"),
                }
            }
            "GadgetGroup" => {
                // configId alone is not unique across GadgetGroup files (issue
                // #186); fold in groupId as the file's own composite key. Both
                // fields are required on every GadgetGroup file, so a missing
                // key errors rather than silently mis-keying the file.
                format!(
                    "{}_{}",
                    data.i("configId").with_context(|| rel.to_string())?,
                    data.i("groupId").with_context(|| rel.to_string())?
                )
            }
            _ => unreachable!(),
        };
        candidates
            .entry((group_type.to_string(), key_id))
            .or_default()
            .push(rel.to_string());
        Ok(())
    };

    for rel in sorted_rels {
        if BAD_TALK_PATHS.contains(&rel.as_str()) {
            continue;
        }
        let subdir = rel
            .split('/')
            .nth(2)
            .ok_or_else(|| anyhow!("talk path too shallow: {rel}"))?;
        if subdir == "BlossomGroup" {
            continue;
        }
        if subdir == "Coop" {
            let stem = util::path_stem(rel);
            let Some((story, local)) = stem.split_once('_') else {
                bail!("Malformed Coop talk filename {rel}");
            };
            if !(util::is_ascii_digits(story) && util::is_ascii_digits(local)) {
                bail!("Malformed Coop talk filename {rel}");
            }
            coop_group
                .entry(story.parse().unwrap())
                .or_default()
                .push((local.parse().unwrap(), rel.clone()));
            continue;
        }
        let data = &talk_files[rel];
        if subdir == "FreeGroup" {
            let talk_id = match data.f("talkId")? {
                Value::Number(n) => as_i64(&Value::Number(n.clone()))?,
                Value::String(s) => util::parse_i64(s)?,
                other => bail!("bad talkId {other:?} in {rel}"),
            };
            if let Some(quest_id) = free_group_quest_id(&talk_id.to_string()) {
                free_group
                    .entry(quest_id)
                    .or_default()
                    .push((talk_id, rel.clone()));
            }
        } else if GROUP_DIRECTORIES.contains(&subdir) {
            handle_group(subdir, rel, data, &mut talk_group_candidates)?;
        } else if is_talk_file(data) {
            let talk_id = match data.f("talkId")? {
                Value::Number(n) => as_i64(&Value::Number(n.clone()))?,
                Value::String(s) => util::parse_i64(s)?,
                other => bail!("bad talkId {other:?} in {rel}"),
            };
            talk_candidates
                .entry(talk_id)
                .or_default()
                .push(rel.clone());
        } else if data.has("activityId") {
            handle_group("ActivityGroup", rel, data, &mut talk_group_candidates)?;
        } else if data.has("npcId") {
            handle_group("NpcGroup", rel, data, &mut talk_group_candidates)?;
        } else {
            bail!("Unknown talk file type {rel}");
        }
    }

    // Resolve group candidates.
    let mut talk_group_id_to_path = FxHashMap::default();
    for ((group_type, group_id), candidates) in &talk_group_candidates {
        let winner = candidates
            .iter()
            .map(|p| (preference_key(group_id, p), p))
            .min_by(|a, b| a.0.cmp(&b.0))
            .map(|(_, p)| p.clone())
            .unwrap();
        talk_group_id_to_path.insert((group_type.clone(), group_id.clone()), winner);
    }

    let mut free_group_quest_to_paths = FxHashMap::default();
    for (quest_id, mut talks) in free_group {
        talks.sort();
        free_group_quest_to_paths.insert(quest_id, talks.into_iter().map(|(_, p)| p).collect());
    }

    let mut coop_story_to_paths = FxHashMap::default();
    for (story_id, mut talks) in coop_group {
        talks.sort();
        coop_story_to_paths.insert(story_id, talks.into_iter().map(|(_, p)| p).collect());
    }

    // Collapse per-talkId candidate files into a single authoritative path.
    // Several files can share a talkId (e.g. a canonical and a hash-named
    // copy, distinct Coop hangouts reusing a local id, or the same id in
    // Quest and Npc). Resolution, in order: (1) the file whose initDialog
    // dialog actually carries text, when exactly one qualifies; (2) when the
    // text-bearing files are equivalent, the canonically-named
    // `<talkId>.json` copy over a hash-named one; (3) when one candidate's
    // text-bearing dialogs are a superset of every other's, that fuller copy
    // (the rest being stubs); (4) otherwise the talkId is genuinely
    // ambiguous and is dropped.
    let mut talk_id_to_path: FxHashMap<i64, String> = FxHashMap::default();
    for (talk_id, candidates) in &talk_candidates {
        if candidates.len() == 1 {
            talk_id_to_path.insert(*talk_id, candidates[0].clone());
            continue;
        }
        let mut signatures: HashMap<&String, TalkSignature> = HashMap::new();
        for p in candidates {
            if let Some(sig) = talk_signature(&talk_files[p], tm)? {
                signatures.insert(p, sig);
            }
        }
        let usable: Vec<&String> = candidates
            .iter()
            .filter(|p| signatures.contains_key(p))
            .collect();
        if usable.is_empty() {
            continue; // dropped
        }
        let talk_id_str = talk_id.to_string();

        if let Some(&init_dialog) = init_dialogs.get(talk_id) {
            let eligible: Vec<&&String> = usable
                .iter()
                .filter(|p| signatures[**p].text_ids.contains(&init_dialog))
                .collect();
            if eligible.len() == 1 {
                talk_id_to_path.insert(*talk_id, (**eligible[0]).clone());
                continue;
            }
        }

        let textful: Vec<&String> = usable
            .iter()
            .filter(|p| !signatures[**p].text_ids.is_empty())
            .copied()
            .collect();

        let distinct_dialogs: FxHashSet<&Vec<(i64, i64)>> =
            textful.iter().map(|p| &signatures[*p].dialogs).collect();
        let distinct_texts: FxHashSet<&Vec<(i64, String)>> = textful
            .iter()
            .map(|p| &signatures[*p].dialog_texts)
            .collect();
        let distinct_counts: FxHashSet<Vec<(String, usize)>> = textful
            .iter()
            .map(|p| sorted_counter(&signatures[*p].text_counts))
            .collect();
        if distinct_dialogs.len() <= 1 || distinct_texts.len() <= 1 || distinct_counts.len() <= 1 {
            // Equivalent content: prefer the canonically-named `<talkId>.json`
            // copy over a hash-named one. Hash-identical files can come from
            // different builds, and text-identical files can carry remapped
            // hashes for the same displayed dialogue.
            let pool: Vec<&String> = if textful.is_empty() {
                usable.clone()
            } else {
                textful.clone()
            };
            talk_id_to_path.insert(*talk_id, min_by_canonical(pool.into_iter(), &talk_id_str));
            continue;
        }

        // Stub-vs-full collision: when one candidate's text-bearing dialogs
        // are a superset of every other textful candidate's, that fuller copy
        // is authoritative and the rest are stubs missing real dialogue
        // (issue #75). Comparing the (id, content-hash) pairs of text-bearing
        // dialogs — not dialog ids alone — keeps distinct talks that merely
        // reuse local dialog ids (e.g. Coop hangouts) ambiguous.
        let superset = textful
            .iter()
            .max_by_key(|p| signatures[**p].text_dialogs.len())
            .unwrap();
        if textful.iter().all(|p| {
            signatures[*p]
                .text_dialogs
                .is_subset(&signatures[*superset].text_dialogs)
        }) {
            let winners = textful
                .iter()
                .filter(|p| signatures[**p].text_dialogs == signatures[*superset].text_dialogs)
                .copied();
            talk_id_to_path.insert(*talk_id, min_by_canonical(winners, &talk_id_str));
            continue;
        }

        // Multiset superset over resolved texts.
        let text_superset = textful
            .iter()
            .max_by_key(|p| signatures[**p].text_counts.values().sum::<usize>())
            .unwrap();
        if textful.iter().all(|p| {
            counter_le(
                &signatures[*p].text_counts,
                &signatures[*text_superset].text_counts,
            )
        }) {
            let winners = textful
                .iter()
                .filter(|p| {
                    counter_eq(
                        &signatures[**p].text_counts,
                        &signatures[*text_superset].text_counts,
                    )
                })
                .copied();
            talk_id_to_path.insert(*talk_id, min_by_canonical(winners, &talk_id_str));
            continue;
        }
        // dropped as ambiguous
    }

    Ok(TalkParseResult {
        talk_id_to_path,
        talk_group_id_to_path,
        coop_story_to_paths,
        free_group_quest_to_paths,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn free_group_quest_id_heuristic() {
        for (talk_id, expected) in [
            ("7407804", Some(74078)), // 7-digit: drop trailing index
            ("1000401", Some(10004)),
            ("602708", Some(6027)),     // 6-digit
            ("100089906", Some(10008)), // 9-digit "99" ambient bucket: drop 4
            ("402217", Some(4022)),
            ("7", None), // degenerate id too short to contain a quest id
        ] {
            assert_eq!(free_group_quest_id(talk_id), expected, "{talk_id}");
        }
    }

    fn empty_tm() -> TextMaps {
        TextMaps::for_tests(
            crate::lang::Language::Chs,
            FxHashMap::default(),
            FxHashMap::default(),
            FxHashMap::default(),
        )
    }

    fn parse(files: &[(&str, Value)], tm: &TextMaps) -> TalkParseResult {
        let talk_files: FxHashMap<String, Value> = files
            .iter()
            .map(|(rel, data)| (rel.to_string(), data.clone()))
            .collect();
        let mut sorted_rels: Vec<String> = talk_files.keys().cloned().collect();
        sorted_rels.sort();
        parse_talks(&talk_files, &sorted_rels, tm, &FxHashMap::default()).unwrap()
    }

    #[test]
    fn npc_group_duplicate_prefers_canonical_id_path() {
        let data = json!({"talks": [{}], "npcId": 1292});
        let result = parse(
            &[
                ("BinOutput/Talk/NpcGroup/cc9d0cc9.json", data.clone()),
                ("BinOutput/Talk/NpcGroup/1292.json", data),
            ],
            &empty_tm(),
        );
        assert_eq!(
            result.talk_group_id_to_path[&("NpcGroup".to_string(), "1292".to_string())],
            "BinOutput/Talk/NpcGroup/1292.json"
        );
    }

    #[test]
    fn gadget_group_composite_config_group_key() {
        // A configId alone is not unique across GadgetGroup files (issue #186):
        // files sharing configId 1003 survive as distinct composite keys.
        let result = parse(
            &[
                (
                    "BinOutput/Talk/GadgetGroup/1003_201096001.json",
                    json!({"talks": [{}], "configId": 1003, "groupId": 201096001}),
                ),
                (
                    "BinOutput/Talk/GadgetGroup/1003_220200001.json",
                    json!({"talks": [{}], "configId": 1003, "groupId": 220200001}),
                ),
            ],
            &empty_tm(),
        );
        assert_eq!(result.talk_group_id_to_path.len(), 2);
        for group_id in ["1003_201096001", "1003_220200001"] {
            assert_eq!(
                result.talk_group_id_to_path[&("GadgetGroup".to_string(), group_id.to_string())],
                format!("BinOutput/Talk/GadgetGroup/{group_id}.json")
            );
        }
    }

    #[test]
    fn gadget_group_prefers_canonical_named_composite() {
        // A hash-named file claiming the same (configId, groupId) composite
        // loses to the canonically-named copy.
        let data = json!({"talks": [{}], "configId": 4242, "groupId": 99});
        let result = parse(
            &[
                ("BinOutput/Talk/GadgetGroup/4242_99.json", data.clone()),
                ("BinOutput/Talk/GadgetGroup/26e54092.json", data),
            ],
            &empty_tm(),
        );
        assert_eq!(result.talk_group_id_to_path.len(), 1);
        assert_eq!(
            result.talk_group_id_to_path[&("GadgetGroup".to_string(), "4242_99".to_string())],
            "BinOutput/Talk/GadgetGroup/4242_99.json"
        );
    }

    fn collision_tm() -> TextMaps {
        TextMaps::for_tests(
            crate::lang::Language::Chs,
            [
                (100, "Same"),
                (101, "Same"),
                (200, "Tail"),
                (201, "Tail"),
                (300, "Only fuller"),
            ]
            .into_iter()
            .map(|(k, v)| (k, v.to_string()))
            .collect(),
            FxHashMap::default(),
            FxHashMap::default(),
        )
    }

    #[test]
    fn talk_collision_dedupes_identical_resolved_text() {
        // Different hashes are duplicate content when they resolve to the same
        // text; the canonically-named copy wins.
        let result = parse(
            &[
                (
                    "BinOutput/Talk/Quest/42.json",
                    json!({"talkId": 42, "dialogList": [
                        {"id": 1, "talkContentTextMapHash": 100},
                        {"id": 2, "talkContentTextMapHash": 200},
                    ]}),
                ),
                (
                    "BinOutput/Talk/Quest/8dc4251a.json",
                    json!({"talkId": 42, "dialogList": [
                        {"id": 1, "talkContentTextMapHash": 101},
                        {"id": 2, "talkContentTextMapHash": 201},
                    ]}),
                ),
            ],
            &collision_tm(),
        );
        assert_eq!(result.talk_id_to_path[&42], "BinOutput/Talk/Quest/42.json");
    }

    #[test]
    fn talk_collision_prefers_resolved_text_superset() {
        // A fuller candidate wins even when ids and hashes were remapped.
        let result = parse(
            &[
                (
                    "BinOutput/Talk/Quest/42.json",
                    json!({"talkId": 42, "dialogList": [
                        {"id": 1, "talkContentTextMapHash": 100},
                    ]}),
                ),
                (
                    "BinOutput/Talk/Npc/42.json",
                    json!({"talkId": 42, "dialogList": [
                        {"id": 9, "talkContentTextMapHash": 101},
                        {"id": 10, "talkContentTextMapHash": 300},
                    ]}),
                ),
            ],
            &collision_tm(),
        );
        assert_eq!(result.talk_id_to_path[&42], "BinOutput/Talk/Npc/42.json");
    }
}
