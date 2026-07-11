//! Port of istaroth.agd.talk_parsing.TalkParser: classify BinOutput/Talk files
//! and resolve talkId/talk-group collisions.

use crate::textmap::TextMaps;
use crate::util;
use crate::vh::{ValueExt, as_i64};
use anyhow::{Context, Result, anyhow, bail};
use indexmap::IndexMap;
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

pub struct TalkParseResult {
    pub talk_id_to_path: FxHashMap<i64, String>,
    pub talk_group_id_to_path: IndexMap<(String, String), String>,
    pub coop_story_to_paths: FxHashMap<i64, Vec<String>>,
    pub free_group_quest_to_paths: FxHashMap<i64, Vec<String>>,
}

/// Owning quest id for a FreeGroup talk, from its talkId numbering.
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

struct TalkSignature {
    dialogs: Vec<(i64, i64)>,
    dialog_texts: Vec<(i64, String)>,
    text_counts: FxHashMap<String, usize>,
    text_dialogs: FxHashSet<(i64, i64)>,
    text_ids: FxHashSet<i64>,
}

fn talk_signature(data: &Value, tm: &TextMaps) -> Result<Option<TalkSignature>> {
    // Python: KeyError (missing key) means "no dialogList"; a present non-list
    // value (including null) is a parse failure.
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
        && util::py_isdigit(suffix)
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

/// Python max(): the first maximal element on ties.
fn py_max_by_key<T, K: Ord>(items: &[T], key: impl Fn(&T) -> K) -> &T {
    let mut best = &items[0];
    let mut best_key = key(best);
    for item in &items[1..] {
        let k = key(item);
        if k > best_key {
            best = item;
            best_key = k;
        }
    }
    best
}

/// min(paths, key=(stem != talk_id_str, path)) — the canonical-name tie-break.
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
    let mut talk_group_candidates: IndexMap<(String, String), Vec<String>> = IndexMap::new();
    let mut coop_group: FxHashMap<i64, Vec<(i64, String)>> = FxHashMap::default();
    let mut talk_candidates: IndexMap<i64, Vec<String>> = IndexMap::new();
    let mut free_group: FxHashMap<i64, Vec<(i64, String)>> = FxHashMap::default();

    let handle_group = |group_type: &str,
                        rel: &str,
                        data: &Value,
                        candidates: &mut IndexMap<(String, String), Vec<String>>|
     -> Result<()> {
        let talks = data.arr("talks").with_context(|| rel.to_string())?;
        if talks.is_empty() {
            return Ok(());
        }
        let key_id = match group_type {
            "ActivityGroup" | "NpcGroup" | "StoryboardGroup" => {
                // Python `a or b or c`: first truthy operand, else the last one.
                let chain = [
                    data.get("activityId"),
                    data.get("npcId"),
                    data.get("storyboardId"),
                ];
                let chosen = chain
                    .iter()
                    .find(|v| v.is_some_and(crate::vh::truthy))
                    .copied()
                    .unwrap_or(chain[2]);
                match chosen.and_then(|v| v.as_i64()) {
                    Some(id) => id.to_string(),
                    None => bail!("no int group id in {rel}"),
                }
            }
            "GadgetGroup" => {
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
        let parts: Vec<&str> = rel.split('/').collect();
        let subdir = parts[2];
        if subdir == "BlossomGroup" {
            continue;
        }
        if subdir == "Coop" {
            let stem = util::path_stem(rel);
            let Some((story, local)) = stem.split_once('_') else {
                bail!("Malformed Coop talk filename {rel}");
            };
            if !(util::py_isdigit(story) && util::py_isdigit(local)) {
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
                Value::String(s) => util::py_int(s)?,
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
                Value::String(s) => util::py_int(s)?,
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
    let mut talk_group_id_to_path = IndexMap::new();
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

    // Resolve talkId collisions.
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
            let pool: Vec<&String> = if textful.is_empty() {
                usable.clone()
            } else {
                textful.clone()
            };
            talk_id_to_path.insert(*talk_id, min_by_canonical(pool.into_iter(), &talk_id_str));
            continue;
        }

        // Stub-vs-full by (id, content-hash) pairs. Python max() keeps the
        // FIRST maximal element on ties.
        let superset = py_max_by_key(&textful, |p| signatures[*p].text_dialogs.len());
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
        let text_superset = py_max_by_key(&textful, |p| {
            signatures[*p].text_counts.values().sum::<usize>()
        });
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
