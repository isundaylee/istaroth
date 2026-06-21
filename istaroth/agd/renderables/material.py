"""Material processing and rendering."""

import hashlib

from istaroth import utils
from istaroth.agd import (
    id_types,
    issues,
    processed_types,
    repo,
    text_utils,
)
from istaroth.text import types as text_types


def get_material_info(
    material_id: id_types.MaterialId, *, data_repo: repo.DataRepo
) -> processed_types.MaterialInfo:
    """Get material information for a specific material ID."""
    text_map = data_repo.load_text_map()
    material_tracker = data_repo.load_material_excel_config_data()

    material = material_tracker.get(material_id)
    if material is None:
        raise ValueError(f"Material with ID {material_id} not found")

    name_hash = material["nameTextMapHash"]
    if (name := text_map.get_optional(name_hash)) is None:
        issues.record(issues.IssueType.MISSING_MATERIAL_NAME, str(name_hash))
        name = "Unknown Material"

    desc_hash = material["descTextMapHash"]
    if (description := text_map.get_optional(desc_hash)) is None:
        issues.record(issues.IssueType.MISSING_MATERIAL_DESC, str(desc_hash))
        description = "No description available"

    return processed_types.MaterialInfo(
        material_id=material_id, name=name, description=description
    )


def _humanize_material_type(material_type: str) -> str:
    """Turn a raw MaterialType enum into a readable title."""
    return material_type.removeprefix("MATERIAL_").replace("_", " ").title()


def render_materials_by_type(
    material_type: str, materials: list[processed_types.MaterialInfo]
) -> processed_types.RenderedItem:
    """Render multiple materials of the same type into a single RAG-suitable file."""
    material_type_id = int(
        hashlib.sha256(material_type.encode("utf-8")).hexdigest()[:12], base=16
    )

    safe_type = utils.make_safe_filename_part(material_type)
    filename = f"{material_type_id}_{safe_type}.txt"

    material_type_name = _humanize_material_type(material_type)

    content_lines = [f"# Materials: {material_type_name}\n"]

    sorted_materials = sorted(materials, key=lambda x: x.material_id)

    for material_info in sorted_materials:
        content_lines.append(f"## {material_info.name}")
        content_lines.append("")
        content_lines.append(material_info.description)
        content_lines.append("")

    rendered_content = "\n".join(content_lines).rstrip()

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_MATERIAL_TYPE,
            title=material_type_name,
            id=material_type_id,
            relative_path=f"{text_types.TextCategory.AGD_MATERIAL_TYPE.value}/{filename}",
        ),
        content=rendered_content,
    )
