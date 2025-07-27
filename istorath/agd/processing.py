"""Processing functions for AGD data."""

import pathlib

from istorath.agd import repo, types


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
    text_map = data_repo.load_text_map("CHS")

    # Step 1: Find localization ID for the readable
    for entry in localization_data:
        if readable_id in entry["defaultPath"]:
            localization_id = entry["id"]
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
    title = text_map.get(title_hash)

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
    text_map = data_repo.load_text_map("CHS")

    # Create NPC ID to name mapping
    npc_id_to_name = {}
    for npc in npc_data:
        npc_id = str(npc["id"])
        name_hash = str(npc["nameTextMapHash"])
        if name_hash in text_map:
            npc_id_to_name[npc_id] = text_map[name_hash]

    # Process dialog items
    talk_texts = []
    for dialog_item in dialog_list:
        talk_role = dialog_item["talkRole"]
        content_hash = str(dialog_item["talkContentTextMapHash"])

        # Determine role name
        if talk_role["type"] == "TALK_ROLE_NPC":
            npc_id = talk_role["_id"]
            role = npc_id_to_name.get(npc_id, f"Unknown NPC ({npc_id})")
        elif talk_role["type"] == "TALK_ROLE_PLAYER":
            role = "旅行者"
        elif talk_role["type"] == "TALK_ROLE_NEED_CLICK_BLACK_SCREEN":
            role = "黑屏文本"
        else:
            role = f"Unknown Role ({talk_role['type']})"

        # Get message text
        message = text_map.get(content_hash, f"Missing text ({content_hash})")

        talk_texts.append(types.TalkText(role=role, message=message))

    return types.TalkInfo(text=talk_texts)


def get_quest_info(quest_path: str, *, data_repo: repo.DataRepo) -> types.QuestInfo:
    """Retrieve quest information from quest file."""
    # Load quest data
    quest_data = data_repo.load_quest_data(quest_path)

    # Process each talk in the quest
    talk_infos = []
    for talk_item in quest_data["talks"]:
        init_dialog_id = talk_item["initDialog"]

        # Convert dialog ID to talk file path
        # Dialog IDs like 740780101 map to BinOutput/Talk/Quest/7407801.json
        # Take first 7 digits as the talk file ID
        talk_file_id = str(init_dialog_id)[:7]
        talk_file_path = f"BinOutput/Talk/Quest/{talk_file_id}.json"

        try:
            # Get the talk info for this dialog
            talk_info = get_talk_info(talk_file_path, data_repo=data_repo)
            talk_infos.append(talk_info)
        except Exception:
            # Skip talks that can't be loaded (file might not exist)
            continue

    return types.QuestInfo(talks=talk_infos)
