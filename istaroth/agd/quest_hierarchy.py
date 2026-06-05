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


def _make_chapters(
    by_chapter: dict[int, list[types.QuestHierarchyQuest]], *, data_repo: repo.DataRepo
) -> list[types.QuestHierarchyChapter]:
    return [
        types.QuestHierarchyChapter(
            chapter_id=cid,
            chapter_title=_chapter_title(cid, data_repo=data_repo),
            quests=sorted(by_chapter[cid], key=lambda q: q.id),
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

        chapter_id = main_quest.get("chapterId") or 0
        if not chapter_id:
            standalone_buckets[quest_type].append(quest)
            continue

        if (chapter := chapters.get(chapter_id)) is not None and (
            series_id := chapter.get("groupId")
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
                series_buckets[quest_type][series_id], data_repo=data_repo
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
                    chapter_buckets.get(quest_type, {}), data_repo=data_repo
                ),
                standalone_quests=sorted(
                    standalone_buckets.get(quest_type, []), key=lambda q: q.id
                ),
            )
        )

    return types.QuestHierarchy(types=type_nodes)
