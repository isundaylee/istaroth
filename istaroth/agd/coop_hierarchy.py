"""Build the browsable hangout hierarchy: character -> chapter -> quest."""

from __future__ import annotations

import collections

from istaroth.agd import repo, types


def _leaf_id(node: types.HierarchyNode) -> types.QuestId:
    assert node.file_id is not None, "hangout leaf must carry a file_id"
    return node.file_id


def build_coop_hierarchy(
    coop_items: list[tuple[types.QuestId, str]], *, data_repo: repo.DataRepo
) -> types.Hierarchy:
    """Assemble the hangout hierarchy from rendered (quest_id, title) pairs.

    Each hangout quest is placed under its primary character (the avatar of its
    Coop chapter) and that chapter (act). The leaf shows the act title alone (the
    character already labels the enclosing node), falling back to the manifest
    title if the act title doesn't resolve. A character with a single act is
    flattened: its quest leaves hang directly off the character node so there is
    no redundant lone-chapter level.
    """
    text_map = data_repo.load_text_map()
    main_quests = data_repo.load_main_quest_excel_config_data()
    coop_chapters = {
        chapter["id"]: chapter
        for chapter in data_repo.load_coop_chapter_excel_config_data()
    }
    avatar_names = data_repo.build_avatar_id_to_name_mapping()

    # avatar_id -> chapter_id -> quest leaves
    buckets: dict[types.AvatarId, dict[types.ChapterId, list[types.HierarchyNode]]] = (
        collections.defaultdict(lambda: collections.defaultdict(list))
    )
    for quest_id, title in coop_items:
        if (main_quest := main_quests.get(quest_id)) is None:
            continue
        if (chapter := coop_chapters.get(main_quest["chapterId"])) is None:
            continue
        act_title = text_map.get_optional(main_quest["titleTextMapHash"]) or title
        buckets[chapter["avatarId"]][chapter["id"]].append(
            types.HierarchyNode(
                key=f"q{quest_id}",
                title=act_title,
                title_key=None,
                children=None,
                file_id=quest_id,
                toc_eligible=False,
            )
        )

    character_nodes = []
    for avatar_id in sorted(buckets):
        chapter_ids = sorted(buckets[avatar_id])
        if len(chapter_ids) == 1:
            children = sorted(buckets[avatar_id][chapter_ids[0]], key=_leaf_id)
        else:
            children = [
                types.HierarchyNode(
                    key=f"c{chapter_id}",
                    title=text_map.get_optional(
                        coop_chapters[chapter_id]["chapterNameTextMapHash"]
                    )
                    or "",
                    title_key=None,
                    children=sorted(buckets[avatar_id][chapter_id], key=_leaf_id),
                    file_id=None,
                    toc_eligible=True,
                )
                for chapter_id in chapter_ids
            ]
        character_nodes.append(
            types.HierarchyNode(
                key=f"a{avatar_id}",
                title=avatar_names.get(avatar_id, str(avatar_id)),
                title_key=None,
                children=children,
                file_id=None,
                toc_eligible=True,
            )
        )

    return types.Hierarchy(nodes=character_nodes)
