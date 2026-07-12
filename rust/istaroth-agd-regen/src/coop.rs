//! Port of istaroth.agd.coop_graph: Coop story node graph + play-order walk.
//!
//! A Coop story (`coopStoryId`) carries a node graph in
//! `BinOutput/Coop/Coop*.json` (`coopInteractionMap[coopStoryId]`). Nodes are
//! `COOP_NODE_TALK` (its `coopNodeId` equals the local talk id, i.e. the
//! `_<localTalkId>` suffix of the talk filename), `COOP_NODE_SELECT` (a player
//! choice whose `nextNodeArray[i]` is the branch for option `i`, paired with
//! `selectList[i].dialogId`), and `COOP_NODE_END`. Walking from `startNodeId`
//! along `nextNodeArray` yields the talks in play order, with player-choice
//! branches.
//!
//! This module is pure graph logic over already-deobfuscated values; resolving
//! talk ids to dialogue and choice `dialogId`s to prompt text happens in the
//! hangout renderable.

use crate::vh::{ValueExt, as_i64, int_array};
use anyhow::{Result, anyhow};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;

pub struct CoopNode {
    pub node_id: i64,
    pub node_type: String,
    pub next_node_ids: Vec<i64>,
    /// `selectList` dialog ids (SELECT nodes only), positionally paired with
    /// `next_node_ids`.
    pub select_dialog_ids: Vec<i64>,
    /// Full `selectList` items (with `showCond`/`enableCond`).
    pub select_items: Vec<Value>,
    /// `coopCondGrp` on COND nodes (the routing predicate); None on others.
    pub cond_grp: Option<Value>,
    /// `savePointId` on END nodes (the ending/save-point id); None on others.
    pub save_point_id: Option<i64>,
}

pub struct CoopStoryGraph {
    pub coop_story_id: i64,
    pub start_node_id: i64,
    pub nodes: FxHashMap<i64, CoopNode>,
}

pub enum PlayStep {
    /// A play-order step pointing at a Coop talk file by its local talk id.
    Talk { local_talk_id: i64 },
    /// A player choice or conditional branch fanning into one branch per option.
    Choice { branches: Vec<ChoiceBranch> },
    /// A terminal ending step reached by walking to a `COOP_NODE_END`.
    End { save_point_id: i64 },
}

pub struct ChoiceBranch {
    pub dialog_id: Option<i64>,
    pub steps: Vec<PlayStep>,
    /// Raw `coopCondGrp` (COND branch 0 only; None for else/SELECT).
    pub cond_grp: Option<Value>,
    /// Raw `selectList[i].showCond` (SELECT only).
    pub show_cond: Option<Value>,
    /// Raw `selectList[i].enableCond` (SELECT only).
    pub enable_cond: Option<Value>,
}

pub fn build_story_graph(story: &Value) -> Result<CoopStoryGraph> {
    let mut nodes = FxHashMap::default();
    for node in story
        .f("coopMap")?
        .as_object()
        .ok_or_else(|| anyhow!("coopMap must be an object"))?
        .values()
    {
        let node_id = node.i("coopNodeId")?;
        let select_items: Vec<Value> = node
            .get_arr("selectList")
            .map(|a| a.to_vec())
            .unwrap_or_default();
        let select_dialog_ids = select_items
            .iter()
            .map(|s| s.i("dialogId"))
            .collect::<Result<Vec<i64>>>()?;
        nodes.insert(
            node_id,
            CoopNode {
                node_id,
                node_type: node.s("coopNodeType")?.to_string(),
                next_node_ids: int_array(node.f("nextNodeArray")?)?,
                select_dialog_ids,
                select_items,
                cond_grp: node.get("coopCondGrp").cloned(),
                save_point_id: node.get("savePointId").map(as_i64).transpose()?,
            },
        );
    }
    Ok(CoopStoryGraph {
        coop_story_id: story.i("id")?,
        start_node_id: story.i("startNodeId")?,
        nodes,
    })
}

/// Return the story's talks/choices in play order from `start_node_id`.
///
/// A shared `visited` set across branches prevents cycles and keeps a node
/// that multiple branches converge on from being emitted more than once.
pub fn walk_play_order(graph: &CoopStoryGraph) -> Result<Vec<PlayStep>> {
    let mut visited = FxHashSet::default();
    walk_from(graph, graph.start_node_id, &mut visited)
}

fn walk_from(
    graph: &CoopStoryGraph,
    node_id: i64,
    visited: &mut FxHashSet<i64>,
) -> Result<Vec<PlayStep>> {
    let mut steps = Vec::new();
    let mut current = Some(node_id);
    while let Some(cur) = current {
        if visited.contains(&cur) {
            break;
        }
        visited.insert(cur);
        let Some(node) = graph.nodes.get(&cur) else {
            break;
        };
        // SELECT is a player choice (its selectList supplies per-branch
        // prompts); COND is a state-based branch (no prompts). Both fan out,
        // so walk every branch to avoid dropping the alternative outcome's
        // dialogue.
        if node.node_type == "COOP_NODE_SELECT" || node.node_type == "COOP_NODE_COND" {
            let is_cond = node.node_type == "COOP_NODE_COND";
            // COND branches: index 0 is the true/positive outcome (carries
            // the routing cond_grp), index 1 is the else/default (no
            // cond_grp). SELECT branches: per-option showCond/enableCond from
            // the paired selectList entry; the `!is_cond && i < len` guard is
            // needed because COND nodes have an empty select_items list.
            let branches = node
                .next_node_ids
                .iter()
                .enumerate()
                .map(|(i, &next_id)| {
                    Ok(ChoiceBranch {
                        dialog_id: node.select_dialog_ids.get(i).copied(),
                        steps: walk_from(graph, next_id, visited)?,
                        cond_grp: if is_cond && i == 0 {
                            node.cond_grp.clone()
                        } else {
                            None
                        },
                        show_cond: if !is_cond && i < node.select_items.len() {
                            Some(node.select_items[i].f("showCond")?.clone())
                        } else {
                            None
                        },
                        enable_cond: if !is_cond && i < node.select_items.len() {
                            Some(node.select_items[i].f("enableCond")?.clone())
                        } else {
                            None
                        },
                    })
                })
                .collect::<Result<Vec<ChoiceBranch>>>()?;
            steps.push(PlayStep::Choice { branches });
            break; // the branches are the continuation
        } else if node.node_type == "COOP_NODE_END" {
            if let Some(save_point_id) = node.save_point_id {
                steps.push(PlayStep::End { save_point_id });
            }
            break;
        } else {
            // COOP_NODE_TALK emits; COOP_NODE_ACTION and others pass through.
            if node.node_type == "COOP_NODE_TALK" {
                steps.push(PlayStep::Talk {
                    local_talk_id: node.node_id,
                });
            }
            current = node.next_node_ids.first().copied();
        }
    }
    Ok(steps)
}
