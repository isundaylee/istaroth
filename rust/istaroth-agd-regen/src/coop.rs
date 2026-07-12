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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn walk(story: Value) -> Vec<PlayStep> {
        walk_play_order(&build_story_graph(&story).unwrap()).unwrap()
    }

    fn talk_id(step: &PlayStep) -> i64 {
        match step {
            PlayStep::Talk { local_talk_id } => *local_talk_id,
            _ => panic!("expected Talk step"),
        }
    }

    fn branches(step: &PlayStep) -> &[ChoiceBranch] {
        match step {
            PlayStep::Choice { branches } => branches,
            _ => panic!("expected Choice step"),
        }
    }

    #[test]
    fn walk_play_order_branches_and_convergence() {
        // A SELECT fans into branches; a node both branches reach is emitted once.
        let steps = walk(json!({
            "id": 999,
            "startNodeId": 1,
            "coopMap": {
                "1": {"coopNodeId": 1, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": [2]},
                "2": {"coopNodeId": 2, "coopNodeType": "COOP_NODE_SELECT", "nextNodeArray": [3, 4],
                      "selectList": [
                          {"dialogId": 111, "showCond": {}, "enableCond": {}},
                          {"dialogId": 222, "showCond": {}, "enableCond": {}},
                      ]},
                "3": {"coopNodeId": 3, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": [5]},
                "4": {"coopNodeId": 4, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": [5]},
                "5": {"coopNodeId": 5, "coopNodeType": "COOP_NODE_END", "nextNodeArray": []},
            },
        }));
        assert_eq!(steps.len(), 2);
        assert_eq!(talk_id(&steps[0]), 1);
        let choice = branches(&steps[1]);
        let flat: Vec<(Option<i64>, Vec<i64>)> = choice
            .iter()
            .map(|b| (b.dialog_id, b.steps.iter().map(talk_id).collect()))
            .collect();
        assert_eq!(flat, vec![(Some(111), vec![3]), (Some(222), vec![4])]);
    }

    #[test]
    fn walk_play_order_skips_action_and_branches_cond() {
        // ACTION nodes pass through (no step); COND fans out with no prompts.
        let steps = walk(json!({
            "id": 999,
            "startNodeId": 1,
            "coopMap": {
                "1": {"coopNodeId": 1, "coopNodeType": "COOP_NODE_ACTION", "nextNodeArray": [2]},
                "2": {"coopNodeId": 2, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": [3]},
                "3": {"coopNodeId": 3, "coopNodeType": "COOP_NODE_COND", "nextNodeArray": [4, 5],
                      "coopCondGrp": {
                          "condCombType": "LOGIC_AND",
                          "coopCondList": [{"type": "COOP_COND_QUEST_FINISH", "param": [1901503]}],
                      }},
                "4": {"coopNodeId": 4, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": []},
                "5": {"coopNodeId": 5, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": []},
            },
        }));
        assert_eq!(steps.len(), 2);
        assert_eq!(talk_id(&steps[0]), 2);
        let cond = branches(&steps[1]);
        assert!(cond.iter().all(|b| b.dialog_id.is_none()));
        assert_eq!(talk_id(&cond[0].steps[0]), 4);
        assert_eq!(talk_id(&cond[1].steps[0]), 5);
        // Branch 0 carries the routing cond_grp; branch 1 is else.
        assert_eq!(
            cond[0].cond_grp.as_ref().unwrap()["condCombType"],
            "LOGIC_AND"
        );
        assert!(cond[1].cond_grp.is_none());
    }

    #[test]
    fn end_node_emits_end_step() {
        // Walking to an END node with savePointId emits an End step.
        let steps = walk(json!({
            "id": 999,
            "startNodeId": 1,
            "coopMap": {
                "1": {"coopNodeId": 1, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": [2]},
                "2": {"coopNodeId": 2, "coopNodeType": "COOP_NODE_COND", "nextNodeArray": [3, 4],
                      "coopCondGrp": {"condCombType": "LOGIC_NONE", "coopCondList": []}},
                "3": {"coopNodeId": 3, "coopNodeType": "COOP_NODE_END", "nextNodeArray": [],
                      "savePointId": 90501},
                "4": {"coopNodeId": 4, "coopNodeType": "COOP_NODE_TALK", "nextNodeArray": []},
            },
        }));
        let cond = branches(&steps[1]);
        assert!(matches!(
            cond[0].steps[..],
            [PlayStep::End {
                save_point_id: 90501
            }]
        ));
        assert_eq!(talk_id(&cond[1].steps[0]), 4);
    }
}
