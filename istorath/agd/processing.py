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
