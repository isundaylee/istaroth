//! Port of renderables/creature.py.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow, bail};
use rustc_hash::FxHashSet;
use serde_json::Value;

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
        .excel
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
                .excel
                .monster_describe
                .get(&describe_id)
                .ok_or_else(|| anyhow!("unknown monster describe {describe_id}"))?;
            let title_id = describe.i("titleID")?;
            let title_entry = repo
                .excel
                .monster_title
                .get(&title_id)
                .ok_or_else(|| anyhow!("unknown monster title {title_id}"))?;
            title = repo
                .tm
                .get_optional(title_entry.i("titleNameTextMapHash")?, scope)?;
            let lab_id = describe.i("specialNameLabID")?;
            let mut matches: Vec<&Value> = Vec::new();
            for entry in &repo.excel.monster_special_name {
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
                .excel
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

/// Creatures pass discovery: sorted distinct non-disused codex subTypes.
pub fn discover(repo: &Repo) -> Result<Vec<String>> {
    let mut subtypes: FxHashSet<String> = FxHashSet::default();
    for entry in repo.excel.animal_codex.values() {
        if !entry.b("isDisuse")? {
            subtypes.insert(entry.s("subType")?.to_string());
        }
    }
    let mut v: Vec<String> = subtypes.into_iter().collect();
    v.sort();
    Ok(v)
}

/// Creatures: one codex subType group per file.
pub fn process(repo: &Repo, scope: &Scope, subtype: &str) -> Result<Option<RenderedItem>> {
    let mut entries: Vec<(i64, i64, &Value)> = Vec::new();
    for entry in repo.excel.animal_codex.values() {
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
