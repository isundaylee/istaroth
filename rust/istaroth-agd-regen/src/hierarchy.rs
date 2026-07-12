//! Port of istaroth.agd.quest_hierarchy + coop_hierarchy: the browsable
//! quest hierarchy (type -> series -> chapter -> quest) and hangout
//! hierarchy (character -> chapter -> quest).

use crate::issues::Scope;
use crate::lang::Language;
use crate::renderables::quest;
use crate::repo::Repo;
use crate::vh::ValueExt;
use anyhow::Result;

use rustc_hash::{FxHashMap, FxHashSet};
use serde::Serialize;
use serde_json::Value;

/// Serialized hierarchy schema, deserialized by the Python readers
/// (`istaroth/agd/processed_types.py`) and mirrored by the frontend
/// (`frontend/src/utils/hierarchy.ts`). Parity is pinned byte-exactly by
/// `tests/contract.rs` and `tests/test_schema_contract.py` (repo root),
/// sharing `tests/fixtures/contract/`.
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

/// Schema of `metadata/agd/hierarchy.json`: the pre-baked per-category
/// document trees, keyed by category value.
#[derive(Serialize)]
pub struct Hierarchies {
    pub agd_quest: Hierarchy,
    pub agd_hangout: Hierarchy,
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

// Display order for top-level quest types; any unlisted type is appended after.
const TYPE_ORDER: [&str; 5] = ["AQ", "LQ", "WQ", "EQ", "IQ"];

/// Order a chapter's quest leaves by narrative sequence.
///
/// Quest ids do not track play order, so follow each quest's
/// `suggestTrackMainQuestList` "next quest" pointers, seeded from the
/// chapter's begin quest, taking the lowest-id branch for determinism. Quests
/// the chain never reaches (parallel/branching world quests, or chapters with
/// no begin quest) are appended in id order as a fallback.
fn order_quests(
    repo: &Repo,
    quests: Vec<HierarchyNode>,
    begin_quest_id: i64,
) -> Result<Vec<HierarchyNode>> {
    let mut by_id: FxHashMap<i64, HierarchyNode> = FxHashMap::default();
    for q in quests {
        by_id.insert(q.file_id.unwrap(), q);
    }
    let next_of = |quest_id: i64| -> Result<Vec<i64>> {
        // Every quest reached here is in by_id, which build_quest_hierarchy
        // only populated with quests that have a MainQuest entry, so index
        // strictly.
        let mut targets: Vec<i64> = repo.excel.main_quest[&quest_id]
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
    Ok(ordered_ids
        .into_iter()
        .map(|id| by_id.remove(&id).unwrap())
        .collect())
}

fn make_chapters(
    repo: &Repo,
    scope: &Scope,
    by_chapter: FxHashMap<i64, Vec<HierarchyNode>>,
) -> Result<Vec<HierarchyNode>> {
    let mut chapter_ids: Vec<i64> = by_chapter.keys().copied().collect();
    chapter_ids.sort();
    let mut by_chapter = by_chapter;
    let mut nodes = Vec::new();
    for cid in chapter_ids {
        // by_chapter ids all come from main-quest chapterIds, every one of
        // which is present in ChapterExcelConfigData, so index strictly.
        let chapter = &repo.excel.chapter[&cid];
        let title = quest::get_chapter_title(repo, scope, chapter)?;
        let begin_quest_id = chapter.i("beginQuestId")? / 100;
        let quests = by_chapter.remove(&cid).unwrap();
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

/// Assemble the quest hierarchy from rendered (quest_id, title) pairs.
///
/// Each quest is placed under its type and, when available, its series
/// (chapter `groupId`) and chapter; quests with a chapter but no series sit
/// directly under the type, and quests with no chapter land in the type's
/// standalone bucket.
pub fn build_quest_hierarchy(repo: &Repo, quest_items: &[(i64, String)]) -> Result<Hierarchy> {
    // Hierarchy building never counts toward text-map usage stats; a
    // discarded local scope drops its accesses.
    let scope = Scope::default();
    let scope = &scope;
    // type -> series -> chapter -> leaves; every level is sorted before output.
    let mut series_buckets: FxHashMap<String, FxHashMap<i64, FxHashMap<i64, Vec<HierarchyNode>>>> =
        FxHashMap::default();
    let mut chapter_buckets: FxHashMap<String, FxHashMap<i64, Vec<HierarchyNode>>> =
        FxHashMap::default();
    let mut standalone_buckets: FxHashMap<String, Vec<HierarchyNode>> = FxHashMap::default();

    for (quest_id, title) in quest_items {
        // A rendered quest with no MainQuest entry cannot be placed; skip it
        // (it still exists in the flat manifest). In practice every quest has
        // one.
        let Some(main_quest) = repo.excel.main_quest.get(quest_id) else {
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
            .excel
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
        Ok(match (t, repo.language) {
            ("AQ", Language::Chs) => "魔神任务",
            ("AQ", Language::Eng) => "Archon Quests",
            ("LQ", Language::Chs) => "传说任务",
            ("LQ", Language::Eng) => "Story Quests",
            ("WQ", Language::Chs) => "世界任务",
            ("WQ", Language::Eng) => "World Quests",
            ("EQ", Language::Chs) => "活动任务",
            ("EQ", Language::Eng) => "Event Quests",
            ("IQ", Language::Chs) => "每日委托",
            ("IQ", Language::Eng) => "Daily Commissions",
            (other, _) => anyhow::bail!("unknown quest type {other}"),
        })
    };

    let mut type_nodes = Vec::new();
    for quest_type in ordered_types {
        let mut series_nodes = Vec::new();
        if let Some(buckets) = series_buckets.get_mut(&quest_type) {
            let mut series_ids: Vec<i64> = buckets.keys().copied().collect();
            series_ids.sort();
            for series_id in series_ids {
                let bucket = buckets.remove(&series_id).unwrap();
                let min_chapter = *bucket.keys().min().unwrap();
                let series_chapters = make_chapters(repo, scope, bucket)?;
                // No dedicated series-name field exists, so label the series
                // with the common prefix of its chapters' titles, falling
                // back to its first chapter's title (or that chapter's first
                // quest's title).
                let series_title = match quest::get_quest_group_name(repo, scope, min_chapter)? {
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
        if let Some(buckets) = chapter_buckets.remove(&quest_type) {
            children.extend(make_chapters(repo, scope, buckets)?);
        }
        // Wrap loose, chapter-less quests in a synthetic "standalone" group
        // so they get their own browse level, but only when the type actually
        // has any.
        if let Some(mut standalone) = standalone_buckets.remove(&quest_type)
            && !standalone.is_empty()
        {
            standalone.sort_by_key(|n| n.file_id.unwrap());
            children.push(HierarchyNode {
                key: "standalone".to_string(),
                title: Some(
                    match repo.language {
                        Language::Chs => "独立任务",
                        Language::Eng => "Standalone Quests",
                    }
                    .to_string(),
                ),
                children: Some(standalone),
                file_id: None,
                // Unrelated chapter-less quests bucketed together; not a series.
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

/// Assemble the hangout hierarchy from rendered (quest_id, title) pairs.
///
/// Each hangout quest is placed under its primary character (the avatar of
/// its Coop chapter) and that chapter (act). The leaf shows the act title
/// alone (the character already labels the enclosing node), falling back to
/// the manifest title if the act title doesn't resolve. A character with a
/// single act is flattened: its quest leaves hang directly off the character
/// node so there is no redundant lone-chapter level.
pub fn build_coop_hierarchy(repo: &Repo, coop_items: &[(i64, String)]) -> Result<Hierarchy> {
    // Like build_quest_hierarchy: text-map accesses here are dropped.
    let scope = Scope::default();
    let scope = &scope;
    let coop_chapters: FxHashMap<i64, &Value> = repo
        .excel
        .coop_chapter
        .iter()
        .map(|c| Ok((c.i("id")?, c)))
        .collect::<Result<_>>()?;

    let mut buckets: FxHashMap<i64, FxHashMap<i64, Vec<HierarchyNode>>> = FxHashMap::default();
    for (quest_id, title) in coop_items {
        let Some(main_quest) = repo.excel.main_quest.get(quest_id) else {
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
        let chapters_bucket = buckets.remove(&avatar_id).unwrap();
        let mut chapter_ids: Vec<i64> = chapters_bucket.keys().copied().collect();
        chapter_ids.sort();
        let mut chapters_bucket = chapters_bucket;
        let children: Vec<HierarchyNode> = if chapter_ids.len() == 1 {
            let mut leaves = chapters_bucket.remove(&chapter_ids[0]).unwrap();
            leaves.sort_by_key(|n| n.file_id.unwrap());
            leaves
        } else {
            let mut nodes = Vec::new();
            for chapter_id in chapter_ids {
                let mut leaves = chapters_bucket.remove(&chapter_id).unwrap();
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
