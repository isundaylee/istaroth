//! Port of istaroth.agd.coop_graph: Coop story node graph + play-order walk.

use crate::vh::{ValueExt, as_i64, int_array};
use anyhow::{Result, anyhow};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;

pub struct CoopNode {
    pub node_id: i64,
    pub node_type: String,
    pub next_node_ids: Vec<i64>,
    pub select_dialog_ids: Vec<i64>,
    pub select_items: Vec<Value>,
    pub cond_grp: Option<Value>,
    pub save_point_id: Option<i64>,
}

pub struct CoopStoryGraph {
    pub coop_story_id: i64,
    pub start_node_id: i64,
    pub nodes: FxHashMap<i64, CoopNode>,
}

pub enum PlayStep {
    Talk { local_talk_id: i64 },
    Choice { branches: Vec<ChoiceBranch> },
    End { save_point_id: i64 },
}

pub struct ChoiceBranch {
    pub dialog_id: Option<i64>,
    pub steps: Vec<PlayStep>,
    pub cond_grp: Option<Value>,
    pub show_cond: Option<Value>,
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
        if node.node_type == "COOP_NODE_SELECT" || node.node_type == "COOP_NODE_COND" {
            let is_cond = node.node_type == "COOP_NODE_COND";
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
            break;
        } else if node.node_type == "COOP_NODE_END" {
            if let Some(save_point_id) = node.save_point_id {
                steps.push(PlayStep::End { save_point_id });
            }
            break;
        } else {
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
