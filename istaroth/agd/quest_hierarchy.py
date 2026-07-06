"""Build the browsable quest hierarchy: type -> series -> chapter -> quest."""

from __future__ import annotations

import collections

from istaroth.agd import (
    agd_types,
    id_types,
    localization,
    processed_types,
    repo,
)
from istaroth.agd.renderables import quest

# Display order for top-level quest types; any unlisted type is appended after.
_TYPE_ORDER = ["AQ", "LQ", "WQ", "EQ", "IQ"]


def _chapter_title(chapter_id: id_types.ChapterId, *, data_repo: repo.DataRepo) -> str:
    """Resolve a chapter's display title."""
    if (chapter := data_repo.load_chapter_excel_config_data().get(chapter_id)) is None:
        raise ValueError(f"Unknown chapter {chapter_id}")
    return quest.get_chapter_title(chapter, data_repo=data_repo)


def _quest_leaf(
    quest_id: id_types.QuestId, title: str
) -> processed_types.HierarchyNode:
    return processed_types.HierarchyNode(
        key=f"q{quest_id}",
        title=title,
        children=None,
        file_id=quest_id,
        toc_eligible=False,
    )


def _leaf_id(node: processed_types.HierarchyNode) -> id_types.QuestId:
    assert node.file_id is not None, "quest leaf must carry a file_id"
    return node.file_id


def _order_quests(
    quests: list[processed_types.HierarchyNode],
    begin_quest_id: id_types.QuestId,
    *,
    main_quests: dict[id_types.QuestId, agd_types.MainQuestExcelConfigDataItem],
) -> list[processed_types.HierarchyNode]:
    """Order a chapter's quest leaves by narrative sequence.

    Quest ids do not track play order, so follow each quest's
    ``suggestTrackMainQuestList`` "next quest" pointers, seeded from the
    chapter's begin quest, taking the lowest-id branch for determinism. Quests
    the chain never reaches (parallel/branching world quests, or chapters with
    no begin quest) are appended in id order as a fallback.
    """
    by_id = {_leaf_id(q): q for q in quests}

    def _next(quest_id: id_types.QuestId) -> list[id_types.QuestId]:
        # Every quest reached here is in by_id, which build_quest_hierarchy only
        # populated with quests that have a MainQuest entry, so index strictly.
        return sorted(
            t for t in main_quests[quest_id]["suggestTrackMainQuestList"] if t in by_id
        )

    pointed = {t for quest_id in by_id for t in _next(quest_id)}
    # Seed from the declared begin quest, then any quest no other quest points to.
    starts = [begin_quest_id] if begin_quest_id in by_id else []
    starts += [quest_id for quest_id in sorted(by_id) if quest_id not in pointed]

    ordered: list[processed_types.HierarchyNode] = []
    seen: set[id_types.QuestId] = set()
    for start in starts:
        current: id_types.QuestId | None = start
        while current is not None and current not in seen:
            ordered.append(by_id[current])
            seen.add(current)
            current = next((t for t in _next(current) if t not in seen), None)
    ordered.extend(by_id[q] for q in sorted(by_id) if q not in seen)
    return ordered


