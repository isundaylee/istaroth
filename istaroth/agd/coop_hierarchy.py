"""Build the browsable hangout hierarchy: character -> chapter -> quest."""

from __future__ import annotations

import collections

from istaroth.agd import repo, types


def build_coop_hierarchy(
    coop_items: list[tuple[types.QuestId, str]], *, data_repo: repo.DataRepo
) -> types.CoopHierarchy:
    """Assemble the hangout hierarchy from rendered (quest_id, title) pairs.

    Each hangout quest is placed under its primary character (the avatar of its
    Coop chapter) and that chapter (act). The leaf shows the act title alone (the
    character already labels the enclosing node), falling back to the manifest
    title if the act title doesn't resolve.
    """
    text_map = data_repo.load_text_map()
    main_quests = data_repo.load_main_quest_excel_config_data()
    coop_chapters = {
        chapter["id"]: chapter
        for chapter in data_repo.load_coop_chapter_excel_config_data()
    }
    avatar_names = data_repo.build_avatar_id_to_name_mapping()

    # avatar_id -> chapter_id -> quests
    buckets: dict[
        types.AvatarId, dict[types.ChapterId, list[types.CoopHierarchyQuest]]
    ] = collections.defaultdict(lambda: collections.defaultdict(list))
    for quest_id, title in coop_items:
        if (main_quest := main_quests.get(quest_id)) is None:
            continue
        if (chapter := coop_chapters.get(main_quest["chapterId"])) is None:
            continue
        act_title = text_map.get_optional(main_quest["titleTextMapHash"]) or title
        buckets[chapter["avatarId"]][chapter["id"]].append(
            types.CoopHierarchyQuest(id=quest_id, title=act_title)
        )

    characters = [
        types.CoopHierarchyCharacter(
            avatar_id=avatar_id,
            character_name=avatar_names.get(avatar_id, str(avatar_id)),
            chapters=[
                types.CoopHierarchyChapter(
                    chapter_id=chapter_id,
                    chapter_title=text_map.get_optional(
                        coop_chapters[chapter_id]["chapterNameTextMapHash"]
                    )
                    or "",
                    quests=sorted(
                        buckets[avatar_id][chapter_id], key=lambda quest: quest.id
                    ),
                )
                for chapter_id in sorted(buckets[avatar_id])
            ],
        )
        for avatar_id in sorted(buckets)
    ]

    return types.CoopHierarchy(characters=characters)
