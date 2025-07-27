"""Processing functions for AGD data."""

import pathlib

from istorath.agd import repo, types


def _get_localized_role_names(language: str) -> types.LocalizedRoleNames:
    """Get localized role names based on language."""
    role_names = {
        "CHS": types.LocalizedRoleNames(
            player="旅行者",
            black_screen="黑屏文本",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
        "ENG": types.LocalizedRoleNames(
            player="Traveler",
            black_screen="Black Screen Text",
            unknown_npc="Unknown NPC",
            unknown_role="Unknown Role",
        ),
        # Add more languages as needed
    }
    # Default to English for unsupported languages
    return role_names.get(language, role_names["ENG"])


def get_readable_metadata(
    readable_path: str, *, data_repo: repo.DataRepo
) -> types.ReadableMetadata:
    """Retrieve metadata for a readable file."""
    # Extract readable identifier from path (e.g., "Book100" or "Weapon11101" from path)
    path_obj = pathlib.Path(readable_path)
    readable_id = path_obj.stem

    # Load required data files
    localization_data = data_repo.load_localization_excel_config_data()
    document_data = data_repo.load_document_excel_config_data()
    text_map = data_repo.load_text_map()
    language = data_repo.language

    # Step 1: Find localization ID for the readable
    for entry in localization_data:
        # Look through all fields to find one with a path ending in the target language
        for _, path_value in entry.items():
            if (
                isinstance(path_value, str)
                and (readable_id in path_value)
                and (
                    path_value.endswith(f"_{language}")
                    or (f"/{language}/" in path_value)
                )
            ):
                localization_id = entry["id"]
                break
        else:
            continue
        break
    else:
        raise ValueError(f"Localization ID not found for readable: {readable_id}")

    # Step 2: Find document entry using localization ID
    for doc_item in document_data:
        if localization_id in doc_item["questIDList"]:
            doc_entry = doc_item
            break
    else:
        raise ValueError(
            f"Document entry not found for localization ID: {localization_id}"
        )

    # Step 3: Get title from document's titleTextMapHash
    title_hash = str(doc_entry["titleTextMapHash"])
    title = text_map.get_optional(title_hash)

    if title is None:
        raise ValueError(f"Title not found for title hash: {title_hash}")

    return types.ReadableMetadata(title=title)


def get_talk_info(talk_path: str, *, data_repo: repo.DataRepo) -> types.TalkInfo:
    """Retrieve talk information from talk file."""
    # Load talk data
    talk_data = data_repo.load_talk_data(talk_path)
    dialog_list = talk_data["dialogList"]

    # Load supporting data
    npc_data = data_repo.load_npc_excel_config_data()
    text_map = data_repo.load_text_map()

    # Create NPC ID to name mapping
    npc_id_to_name = {}
    for npc in npc_data:
        npc_id = str(npc["id"])
        name_hash = str(npc["nameTextMapHash"])
        if name_hash in text_map:
            npc_id_to_name[npc_id] = text_map[name_hash]

    # Get localized role names
    localized_roles = _get_localized_role_names(data_repo.language)

    # Process dialog items
    talk_texts = []
    for dialog_item in dialog_list:
        talk_role = dialog_item["talkRole"]
        content_hash = str(dialog_item["talkContentTextMapHash"])

        # Determine role name
        if talk_role["type"] == "TALK_ROLE_NPC":
            npc_id = talk_role["_id"]
            role = npc_id_to_name.get(
                npc_id, f"{localized_roles.unknown_npc} ({npc_id})"
            )
        elif talk_role["type"] == "TALK_ROLE_PLAYER":
            role = localized_roles.player
        elif talk_role["type"] == "TALK_ROLE_NEED_CLICK_BLACK_SCREEN":
            role = localized_roles.black_screen
        else:
            role = f"{localized_roles.unknown_role} ({talk_role['type']})"

        # Get message text
        message = text_map.get(content_hash, f"Missing text ({content_hash})")

        talk_texts.append(types.TalkText(role=role, message=message))

    return types.TalkInfo(text=talk_texts)


def get_quest_info(quest_path: str, *, data_repo: repo.DataRepo) -> types.QuestInfo:
    """Retrieve quest information from quest file."""
    # Load quest data
    quest_data = data_repo.load_quest_data(quest_path)

    # Load text map for title resolution
    text_map = data_repo.load_text_map()

    # Resolve quest title from title hash, fallback to description hash
    if (
        title_hash := quest_data.get(
            "titleTextMapHash", quest_data.get("descTextMapHash")
        )
    ) is None:
        raise ValueError(f"Could not find title for quest {quest_data['id']}")

    quest_title = text_map[str(title_hash)]

    # Process subQuests in order (maintaining quest progression sequence)
    subquest_talk_infos = []
    subquest_talk_ids = set()

    # Get subquests and sort by order field to maintain quest progression
    subquests = quest_data.get("subQuests", [])
    sorted_subquests = sorted(subquests, key=lambda x: x.get("order", 0))

    for subquest in sorted_subquests:
        sub_id = str(subquest["subId"])
        talk_file_path = f"BinOutput/Talk/Quest/{sub_id}.json"

        try:
            talk_info = get_talk_info(talk_file_path, data_repo=data_repo)
            if talk_info.text:  # Only add if there's actual dialog content
                subquest_talk_infos.append(talk_info)
                subquest_talk_ids.add(sub_id)
        except Exception:
            # Skip talks that can't be loaded
            continue

    # Process talks to find non-subquest dialogs
    non_subquest_talk_infos = []

    for talk_item in quest_data.get("talks", []):
        init_dialog_id = talk_item.get("initDialog")
        if init_dialog_id is None:
            continue  # Skip talks without initDialog
        talk_file_id = str(init_dialog_id)[:7]

        # Skip if this talk is already in subquest talks
        if talk_file_id in subquest_talk_ids:
            continue

        talk_file_path = f"BinOutput/Talk/Quest/{talk_file_id}.json"

        try:
            talk_info = get_talk_info(talk_file_path, data_repo=data_repo)
            non_subquest_talk_infos.append(talk_info)
        except Exception:
            # Skip talks that can't be loaded
            continue

    return types.QuestInfo(
        title=quest_title,
        talks=subquest_talk_infos,
        non_subquest_talks=non_subquest_talk_infos,
    )


def get_unused_text_map_info(*, data_repo: repo.DataRepo) -> types.UnusedTextMapInfo:
    """Get unused text map entries from the data repository."""
    text_map_tracker = data_repo.load_text_map()
    unused_entries = text_map_tracker.get_unused_entries()
    return types.UnusedTextMapInfo(unused_entries=unused_entries)


def get_character_story_info(
    avatar_id_str: str, *, data_repo: repo.DataRepo
) -> types.CharacterStoryInfo:
    """Get all character story information for a specific character.

    Args:
        avatar_id_str: Avatar ID as string (e.g. "10000032")
        data_repo: Data repository instance
    """
    avatar_id = int(avatar_id_str)

    # Load required data
    text_map = data_repo.load_text_map()
    avatar_data = data_repo.load_avatar_excel_config_data()
    fetter_data = data_repo.load_fetter_story_excel_config_data()

    # Find character name from avatar data
    character_name = "Unknown Character"
    for avatar in avatar_data:
        if avatar["id"] == avatar_id:
            name_hash = avatar.get("nameTextMapHash")
            if name_hash:
                character_name = text_map.get(str(name_hash), "Unknown Character")
            break

    # Collect all stories for this character
    stories = []
    for story in fetter_data:
        if story["avatarId"] == avatar_id:
            # Get story title
            title_hash = story.get("storyTitleTextMapHash")
            title = "Unknown Title"
            if title_hash:
                title = text_map.get(str(title_hash), "Unknown Title")

            # Get story content
            context_hash = story.get("storyContextTextMapHash")
            content = "Story content not found"
            if context_hash:
                content = text_map.get(str(context_hash), "Story content not found")

            stories.append(types.CharacterStory(title=title, content=content))

    return types.CharacterStoryInfo(character_name=character_name, stories=stories)
