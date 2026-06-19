"""Tests for hangout (Coop) extraction: graph walk, processing, and hierarchy."""

from istaroth.agd import coop_graph, coop_hierarchy, processing, repo


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
                "selectList": [{"dialogId": 111}, {"dialogId": 222}],
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
    info = processing.get_hangout_info(19017, data_repo=data_repo)
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
        (quest_id, "") for quest_id in data_repo.build_hangout_quest_to_stories()
    ]
    hierarchy = coop_hierarchy.build_coop_hierarchy(coop_items, data_repo=data_repo)

    yunjin = next(c for c in hierarchy.characters if c.character_name == "云堇")
    [chapter] = yunjin.chapters
    assert chapter.chapter_title == "弦歌知雅意"
    assert (19017, "郊野觅芳踪") in [(q.id, q.title) for q in chapter.quests]

    # Noelle is the one character split across two hangout chapters (acts).
    noelle = next(c for c in hierarchy.characters if c.character_name == "诺艾尔")
    assert len(noelle.chapters) == 2
