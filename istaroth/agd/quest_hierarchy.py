"""Build the browsable quest hierarchy: type -> series -> chapter -> quest."""

from __future__ import annotations

import collections

from istaroth.agd import processing, repo, types

# Display order for top-level quest types; any unlisted type is appended after.
_TYPE_ORDER = ["AQ", "LQ", "WQ", "EQ", "IQ"]


def _chapter_title(chapter_id: int, *, data_repo: repo.DataRepo) -> str:
    """Resolve a chapter title, falling back to a placeholder for unknown chapters."""
    if (chapter := data_repo.load_chapter_excel_config_data().get(chapter_id)) is None:
        return f"Unknown Chapter {chapter_id}"
    return processing.get_chapter_title(chapter, data_repo=data_repo)


def _order_quests(
    quests: list[types.QuestHierarchyQuest],
    begin_quest_id: int,
    *,
    main_quests: dict[int, types.MainQuestExcelConfigDataItem],
) -> list[types.QuestHierarchyQuest]:
    """Order a chapter's quests by narrative sequence.

    Quest ids do not track play order, so follow each quest's
    ``suggestTrackMainQuestList`` "next quest" pointers, seeded from the
    chapter's begin quest, taking the lowest-id branch for determinism. Quests
    the chain never reaches (parallel/branching world quests, or chapters with
    no begin quest) are appended in id order as a fallback.
    """
    by_id = {q.id: q for q in quests}

    def _next(quest_id: int) -> list[int]:
        # Every quest reached here is in by_id, which build_quest_hierarchy only
        # populated with quests that have a MainQuest entry, so index strictly.
        return sorted(
            t for t in main_quests[quest_id]["suggestTrackMainQuestList"] if t in by_id
        )

    pointed = {t for quest_id in by_id for t in _next(quest_id)}
    # Seed from the declared begin quest, then any quest no other quest points to.
    starts = [begin_quest_id] if begin_quest_id in by_id else []
    starts += [quest_id for quest_id in sorted(by_id) if quest_id not in pointed]

    ordered: list[types.QuestHierarchyQuest] = []
    seen: set[int] = set()
    for start in starts:
        current: int | None = start
        while current is not None and current not in seen:
            ordered.append(by_id[current])
            seen.add(current)
            current = next((t for t in _next(current) if t not in seen), None)
    ordered.extend(by_id[q] for q in sorted(by_id) if q not in seen)
    return ordered


def _make_chapters(
    by_chapter: dict[int, list[types.QuestHierarchyQuest]],
    *,
    main_quests: dict[int, types.MainQuestExcelConfigDataItem],
    data_repo: repo.DataRepo,
) -> list[types.QuestHierarchyChapter]:
    chapters = data_repo.load_chapter_excel_config_data()
    return [
        types.QuestHierarchyChapter(
            chapter_id=cid,
            chapter_title=_chapter_title(cid, data_repo=data_repo),
            quests=_order_quests(
                by_chapter[cid],
                # chapter_buckets may hold ids absent from ChapterExcelConfigData
                # (unknown chapters); those have no begin quest to seed from.
                (chapters[cid]["beginQuestId"] if cid in chapters else 0) // 100,
                main_quests=main_quests,
            ),
        )
        for cid in sorted(by_chapter)
    ]


def build_quest_hierarchy(
    quest_items: list[tuple[int, str]], *, data_repo: repo.DataRepo
) -> types.QuestHierarchy:
    """Assemble the quest hierarchy from rendered (quest_id, title) pairs.

    Each quest is placed under its type and, when available, its series (chapter
    ``groupId``) and chapter; quests with a chapter but no series sit directly under
    the type, and quests with no chapter land in the type's standalone bucket.
    """
    main_quests = {q["id"]: q for q in data_repo.load_main_quest_excel_config_data()}
    chapters = data_repo.load_chapter_excel_config_data()

    # type -> series_id -> chapter_id -> quests
    series_buckets: dict[str, dict[int, dict[int, list[types.QuestHierarchyQuest]]]] = (
        collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(list))
        )
    )
    # type -> chapter_id -> quests (chapters with no series)
    chapter_buckets: dict[str, dict[int, list[types.QuestHierarchyQuest]]] = (
        collections.defaultdict(lambda: collections.defaultdict(list))
    )
    # type -> quests (no chapter)
    standalone_buckets: dict[str, list[types.QuestHierarchyQuest]] = (
        collections.defaultdict(list)
    )

    for quest_id, title in quest_items:
        # A rendered quest with no MainQuest entry cannot be placed; skip it (it
        # still exists in the flat manifest). In practice every quest has one.
        if (main_quest := main_quests.get(quest_id)) is None:
            continue
        quest_type = main_quest["type"]
        quest = types.QuestHierarchyQuest(id=quest_id, title=title)

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
            if series_chapters[0].chapter_title:
                series_title = series_chapters[0].chapter_title
            else:
                series_title = series_chapters[0].quests[0].title
            series_nodes.append(
                types.QuestHierarchySeries(
                    series_id=series_id,
                    series_title=series_title,
                    chapters=series_chapters,
                )
            )

        type_nodes.append(
            types.QuestHierarchyType(
                quest_type=quest_type,
                series=series_nodes,
                chapters=_make_chapters(
                    chapter_buckets.get(quest_type, {}),
                    main_quests=main_quests,
                    data_repo=data_repo,
                ),
                standalone_quests=sorted(
                    standalone_buckets.get(quest_type, []), key=lambda q: q.id
                ),
            )
        )

    return types.QuestHierarchy(types=type_nodes)
