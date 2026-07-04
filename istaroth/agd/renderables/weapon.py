"""Weapon story processing and rendering."""

from istaroth import utils
from istaroth.agd import (
    id_types,
    processed_types,
    repo,
)
from istaroth.agd.renderables import readable as _readable
from istaroth.text import types as text_types


def get_weapon_info(
    weapon_id: str, *, data_repo: repo.DataRepo
) -> processed_types.WeaponInfo | None:
    """Assemble a weapon's story document from its authoritative weapon config.

    Follows weapon storyId -> DocumentExcelConfigData -> ordered page localization
    ids -> readable files, joining the pages into one document. Returns None when
    the weapon has no story (storyId 0, no document, or no page has on-disk
    content), mirroring the artifact-set discovery model. Reading each page also
    marks it accessed, keeping rendered pages out of the generic Readables
    catch-all; the unrendered base/placeholder files it leaves behind are dropped
    there by the empty/placeholder content skip.
    """
    text_map = data_repo.build_text_map_tracker()
    readables = data_repo.build_readables_tracker()

    if (
        weapon := data_repo.load_weapon_excel_config_data().get(int(weapon_id))
    ) is None:
        raise ValueError(f"Weapon configuration not found for weapon ID: {weapon_id}")

    if (story_id := weapon["storyId"]) == 0:
        return None

    if (doc_item := data_repo.load_document_excel_config_data().get(story_id)) is None:
        return None

    ordered_loc_ids = dict.fromkeys(
        doc_item["questContentLocalizedId"]
        + doc_item["questIDList"]
        + doc_item.get("CUSTOM_addlLocalID", [])
    )
    readable_paths = data_repo.build_localization_id_to_readable_path_mapping()
    story_pages = [
        content
        for loc_id in ordered_loc_ids
        if (path := readable_paths.get(loc_id)) is not None
        and (content := readables.get_content(path))
    ]
    if not story_pages:
        return None

    if (name := text_map.get_optional(weapon["nameTextMapHash"])) is None:
        raise ValueError(f"Missing name for weapon ID {weapon_id}")

    return processed_types.WeaponInfo(
        weapon_id=weapon_id,
        name=name,
        description=text_map.get(weapon["descTextMapHash"], ""),
        story_pages=story_pages,
    )


def render_weapon(
    weapon_info: processed_types.WeaponInfo,
) -> processed_types.RenderedItem:
    """Render a weapon's assembled story document into RAG-suitable format."""
    safe_name = utils.make_safe_filename_part(weapon_info.name)
    filename = f"{weapon_info.weapon_id}_{safe_name}.txt"

    content_lines = [f"# {weapon_info.name}\n"]
    if weapon_info.description:
        content_lines.append(f"{weapon_info.description}\n")
    content_lines.append("\n\n---\n\n".join(weapon_info.story_pages))

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_WEAPON,
            title=weapon_info.name,
            id=int(weapon_info.weapon_id),
            relative_path=f"{text_types.TextCategory.AGD_WEAPON.value}/{filename}",
        ),
        content="\n".join(content_lines),
    )
