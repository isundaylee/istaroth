"""Tests for hangout (Coop) extraction: graph walk, processing, and hierarchy."""

import re
from typing import Any

import pytest

from istaroth.agd import (
    coop_graph,
    coop_hierarchy,
    localization,
    repo,
)
from istaroth.agd.renderables import hangout


def test_walk_play_order_branches_and_convergence() -> None:
    """A SELECT fans into branches; a node both branches reach is emitted once."""
    story = {
        "id": 999,
        "startNodeId": 1,
        "coopMap": {
            "1": {
                "coopNodeId": 1,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [2],
            },
            "2": {
                "coopNodeId": 2,
                "coopNodeType": "COOP_NODE_SELECT",
                "nextNodeArray": [3, 4],
                "selectList": [
                    {"dialogId": 111, "showCond": {}, "enableCond": {}},
                    {"dialogId": 222, "showCond": {}, "enableCond": {}},
                ],
            },
            "3": {
                "coopNodeId": 3,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [5],
            },
            "4": {
                "coopNodeId": 4,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [5],
            },
            "5": {
                "coopNodeId": 5,
                "coopNodeType": "COOP_NODE_END",
                "nextNodeArray": [],
            },
        },
    }
    steps = coop_graph.walk_play_order(coop_graph.build_story_graph(story))

    assert steps[0] == coop_graph.TalkStep(local_talk_id=1)
    choice = steps[1]
    assert isinstance(choice, coop_graph.ChoiceStep)
    assert [(b.dialog_id, b.steps) for b in choice.branches] == [
        (111, [coop_graph.TalkStep(local_talk_id=3)]),
        (222, [coop_graph.TalkStep(local_talk_id=4)]),
    ]


def test_walk_play_order_skips_action_and_branches_cond() -> None:
    """ACTION nodes pass through (no step); COND fans out with no prompts."""
    story = {
        "id": 999,
        "startNodeId": 1,
        "coopMap": {
            "1": {
                "coopNodeId": 1,
                "coopNodeType": "COOP_NODE_ACTION",
                "nextNodeArray": [2],
            },
            "2": {
                "coopNodeId": 2,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [3],
            },
            "3": {
                "coopNodeId": 3,
                "coopNodeType": "COOP_NODE_COND",
                "nextNodeArray": [4, 5],
            },
            "4": {
                "coopNodeId": 4,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [],
            },
            "5": {
                "coopNodeId": 5,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [],
            },
        },
    }
    steps = coop_graph.walk_play_order(coop_graph.build_story_graph(story))

    assert steps[0] == coop_graph.TalkStep(local_talk_id=2)
    cond = steps[1]
    assert isinstance(cond, coop_graph.ChoiceStep)
    # A state branch carries no player prompt.
    assert all(branch.dialog_id is None for branch in cond.branches)
    assert [b.steps for b in cond.branches] == [
        [coop_graph.TalkStep(local_talk_id=4)],
        [coop_graph.TalkStep(local_talk_id=5)],
    ]


def test_get_hangout_info_yunjin(data_repo: repo.DataRepo) -> None:
    """Quest 19017 resolves to its primary character, title, and play-ordered talks."""
    info = hangout.get_hangout_info(19017, data_repo=data_repo)
    assert info is not None
    assert info.primary_character == "云堇"
    assert info.quest_title == "郊野觅芳踪"
    assert {story.coop_story_id for story in info.stories} == {
        1901701,
        1901702,
        1901703,
        1901704,
    }

    # Dialogue is present, and at least one story branches on a player choice.
    all_steps = [step for story in info.stories for step in story.steps]
    assert any(step.talk is not None and step.talk.text for step in all_steps)
    assert any(step.choice is not None for step in all_steps)


def test_build_coop_hierarchy_character_chapter_quest(data_repo: repo.DataRepo) -> None:
    """The hierarchy groups hangout quests under character -> chapter -> quest."""
    coop_items = [
        (quest_id, "")
        for quest_id in data_repo.build_hangout_quest_to_stories_mapping()
    ]
    hierarchy = coop_hierarchy.build_coop_hierarchy(coop_items, data_repo=data_repo)

    # Yunjin has a single act, so its quest leaves hang directly off the character.
    yunjin = next(c for c in hierarchy.nodes if c.title == "云堇")
    assert yunjin.children is not None
    assert all(leaf.file_id is not None for leaf in yunjin.children)
    assert (19017, "郊野觅芳踪") in [
        (leaf.file_id, leaf.title) for leaf in yunjin.children
    ]

    # Noelle is the one character split across two hangout chapters (acts), so her
    # children are chapter groups rather than bare quest leaves.
    noelle = next(c for c in hierarchy.nodes if c.title == "诺艾尔")
    assert noelle.children is not None
    assert len(noelle.children) == 2
    assert all(ch.children is not None and ch.file_id is None for ch in noelle.children)


