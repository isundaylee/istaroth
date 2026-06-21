"""Build the browsable quest hierarchy: type -> series -> chapter -> quest."""

from __future__ import annotations

import collections

from istaroth.agd import processing, repo, types

# Display order for top-level quest types; any unlisted type is appended after.
_TYPE_ORDER = ["AQ", "LQ", "WQ", "EQ", "IQ"]


def _chapter_title(chapter_id: types.ChapterId, *, data_repo: repo.DataRepo) -> str:
    """Resolve a chapter's display title."""
    if (chapter := data_repo.load_chapter_excel_config_data().get(chapter_id)) is None:
        raise ValueError(f"Unknown chapter {chapter_id}")
    return processing.get_chapter_title(chapter, data_repo=data_repo)


def _quest_leaf(quest_id: types.QuestId, title: str) -> types.HierarchyNode:
    return types.HierarchyNode(
        key=f"q{quest_id}",
        title=title,
        title_key=None,
        children=None,
        file_id=quest_id,
        toc_eligible=False,
    )


def _leaf_id(node: types.HierarchyNode) -> types.QuestId:
    assert node.file_id is not None, "quest leaf must carry a file_id"
    return node.file_id


def _order_quests(
    quests: list[types.HierarchyNode],
    begin_quest_id: types.QuestId,
    *,
    main_quests: dict[types.QuestId, types.MainQuestExcelConfigDataItem],
) -> list[types.HierarchyNode]:
    """Order a chapter's quest leaves by narrative sequence.

    Quest ids do not track play order, so follow each quest's
    ``suggestTrackMainQuestList`` "next quest" pointers, seeded from the
    chapter's begin quest, taking the lowest-id branch for determinism. Quests
    the chain never reaches (parallel/branching world quests, or chapters with
    no begin quest) are appended in id order as a fallback.
    """
    by_id = {_leaf_id(q): q for q in quests}

    def _next(quest_id: types.QuestId) -> list[types.QuestId]:
        # Every quest reached here is in by_id, which build_quest_hierarchy only
        # populated with quests that have a MainQuest entry, so index strictly.
        return sorted(
            t for t in main_quests[quest_id]["suggestTrackMainQuestList"] if t in by_id
        )

    pointed = {t for quest_id in by_id for t in _next(quest_id)}
    # Seed from the declared begin quest, then any quest no other quest points to.
    starts = [begin_quest_id] if begin_quest_id in by_id else []
    starts += [quest_id for quest_id in sorted(by_id) if quest_id not in pointed]

    ordered: list[types.HierarchyNode] = []
    seen: set[types.QuestId] = set()
    for start in starts:
        current: types.QuestId | None = start
        while current is not None and current not in seen:
            ordered.append(by_id[current])
            seen.add(current)
            current = next((t for t in _next(current) if t not in seen), None)
    ordered.extend(by_id[q] for q in sorted(by_id) if q not in seen)
    return ordered


def _make_chapters(
    by_chapter: dict[types.ChapterId, list[types.HierarchyNode]],
    *,
    main_quests: dict[types.QuestId, types.MainQuestExcelConfigDataItem],
    data_repo: repo.DataRepo,
) -> list[types.HierarchyNode]:
    chapters = data_repo.load_chapter_excel_config_data()
    return [
        types.HierarchyNode(
            key=f"c{cid}",
            title=_chapter_title(cid, data_repo=data_repo),
            title_key=None,
            children=_order_quests(
                by_chapter[cid],
                # by_chapter ids all come from main-quest chapterIds, every one of
                # which is present in ChapterExcelConfigData, so index strictly.
                chapters[cid]["beginQuestId"] // 100,
                main_quests=main_quests,
            ),
            file_id=None,
            toc_eligible=True,
        )
        for cid in sorted(by_chapter)
    ]


def build_quest_hierarchy(
    quest_items: list[tuple[types.QuestId, str]], *, data_repo: repo.DataRepo
) -> types.Hierarchy:
    """Assemble the quest hierarchy from rendered (quest_id, title) pairs.

    Each quest is placed under its type and, when available, its series (chapter
    ``groupId``) and chapter; quests with a chapter but no series sit directly under
    the type, and quests with no chapter land in the type's standalone bucket.
    """
    main_quests = data_repo.load_main_quest_excel_config_data()
    chapters = data_repo.load_chapter_excel_config_data()

    # type -> series_id -> chapter_id -> quests
    series_buckets: dict[
        str,
        dict[types.QuestSeriesId, dict[types.ChapterId, list[types.HierarchyNode]]],
    ] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(list))
    )
    # type -> chapter_id -> quests (chapters with no series)
    chapter_buckets: dict[str, dict[types.ChapterId, list[types.HierarchyNode]]] = (
        collections.defaultdict(lambda: collections.defaultdict(list))
    )
    # type -> quests (no chapter)
    standalone_buckets: dict[str, list[types.HierarchyNode]] = collections.defaultdict(
        list
    )

    for quest_id, title in quest_items:
        # A rendered quest with no MainQuest entry cannot be placed; skip it (it
        # still exists in the flat manifest). In practice every quest has one.
        if (main_quest := main_quests.get(quest_id)) is None:
            continue
        quest_type = main_quest["type"]
        quest = _quest_leaf(quest_id, title)

        chapter_id = main_quest["chapterId"]
        if not chapter_id:
            standalone_buckets[quest_type].append(quest)
            continue

        if (chapter := chapters.get(chapter_id)) is not None and (
            series_id := chapter["groupId"]
        ):
            series_buckets[quest_type][series_id][chapter_id].append(quest)
        else:
            chapter_buckets[quest_type][chapter_id].append(quest)

    all_types = set(series_buckets) | set(chapter_buckets) | set(standalone_buckets)
    ordered_types = [t for t in _TYPE_ORDER if t in all_types] + sorted(
        all_types - set(_TYPE_ORDER)
    )

    type_nodes = []
    for quest_type in ordered_types:
        series_nodes = []
        for series_id in sorted(series_buckets.get(quest_type, {})):
            series_chapters = _make_chapters(
                series_buckets[quest_type][series_id],
                main_quests=main_quests,
                data_repo=data_repo,
            )
            # No dedicated series-name field exists, so label the series with its
            # first chapter's title (falling back to its first quest's title).
            assert series_chapters[0].children is not None
            series_title = (
                series_chapters[0].title or series_chapters[0].children[0].title
            )
            series_nodes.append(
                types.HierarchyNode(
                    key=f"s{series_id}",
                    title=series_title,
                    title_key=None,
                    children=series_chapters,
                    file_id=None,
                    toc_eligible=True,
                )
            )

        children = [
            *series_nodes,
            *_make_chapters(
                chapter_buckets.get(quest_type, {}),
                main_quests=main_quests,
                data_repo=data_repo,
            ),
        ]
        # Wrap loose, chapter-less quests in a synthetic "standalone" group so they
        # get their own browse level, but only when the type actually has any.
        if standalone := sorted(standalone_buckets.get(quest_type, []), key=_leaf_id):
            children.append(
                types.HierarchyNode(
                    key="standalone",
                    title=None,
                    title_key="library.standalone",
                    children=standalone,
                    file_id=None,
                    # Unrelated chapter-less quests bucketed together; not a series.
                    toc_eligible=False,
                )
            )

        type_nodes.append(
            types.HierarchyNode(
                key=quest_type,
                title=None,
                title_key=f"library.questTypes.{quest_type}",
                children=children,
                file_id=None,
                toc_eligible=True,
            )
        )

    return types.Hierarchy(nodes=type_nodes)
