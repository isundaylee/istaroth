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


def test_build_quest_hierarchy_orders_chapter_10130_by_narrative(
    data_repo: repo.DataRepo,
) -> None:
    """Chapter 10130's quests follow narrative order, not ascending id order."""
    ids = [73103, 73186, 73187, 73219, 73220, 73287]
    hierarchy = quest_hierarchy.build_quest_hierarchy(
        [(qid, str(qid)) for qid in ids], data_repo=data_repo
    )

    wq = next(t for t in hierarchy.types if t.quest_type == "WQ")
    series = next(s for s in wq.series if s.series_id == 10130)
    chapter = next(c for c in series.chapters if c.chapter_id == 10130)

    # 73287 is the begin quest yet has the highest id; the suggestTrack chain
    # places it first instead of last (cf. plain id sort).
    assert [q.id for q in chapter.quests] == [73287, 73219, 73186, 73187, 73103, 73220]


def test_build_quest_hierarchy_standalone_bucket(data_repo: repo.DataRepo) -> None:
    """A quest with no chapter falls into its type's standalone bucket."""
    main_quests = data_repo.load_main_quest_excel_config_data()
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