def test_cond_node_carries_cond_grp() -> None:
    """A COND node's branches carry the raw cond_grp dict; branch 1 (else) has None."""
    story: dict[str, Any] = {
        "id": 999,
        "startNodeId": 1,
        "coopMap": {
            "1": {
                "coopNodeId": 1,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [2],
            },
            "2": {
                "coopNodeId": 2,
                "coopNodeType": "COOP_NODE_COND",
                "nextNodeArray": [3, 4],
                "coopCondGrp": {
                    "condCombType": "LOGIC_AND",
                    "coopCondList": [
                        {"type": "COOP_COND_QUEST_FINISH", "param": [1901503]}
                    ],
                },
            },
            "3": {
                "coopNodeId": 3,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [],
            },
            "4": {
                "coopNodeId": 4,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [],
            },
        },
    }
    steps = coop_graph.walk_play_order(coop_graph.build_story_graph(story))
    assert len(steps) == 2
    cond = steps[1]
    assert isinstance(cond, coop_graph.ChoiceStep)
    assert cond.is_conditional
    # Branch 0 carries the cond; branch 1 is else.
    assert cond.branches[0].cond_grp is not None
    assert cond.branches[0].cond_grp["condCombType"] == "LOGIC_AND"
    assert cond.branches[1].cond_grp is None


def test_end_node_emits_end_step() -> None:
    """Walking to an END node with savePointId emits an EndStep."""
    story: dict[str, Any] = {
        "id": 999,
        "startNodeId": 1,
        "coopMap": {
            "1": {
                "coopNodeId": 1,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [2],
            },
            "2": {
                "coopNodeId": 2,
                "coopNodeType": "COOP_NODE_COND",
                "nextNodeArray": [3, 4],
                "coopCondGrp": {"condCombType": "LOGIC_NONE", "coopCondList": []},
            },
            "3": {
                "coopNodeId": 3,
                "coopNodeType": "COOP_NODE_END",
                "nextNodeArray": [],
                "savePointId": 90501,
            },
            "4": {
                "coopNodeId": 4,
                "coopNodeType": "COOP_NODE_TALK",
                "nextNodeArray": [],
            },
        },
    }
    steps = coop_graph.walk_play_order(coop_graph.build_story_graph(story))
    cond = steps[1]
    assert isinstance(cond, coop_graph.ChoiceStep)
    # Branch 0 leads to END → EndStep; branch 1 leads to TALK.
    assert cond.branches[0].steps == [coop_graph.EndStep(save_point_id=90501)]
    assert cond.branches[1].steps == [coop_graph.TalkStep(local_talk_id=4)]


def test_yunjin_rendered_structure(data_repo: repo.DataRepo) -> None:
    """Hangout 19017 (Yunjin) rendered output has the expected section structure."""
    raw_info = hangout.get_hangout_info(19017, data_repo=data_repo)
    assert raw_info is not None, "Hangout 19017 expected to exist"
    rendered = hangout.render_hangout(raw_info, localization.Language.CHS)
    content = rendered.content
    lines = content.split("\n")

    # Yunjin has 4 stories (1901701–1901704). Each gets exactly one ### Talk: header.
    assert len(re.findall(r"^### Talk:", content, re.MULTILINE)) == 4

    # One fork in conversation 3 with 2 branches.
    assert len(re.findall(r"^### Choice ", content, re.MULTILINE)) == 1
    assert len(re.findall(r"^#### Branch ", content, re.MULTILINE)) == 2
    assert len(re.findall(r"\*→ Ending \(save point ", content)) == 5
    assert len(re.findall(r"\*→ Next: Choice ", content)) == 0
    assert len(re.findall(r"\*→ End of conversation\*", content)) == 0
    assert len(re.findall(r"^\*Condition:", content, re.MULTILINE)) == 0
