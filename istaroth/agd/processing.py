"""Processing functions for AGD data."""

import pathlib
from threading import local

from istaroth.agd import localization, repo, types


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
    language_short = data_repo.language_short

    # Step 1: Find localization ID for the readable
    for entry in localization_data:
        # Look through all fields to find one with a path ending in the target language_short
        for _, path_value in entry.items():
            if (
                isinstance(path_value, str)
                and (readable_id in path_value)
                and (
                    path_value.endswith(f"_{language_short}")
                    or (f"/{language_short}/" in path_value)
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


def get_talk_info_by_id(
    talk_id_str: str, *, data_repo: repo.DataRepo
) -> types.TalkInfo:
    """Retrieve talk information by talk ID."""
    # Get talk file path through tracker (this automatically tracks access)
    talk_tracker = data_repo.load_talk_excel_config_data()
    talk_file_path = talk_tracker.get_talk_file_path(talk_id_str)

    if talk_file_path is None:
        raise ValueError(f"Talk ID {talk_id_str} not found")

    return get_talk_info(talk_file_path, data_repo=data_repo)


def get_talk_info(talk_path: str, *, data_repo: repo.DataRepo) -> types.TalkInfo:
    """Retrieve talk information from talk file."""
    # Load talk data
    talk_data = data_repo.load_talk_data(talk_path)
    dialog_list = talk_data["dialogList"]

    # Load supporting data
    text_map = data_repo.load_text_map()

    # Get cached mappings
    npc_id_to_name = data_repo.get_npc_id_to_name_mapping()
    dialog_id_to_role_hash = data_repo.get_dialog_id_to_role_name_hash_mapping()

    # Get localized role names for fallbacks
    localized_roles = localization.get_localized_role_names(data_repo.language)

    def _get_role_name_by_text_map_hash(
        dialog_item: types.TalkDialogItem,
    ) -> str | None:
        dialog_id = dialog_item["id"]
        role_name_hash = dialog_item.get(
            "talkRoleNameTextMapHash"
        ) or dialog_id_to_role_hash.get(dialog_id)

        return (
            None
            if role_name_hash is None
            else text_map.get_optional(str(role_name_hash))
        )

    def _get_role_name_by_role(talk_role: types.TalkRole) -> str | None:
        role_type = talk_role.get("type")
        match role_type:
            case "TALK_ROLE_NPC":
                npc_id = talk_role.get("_id", talk_role.get("id"))
                return npc_id_to_name.get(npc_id)
            case "TALK_ROLE_PLAYER":
                return localized_roles.player
            case "TALK_ROLE_NEED_CLICK_BLACK_SCREEN" | "TALK_ROLE_BLACK_SCREEN":
                return localized_roles.black_screen
            case _:
                return None

    def _get_role_name(dialog_item: types.TalkDialogItem) -> str:
        talk_role = dialog_item["talkRole"]
        role_type = talk_role.get("type")

        by_role = _get_role_name_by_role(talk_role)
        by_name_hash = _get_role_name_by_text_map_hash(dialog_item)

        # If both are available, return one if they match or both otherwise.
        if (by_role is not None) and (by_name_hash is not None):
            if by_role == by_name_hash:
                return by_role
            else:
                return f"{by_role} ({by_name_hash})"

        return (
            by_name_hash or by_role or f"{localized_roles.unknown_role} ({role_type})"
        )

    # Process dialog items
    talk_texts = []
    for dialog_item in dialog_list:
        content_hash = str(dialog_item["talkContentTextMapHash"])
        talk_texts.append(
            types.TalkText(
                role=_get_role_name(dialog_item),
                message=text_map.get(content_hash, f"Missing text ({content_hash})"),
            )
        )

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

    quest_title = text_map.get(str(title_hash), f"Missing title ({title_hash})")

    # Process subQuests in order (maintaining quest progression sequence)
    subquest_talk_infos = []
    subquest_talk_ids = set()

    # Get subquests and sort by order field to maintain quest progression
    subquests = quest_data.get("subQuests", [])
    sorted_subquests = sorted(subquests, key=lambda x: x.get("order", 0))

    for subquest in sorted_subquests:
        sub_id = str(subquest["subId"])

        try:
            # Try to get talk info by sub_id as talk ID first
            talk_info = get_talk_info_by_id(sub_id, data_repo=data_repo)
            if talk_info.text:  # Only add if there's actual dialog content
                subquest_talk_infos.append(talk_info)
                subquest_talk_ids.add(sub_id)
        except Exception:
            # Skip talks that can't be loaded
            continue

    # Process talks to find non-subquest dialogs
    non_subquest_talk_infos = []

    for talk_item in quest_data.get("talks", []):
        talk_id_str = str(talk_item["id"])

        # Skip if this talk is already in subquest talks
        if talk_id_str in subquest_talk_ids:
            continue

        try:
            talk_info = get_talk_info_by_id(talk_id_str, data_repo=data_repo)
            non_subquest_talk_infos.append(talk_info)
        except Exception:
            # Skip talks that can't be loaded
            continue

    return types.QuestInfo(
        title=quest_title,
        talks=subquest_talk_infos,
        non_subquest_talks=non_subquest_talk_infos,
    )


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


def get_subtitle_info(
    subtitle_path: str, *, data_repo: repo.DataRepo
) -> types.SubtitleInfo:
    """Parse subtitle file and extract text lines."""
    subtitle_file_path = data_repo.agd_path / subtitle_path
    content = subtitle_file_path.read_text(encoding="utf-8")

    text_lines = []
    for line in content.strip().split("\n"):
        line = line.strip()
        # Skip empty lines, numbers, and timestamp lines
        if line and not line.isdigit() and "-->" not in line:
            text_lines.append(line)

    return types.SubtitleInfo(text_lines=text_lines)


def get_material_info(
    material_id_str: str, *, data_repo: repo.DataRepo
) -> types.MaterialInfo:
    """Get material information for a specific material ID."""

    # Load required data
    text_map = data_repo.load_text_map()
    material_tracker = data_repo.load_material_excel_config_data()

    # Get material data (this automatically tracks access)
    material = material_tracker.get(material_id_str)
    if material is None:
        raise ValueError(f"Material with ID {material_id_str} not found")

    # Get material name
    name_hash = str(material["nameTextMapHash"])
    name = text_map.get(name_hash, "Unknown Material")

    # Get material description
    desc_hash = str(material["descTextMapHash"])
    description = text_map.get(desc_hash, "No description available")

    return types.MaterialInfo(name=name, description=description)


def get_voiceline_info(
    avatar_id_str: str, *, data_repo: repo.DataRepo
) -> types.VoicelineInfo:
    """Get all voiceline information for a specific character."""
    avatar_id = int(avatar_id_str)

    # Load required data
    text_map = data_repo.load_text_map()
    avatar_data = data_repo.load_avatar_excel_config_data()
    fetters_data = data_repo.load_fetters_excel_config_data()

    # Find character name from avatar data
    character_name = "Unknown Character"
    for avatar in avatar_data:
        if avatar["id"] == avatar_id:
            name_hash = str(avatar["nameTextMapHash"])
            character_name = text_map.get(name_hash, "Unknown Character")
            break

    # Collect all voicelines for this character
    voicelines = {}
    for fetter in fetters_data:
        if fetter["avatarId"] == avatar_id:
            # Get voiceline title
            title_hash = str(fetter["voiceTitleTextMapHash"])
            title = text_map.get(title_hash, "Unknown Title")

            # Get voiceline content
            content_hash = str(fetter["voiceFileTextTextMapHash"])
            content = text_map.get(content_hash, "")

            if content:  # Only add if there's actual content
                voicelines[title] = content

    return types.VoicelineInfo(character_name=character_name, voicelines=voicelines)


def get_artifact_set_info(
    set_id: str, *, data_repo: repo.DataRepo
) -> types.ArtifactSetInfo:
    """Get artifact set information including all pieces and their stories."""
    # Load required data
    set_data = data_repo.load_reliquary_set_excel_config_data()
    reliquary_data = data_repo.load_reliquary_excel_config_data()
    text_map = data_repo.load_text_map()

    set_id_int = int(set_id)

    # Find the artifact set configuration
    set_config = None
    for set_entry in set_data:
        if set_entry["setId"] == set_id_int:
            set_config = set_entry
            break

    if not set_config:
        # Hard error if set configuration not found
        raise ValueError(f"Artifact set configuration not found for set ID: {set_id}")

    # Get artifact IDs from the set
    artifact_ids = set_config["containsList"]

    # Collect artifact information
    artifacts = list[types.ArtifactInfo]()
    for artifact_id in artifact_ids:
        # Find artifact configuration
        artifact_config = None
        for reliquary in reliquary_data:
            if reliquary["id"] == artifact_id:
                artifact_config = reliquary
                break

        if not artifact_config:
            # Hard error if artifact configuration not found
            raise ValueError(
                f"Artifact configuration not found for artifact ID: {artifact_id} in set {set_id}"
            )

        # Get artifact name and description from text map
        name_hash = str(artifact_config["nameTextMapHash"])
        name = text_map.get(name_hash, f"Unknown Artifact {artifact_id}")

        description = ""
        if "descTextMapHash" in artifact_config:
            desc_hash = str(artifact_config["descTextMapHash"])
            description = text_map.get(desc_hash, "")

        # Get artifact story from Readable files
        readables = data_repo.get_readables()
        # Determine piece number within the set (1-5)
        piece_num = artifact_ids.index(artifact_id) + 1
        story = readables.get_relic_story(set_id, piece_num) or ""

        # Create artifact info
        artifact_info = types.ArtifactInfo(
            name=name,
            description=description,
            story=story,
        )
        artifacts.append(artifact_info)

    # Use the first artifact's name prefix as set name, or derive from set ID
    return types.ArtifactSetInfo(
        set_name=artifacts[0].name, set_id=set_id, artifacts=artifacts
    )
