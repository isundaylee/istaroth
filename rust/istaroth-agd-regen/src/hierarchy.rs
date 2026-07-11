//! Ports of quest_hierarchy.py and coop_hierarchy.py.

use crate::render_quest;
use crate::repo::{Repo, Scope};
use crate::vh::ValueExt;
use anyhow::Result;
use indexmap::IndexMap;
use rustc_hash::{FxHashMap, FxHashSet};
use serde::Serialize;
use serde_json::Value;

#[derive(Serialize)]
pub struct HierarchyNode {
    pub key: String,
    pub title: Option<String>,
    pub children: Option<Vec<HierarchyNode>>,
    pub file_id: Option<i64>,
    pub toc_eligible: bool,
}

#[derive(Serialize)]
pub struct Hierarchy {
    pub nodes: Vec<HierarchyNode>,
}

fn quest_leaf(quest_id: i64, title: &str) -> HierarchyNode {
    HierarchyNode {
        key: format!("q{quest_id}"),
        title: Some(title.to_string()),
        children: None,
        file_id: Some(quest_id),
        toc_eligible: false,
    }
}

const TYPE_ORDER: [&str; 5] = ["AQ", "LQ", "WQ", "EQ", "IQ"];

fn order_quests(
    repo: &Repo,
    quests: Vec<HierarchyNode>,
    begin_quest_id: i64,
) -> Result<Vec<HierarchyNode>> {
    let mut by_id: IndexMap<i64, HierarchyNode> = IndexMap::new();
    for q in quests {
        by_id.insert(q.file_id.unwrap(), q);
    }
    let next_of = |quest_id: i64| -> Result<Vec<i64>> {
        let mut targets: Vec<i64> = repo.main_quest[&quest_id]
            .arr("suggestTrackMainQuestList")?
            .iter()
            .filter_map(|v| v.as_i64())
            .filter(|t| by_id.contains_key(t))
            .collect();
        targets.sort();
        Ok(targets)
    };
    let mut pointed: FxHashSet<i64> = FxHashSet::default();
    for &quest_id in by_id.keys() {
        pointed.extend(next_of(quest_id)?);
    }
    let mut starts: Vec<i64> = Vec::new();
    if by_id.contains_key(&begin_quest_id) {
        starts.push(begin_quest_id);
    }
    let mut sorted_ids: Vec<i64> = by_id.keys().copied().collect();
    sorted_ids.sort();
    starts.extend(sorted_ids.iter().filter(|q| !pointed.contains(q)));

    let mut ordered_ids: Vec<i64> = Vec::new();
    let mut seen: FxHashSet<i64> = FxHashSet::default();
    for start in starts {
        let mut current = Some(start);
        while let Some(cur) = current {
            if seen.contains(&cur) {
                break;
            }
            ordered_ids.push(cur);
            seen.insert(cur);
            current = next_of(cur)?.into_iter().find(|t| !seen.contains(t));
        }
    }
    for q in sorted_ids {
        if !seen.contains(&q) {
            ordered_ids.push(q);
        }
    }
    let mut by_id = by_id;
    Ok(ordered_ids
        .into_iter()
        .map(|id| by_id.shift_remove(&id).unwrap())
        .collect())
}

fn make_chapters(
    repo: &Repo,
    scope: &Scope,
    by_chapter: IndexMap<i64, Vec<HierarchyNode>>,
) -> Result<Vec<HierarchyNode>> {
    let mut chapter_ids: Vec<i64> = by_chapter.keys().copied().collect();
    chapter_ids.sort();
    let mut by_chapter = by_chapter;
    let mut nodes = Vec::new();
    for cid in chapter_ids {
        let chapter = &repo.chapter[&cid];
        let title = render_quest::get_chapter_title(repo, scope, chapter)?;
        let begin_quest_id = chapter.i("beginQuestId")? / 100;
        let quests = by_chapter.shift_remove(&cid).unwrap();
        nodes.push(HierarchyNode {
            key: format!("c{cid}"),
            title: Some(title),
            children: Some(order_quests(repo, quests, begin_quest_id)?),
            file_id: None,
            toc_eligible: true,
        });
    }
    Ok(nodes)
}

