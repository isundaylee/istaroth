"""Tests for quest hierarchy assembly."""

from istaroth.agd import localization, quest_hierarchy, repo


def test_build_quest_hierarchy_places_74078(data_repo: repo.DataRepo) -> None:
    """Quest 74078 should land under WQ -> series 10152 -> chapter 10155."""
    hierarchy = quest_hierarchy.build_quest_hierarchy(
        [(74078, "溪舟的尾波")], data_repo=data_repo
    )

    wq = next(t for t in hierarchy.nodes if t.key == "WQ")
    assert wq.children is not None
    series = next(s for s in wq.children if s.key == "s10152")
    assert series.children is not None
    chapter = next(c for c in series.children if c.key == "c10155")
    assert chapter.children is not None

    assert [leaf.file_id for leaf in chapter.children] == [74078]
    # The series is titled by the common prefix of its chapters' titles
    # (水仙的追迹·第N幕 ...), not the first-chapter-title fallback.
    assert series.title == "水仙的追迹"


def test_build_quest_hierarchy_groupless_chapter_stays_loose(
    data_repo: repo.DataRepo,
) -> None:
    """A groupId-less chapter (山中好长日) sits directly under its type, no series."""
    hierarchy = quest_hierarchy.build_quest_hierarchy(
        [(76095, "天堂")], data_repo=data_repo
    )

    wq = next(t for t in hierarchy.nodes if t.key == "WQ")
    assert wq.children is not None
    chapter = next(c for c in wq.children if c.key == "c10094")
    assert chapter.children is not None
    assert [leaf.file_id for leaf in chapter.children] == [76095]


def test_build_quest_hierarchy_orders_chapter_10130_by_narrative(
    data_repo: repo.DataRepo,
) -> None:
    """Chapter 10130's quests follow narrative order, not ascending id order."""
    ids = [73103, 73186, 73187, 73219, 73220, 73287]
    hierarchy = quest_hierarchy.build_quest_hierarchy(
        [(qid, str(qid)) for qid in ids], data_repo=data_repo
    )

    wq = next(t for t in hierarchy.nodes if t.key == "WQ")
    assert wq.children is not None
    series = next(s for s in wq.children if s.key == "s10130")
    assert series.children is not None
    chapter = next(c for c in series.children if c.key == "c10130")
    assert chapter.children is not None

    # 73287 is the begin quest yet has the highest id; the suggestTrack chain
    # places it first instead of last (cf. plain id sort).
    assert [leaf.file_id for leaf in chapter.children] == [
        73287,
        73219,
        73186,
        73187,
        73103,
        73220,
    ]


def test_build_quest_hierarchy_eng_type_label(data_repo: repo.DataRepo) -> None:
    """An ENG data_repo resolves quest type labels in English."""
    main_quests = data_repo.load_main_quest_excel_config_data()
    wq_quest = next(qid for qid, mq in main_quests.items() if mq.get("type") == "WQ")
    eng_repo = repo.DataRepo(data_repo.agd_path, language=localization.Language.ENG)
    hierarchy = quest_hierarchy.build_quest_hierarchy(
        [(wq_quest, "")], data_repo=eng_repo
    )
    wq = next(t for t in hierarchy.nodes if t.key == "WQ")
    assert wq.title == "World Quests"


def test_build_quest_hierarchy_standalone_bucket(data_repo: repo.DataRepo) -> None:
    """A quest with no chapter falls into its type's synthetic standalone group."""
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
    type_node = next(t for t in hierarchy.nodes if t.key == quest_type)

    # The only child is the standalone group holding the lone quest leaf.
    assert type_node.children is not None
    assert [child.key for child in type_node.children] == ["standalone"]
    standalone = type_node.children[0]
    assert standalone.title == "独立任务"
    assert standalone.children is not None
    assert [leaf.file_id for leaf in standalone.children] == [quest_id]