def _make_chapters(
    by_chapter: dict[id_types.ChapterId, list[processed_types.HierarchyNode]],
    *,
    main_quests: dict[id_types.QuestId, agd_types.MainQuestExcelConfigDataItem],
    data_repo: repo.DataRepo,
) -> list[processed_types.HierarchyNode]:
    chapters = data_repo.load_chapter_excel_config_data()
    return [
        processed_types.HierarchyNode(
            key=f"c{cid}",
            title=_chapter_title(cid, data_repo=data_repo),
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
    quest_items: list[tuple[id_types.QuestId, str]], *, data_repo: repo.DataRepo
) -> processed_types.Hierarchy:
    """Assemble the quest hierarchy from rendered (quest_id, title) pairs.

    Each quest is placed under its type and, when available, its series (chapter
    ``groupId``, or the synthetic prefix-linked questline for groupId-less
    chapters) and chapter; quests with a chapter but no series sit directly under
    the type, and quests with no chapter land in the type's standalone bucket.
    """
    main_quests = data_repo.load_main_quest_excel_config_data()
    chapters = data_repo.load_chapter_excel_config_data()

    # type -> series_id -> chapter_id -> quests
    series_buckets: dict[
        str,
        dict[
            id_types.QuestSeriesId,
            dict[id_types.ChapterId, list[processed_types.HierarchyNode]],
        ],
    ] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(list))
    )
    # type -> synthetic series id -> chapter_id -> quests (groupId-less questlines)
    prefix_series_buckets: dict[
        str,
        dict[
            id_types.ChapterId,
            dict[id_types.ChapterId, list[processed_types.HierarchyNode]],
        ],
    ] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(list))
    )
    # type -> chapter_id -> quests (chapters with no series)
    chapter_buckets: dict[
        str, dict[id_types.ChapterId, list[processed_types.HierarchyNode]]
    ] = collections.defaultdict(lambda: collections.defaultdict(list))
    # type -> quests (no chapter)
    standalone_buckets: dict[str, list[processed_types.HierarchyNode]] = (
        collections.defaultdict(list)
    )

    for quest_id, title in quest_items:
        # A rendered quest with no MainQuest entry cannot be placed; skip it (it
        # still exists in the flat manifest). In practice every quest has one.
        if (main_quest := main_quests.get(quest_id)) is None:
            continue
        quest_type = main_quest["type"]
        leaf = _quest_leaf(quest_id, title)

        chapter_id = main_quest["chapterId"]
        if not chapter_id:
            standalone_buckets[quest_type].append(leaf)
            continue

        if (chapter := chapters.get(chapter_id)) is not None and (
            series_id := chapter["groupId"]
        ):
            series_buckets[quest_type][series_id][chapter_id].append(leaf)
        elif (
            chapter is not None
            and (
                prefix_id := quest.get_prefix_series_id(chapter_id, data_repo=data_repo)
            )
            is not None
        ):
            prefix_series_buckets[quest_type][prefix_id][chapter_id].append(leaf)
        else:
            chapter_buckets[quest_type][chapter_id].append(leaf)

    all_types = (
        set(series_buckets)
        | set(prefix_series_buckets)
        | set(chapter_buckets)
        | set(standalone_buckets)
    )
    ordered_types = [t for t in _TYPE_ORDER if t in all_types] + sorted(
        all_types - set(_TYPE_ORDER)
    )

    type_nodes = []
    for quest_type in ordered_types:
        all_series = [
            (series_id, f"s{series_id}", bucket)
            for series_id, bucket in series_buckets.get(quest_type, {}).items()
        ] + [
            (series_id, f"p{series_id}", bucket)
            for series_id, bucket in prefix_series_buckets.get(quest_type, {}).items()
        ]
        series_nodes = []
        for series_id, series_key, bucket in sorted(all_series, key=lambda s: s[0]):
            series_chapters = _make_chapters(
                bucket, main_quests=main_quests, data_repo=data_repo
            )
            # No dedicated series-name field exists, so label the series with the
            # common prefix of its chapters' titles, falling back to its first
            # chapter's title (or that chapter's first quest's title).
            assert series_chapters[0].children is not None
            series_title = quest.get_quest_group_name(
                min(bucket), data_repo=data_repo
            ) or (series_chapters[0].title or series_chapters[0].children[0].title)
            series_nodes.append(
                processed_types.HierarchyNode(
                    key=series_key,
                    title=series_title,
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
                processed_types.HierarchyNode(
                    key="standalone",
                    title=localization.get_standalone_quest_label(
                        language=data_repo.language
                    ),
                    children=standalone,
                    file_id=None,
                    # Unrelated chapter-less quests bucketed together; not a series.
                    toc_eligible=False,
                )
            )

        type_nodes.append(
            processed_types.HierarchyNode(
                key=quest_type,
                title=localization.get_quest_type_label(
                    quest_type, language=data_repo.language
                ),
                children=children,
                file_id=None,
                toc_eligible=True,
            )
        )

    return processed_types.Hierarchy(nodes=type_nodes)