pub fn build_quest_hierarchy(repo: &Repo, quest_items: &[(i64, String)]) -> Result<Hierarchy> {
    // Python builds hierarchies with no tracking scope active, so text-map
    // accesses here are dropped; a discarded local scope replicates that.
    let scope = Scope::default();
    let scope = &scope;
    // type -> series -> chapter -> leaves; insertion-ordered like defaultdicts.
    let mut series_buckets: IndexMap<String, IndexMap<i64, IndexMap<i64, Vec<HierarchyNode>>>> =
        IndexMap::new();
    let mut chapter_buckets: IndexMap<String, IndexMap<i64, Vec<HierarchyNode>>> = IndexMap::new();
    let mut standalone_buckets: IndexMap<String, Vec<HierarchyNode>> = IndexMap::new();

    for (quest_id, title) in quest_items {
        let Some(main_quest) = repo.main_quest.get(quest_id) else {
            continue;
        };
        let quest_type = main_quest.s("type")?.to_string();
        let leaf = quest_leaf(*quest_id, title);
        let chapter_id = main_quest.i("chapterId")?;
        if chapter_id == 0 {
            standalone_buckets.entry(quest_type).or_default().push(leaf);
            continue;
        }
        let series_id = repo
            .chapter
            .get(&chapter_id)
            .map(|c| c.i("groupId"))
            .transpose()?
            .filter(|&g| g != 0);
        match series_id {
            Some(series_id) => {
                series_buckets
                    .entry(quest_type)
                    .or_default()
                    .entry(series_id)
                    .or_default()
                    .entry(chapter_id)
                    .or_default()
                    .push(leaf);
            }
            None => {
                chapter_buckets
                    .entry(quest_type)
                    .or_default()
                    .entry(chapter_id)
                    .or_default()
                    .push(leaf);
            }
        }
    }

    let all_types: FxHashSet<String> = series_buckets
        .keys()
        .chain(chapter_buckets.keys())
        .chain(standalone_buckets.keys())
        .cloned()
        .collect();
    let mut ordered_types: Vec<String> = TYPE_ORDER
        .iter()
        .filter(|t| all_types.contains(**t))
        .map(|t| t.to_string())
        .collect();
    let mut rest: Vec<String> = all_types
        .iter()
        .filter(|t| !TYPE_ORDER.contains(&t.as_str()))
        .cloned()
        .collect();
    rest.sort();
    ordered_types.extend(rest);

    let quest_type_label = |t: &str| -> Result<&'static str> {
        Ok(match t {
            "AQ" => "魔神任务",
            "LQ" => "传说任务",
            "WQ" => "世界任务",
            "EQ" => "活动任务",
            "IQ" => "每日委托",
            other => anyhow::bail!("unknown quest type {other}"),
        })
    };

    let mut type_nodes = Vec::new();
    for quest_type in ordered_types {
        let mut series_nodes = Vec::new();
        if let Some(buckets) = series_buckets.get_mut(&quest_type) {
            let mut series_ids: Vec<i64> = buckets.keys().copied().collect();
            series_ids.sort();
            for series_id in series_ids {
                let bucket = buckets.shift_remove(&series_id).unwrap();
                let min_chapter = *bucket.keys().min().unwrap();
                let series_chapters = make_chapters(repo, scope, bucket)?;
                let series_title =
                    match render_quest::get_quest_group_name(repo, scope, min_chapter)? {
                        Some(name) => Some(name),
                        None => match &series_chapters[0].title {
                            Some(t) if !t.is_empty() => Some(t.clone()),
                            _ => series_chapters[0].children.as_ref().unwrap()[0]
                                .title
                                .clone(),
                        },
                    };
                series_nodes.push(HierarchyNode {
                    key: format!("s{series_id}"),
                    title: series_title,
                    children: Some(series_chapters),
                    file_id: None,
                    toc_eligible: true,
                });
            }
        }
        let mut children = series_nodes;
        if let Some(buckets) = chapter_buckets.shift_remove(&quest_type) {
            children.extend(make_chapters(repo, scope, buckets)?);
        }
        if let Some(mut standalone) = standalone_buckets.shift_remove(&quest_type)
            && !standalone.is_empty()
        {
            standalone.sort_by_key(|n| n.file_id.unwrap());
            children.push(HierarchyNode {
                key: "standalone".to_string(),
                title: Some("独立任务".to_string()),
                children: Some(standalone),
                file_id: None,
                toc_eligible: false,
            });
        }
        type_nodes.push(HierarchyNode {
            key: quest_type.clone(),
            title: Some(quest_type_label(&quest_type)?.to_string()),
            children: Some(children),
            file_id: None,
            toc_eligible: true,
        });
    }
    Ok(Hierarchy { nodes: type_nodes })
}

