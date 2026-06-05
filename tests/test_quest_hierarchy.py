"""Tests for quest hierarchy assembly."""

from istaroth.agd import quest_hierarchy, repo


def test_build_quest_hierarchy_places_74078(data_repo: repo.DataRepo) -> None:
    """Quest 74078 should land under WQ -> series 10152 -> chapter 10155."""
    hierarchy = quest_hierarchy.build_quest_hierarchy(
        [(74078, "溪舟的尾波")], data_repo=data_repo
    )

    wq = next(t for t in hierarchy.types if t.quest_type == "WQ")
    series = next(s for s in wq.series if s.series_id == 10152)
    chapter = next(c for c in series.chapters if c.chapter_id == 10155)

    assert [q.id for q in chapter.quests] == [74078]
    # Series is labeled with its first chapter's title.
    assert series.series_title == series.chapters[0].chapter_title
    assert series.series_title


def test_build_quest_hierarchy_standalone_bucket(data_repo: repo.DataRepo) -> None:
    """A quest with no chapter falls into its type's standalone bucket."""
    main_quests = {q["id"]: q for q in data_repo.load_main_quest_excel_config_data()}
    quest_id = next(
        qid
        for qid, mq in main_quests.items()
        if mq.get("type") and not mq.get("chapterId")
    )
    quest_type = main_quests[quest_id]["type"]

    hierarchy = quest_hierarchy.build_quest_hierarchy(
        [(quest_id, "standalone")], data_repo=data_repo
    )
    type_node = next(t for t in hierarchy.types if t.quest_type == quest_type)

    assert [q.id for q in type_node.standalone_quests] == [quest_id]
    assert not type_node.series
    assert not type_node.chapters
