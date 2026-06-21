"""Coop (hangout) story-graph parsing and play-order traversal.

A Coop story (``coopStoryId``) carries a node graph in
``BinOutput/Coop/Coop*.json`` (``coopInteractionMap[coopStoryId]``). Nodes are
``COOP_NODE_TALK`` (its ``coopNodeId`` equals the local talk id, i.e. the
``_<localTalkId>`` suffix of the talk filename), ``COOP_NODE_SELECT`` (a player
choice whose ``nextNodeArray[i]`` is the branch for option ``i``, paired with
``selectList[i].dialogId``), and ``COOP_NODE_END``. Walking from ``startNodeId``
along ``nextNodeArray`` yields the talks in play order, with player-choice
branches.

This module is pure graph logic over already-deobfuscated dicts; resolving talk
ids to dialogue and choice ``dialogId``s to prompt text happens in ``processing``.
"""

from __future__ import annotations

from typing import Any, TypeAlias

import attrs

from istaroth.agd import id_types


@attrs.define
class _CoopNode:
    node_id: id_types.CoopNodeId
    node_type: str
    next_node_ids: list[id_types.CoopNodeId]
    select_dialog_ids: list[id_types.DialogId]
    """``selectList`` dialog ids (SELECT nodes only), positionally paired with
    ``next_node_ids``."""


@attrs.define
class CoopStoryGraph:
    coop_story_id: id_types.CoopStoryId
    start_node_id: id_types.CoopNodeId
    nodes: dict[id_types.CoopNodeId, _CoopNode]


@attrs.define
class TalkStep:
    """A play-order step pointing at a Coop talk file by its local talk id."""

    local_talk_id: id_types.CoopNodeId


@attrs.define
class ChoiceBranch:
    dialog_id: id_types.DialogId | None
    steps: list[PlayStep]


@attrs.define
class ChoiceStep:
    """A player choice fanning into one branch per option."""

    branches: list[ChoiceBranch]


PlayStep: TypeAlias = TalkStep | ChoiceStep


def build_story_graph(story: dict[str, Any]) -> CoopStoryGraph:
    """Build a story graph from one deobfuscated ``coopInteractionMap`` entry."""
    nodes = {
        node["coopNodeId"]: _CoopNode(
            node_id=node["coopNodeId"],
            node_type=node["coopNodeType"],
            next_node_ids=node["nextNodeArray"],
            # selectList is present only on SELECT nodes.
            select_dialog_ids=[s["dialogId"] for s in node.get("selectList", [])],
        )
        for node in story["coopMap"].values()
    }
    return CoopStoryGraph(
        coop_story_id=story["id"], start_node_id=story["startNodeId"], nodes=nodes
    )


def walk_play_order(graph: CoopStoryGraph) -> list[PlayStep]:
    """Return the story's talks/choices in play order from ``start_node_id``.

    A shared ``visited`` set across branches prevents cycles and keeps a node that
    multiple branches converge on from being emitted more than once.
    """
    return _walk_from(graph, graph.start_node_id, set())


def _walk_from(
    graph: CoopStoryGraph,
    node_id: id_types.CoopNodeId,
    visited: set[id_types.CoopNodeId],
) -> list[PlayStep]:
    steps: list[PlayStep] = []
    current: id_types.CoopNodeId | None = node_id
    while current is not None and current not in visited:
        visited.add(current)
        if (node := graph.nodes.get(current)) is None:
            break

        # SELECT is a player choice (its selectList supplies per-branch prompts);
        # COND is a state-based branch (no prompts). Both fan out, so walk every
        # branch to avoid dropping the alternative outcome's dialogue.
        if node.node_type in ("COOP_NODE_SELECT", "COOP_NODE_COND"):
            steps.append(
                ChoiceStep(
                    branches=[
                        ChoiceBranch(
                            dialog_id=(
                                node.select_dialog_ids[i]
                                if i < len(node.select_dialog_ids)
                                else None
                            ),
                            steps=_walk_from(graph, next_id, visited),
                        )
                        for i, next_id in enumerate(node.next_node_ids)
                    ]
                )
            )
            break  # the branches are the continuation
        elif node.node_type == "COOP_NODE_END":
            break
        else:  # COOP_NODE_TALK emits; COOP_NODE_ACTION and others pass through
            if node.node_type == "COOP_NODE_TALK":
                steps.append(TalkStep(local_talk_id=node.node_id))
            current = node.next_node_ids[0] if node.next_node_ids else None

    return steps