pub fn build_coop_hierarchy(repo: &Repo, coop_items: &[(i64, String)]) -> Result<Hierarchy> {
    // Like build_quest_hierarchy: text-map accesses here are dropped.
    let scope = Scope::default();
    let scope = &scope;
    let coop_chapters: FxHashMap<i64, &Value> = repo
        .coop_chapter
        .iter()
        .map(|c| Ok((c.i("id")?, c)))
        .collect::<Result<_>>()?;

    let mut buckets: IndexMap<i64, IndexMap<i64, Vec<HierarchyNode>>> = IndexMap::new();
    for (quest_id, title) in coop_items {
        let Some(main_quest) = repo.main_quest.get(quest_id) else {
            continue;
        };
        let Some(chapter) = coop_chapters.get(&main_quest.i("chapterId")?) else {
            continue;
        };
        let act_title = repo
            .tm
            .get_optional(main_quest.i("titleTextMapHash")?, scope)?
            .filter(|t| !t.is_empty())
            .unwrap_or_else(|| title.clone());
        buckets
            .entry(chapter.i("avatarId").unwrap())
            .or_default()
            .entry(chapter.i("id").unwrap())
            .or_default()
            .push(HierarchyNode {
                key: format!("q{quest_id}"),
                title: Some(act_title),
                children: None,
                file_id: Some(*quest_id),
                toc_eligible: false,
            });
    }

    let mut character_nodes = Vec::new();
    let mut avatar_ids: Vec<i64> = buckets.keys().copied().collect();
    avatar_ids.sort();
    for avatar_id in avatar_ids {
        let chapters_bucket = buckets.shift_remove(&avatar_id).unwrap();
        let mut chapter_ids: Vec<i64> = chapters_bucket.keys().copied().collect();
        chapter_ids.sort();
        let mut chapters_bucket = chapters_bucket;
        let children: Vec<HierarchyNode> = if chapter_ids.len() == 1 {
            let mut leaves = chapters_bucket.shift_remove(&chapter_ids[0]).unwrap();
            leaves.sort_by_key(|n| n.file_id.unwrap());
            leaves
        } else {
            let mut nodes = Vec::new();
            for chapter_id in chapter_ids {
                let mut leaves = chapters_bucket.shift_remove(&chapter_id).unwrap();
                leaves.sort_by_key(|n| n.file_id.unwrap());
                let title = repo
                    .tm
                    .get_optional(
                        coop_chapters[&chapter_id].i("chapterNameTextMapHash")?,
                        scope,
                    )?
                    .filter(|t| !t.is_empty())
                    .unwrap_or_default();
                nodes.push(HierarchyNode {
                    key: format!("c{chapter_id}"),
                    title: Some(title),
                    children: Some(leaves),
                    file_id: None,
                    toc_eligible: true,
                });
            }
            nodes
        };
        character_nodes.push(HierarchyNode {
            key: format!("a{avatar_id}"),
            title: Some(
                repo.avatar_id_to_name
                    .get(&avatar_id)
                    .cloned()
                    .unwrap_or_else(|| avatar_id.to_string()),
            ),
            children: Some(children),
            file_id: None,
            toc_eligible: true,
        });
    }
    Ok(Hierarchy {
        nodes: character_nodes,
    })
}
