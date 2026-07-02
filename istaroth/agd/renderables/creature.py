"""Creature (living-beings archive) processing and rendering."""

import hashlib

from istaroth import utils
from istaroth.agd import (
    agd_types,
    id_types,
    issues,
    localization,
    processed_types,
    repo,
)
from istaroth.text import types as text_types


def _get_unique_monster_special_name_hash(
    special_names: agd_types.MonsterSpecialNameExcelConfigData,
    special_name_lab_id: id_types.MonsterSpecialNameLabId,
) -> id_types.TextMapHash | None:
    matches = [
        entry
        for entry in special_names
        if entry["specialNameLabID"] == special_name_lab_id
    ]
    if not matches:
        raise ValueError(f"Missing monster special-name lab ID {special_name_lab_id}")
    return matches[0]["specialNameTextMapHash"] if len(matches) == 1 else None


def _get_creature_info(
    codex_id: id_types.AnimalCodexId, *, data_repo: repo.DataRepo
) -> processed_types.CreatureInfo:
    """Get a living-beings archive entry (monster or wildlife) by its codex id."""
    entry = data_repo.load_animal_codex_excel_config_data()[codex_id]
    text_map = data_repo.build_text_map_tracker()

    if (description := text_map.get_optional(entry["descTextMapHash"])) is None:
        raise ValueError(f"Missing description for creature codex {codex_id}")

    describe_id = entry["describeId"]
    title: str | None = None
    special_name: str | None = None
    match entry["type"]:
        case "CODEX_MONSTER":
            describe = data_repo.load_monster_describe_excel_config_data()[describe_id]
            title = text_map.get_optional(
                data_repo.load_monster_title_excel_config_data()[describe["titleID"]][
                    "titleNameTextMapHash"
                ]
            )
            special_name_hash = _get_unique_monster_special_name_hash(
                data_repo.load_monster_special_name_excel_config_data(),
                describe["specialNameLabID"],
            )
            special_name = (
                None
                if special_name_hash is None
                else text_map.get_optional(special_name_hash)
            )
            name_hash = describe["nameTextMapHash"]
        case "CODEX_ANIMAL":
            name_hash = data_repo.load_animal_describe_excel_config_data()[describe_id][
                "nameTextMapHash"
            ]
        case other:
            raise ValueError(f"Unknown codex type {other!r} for creature {codex_id}")

    if (name := text_map.get_optional(name_hash)) is None:
        raise ValueError(f"Missing name for creature codex {codex_id}")

    return processed_types.CreatureInfo(
        codex_id=codex_id,
        name=name,
        special_name=special_name if special_name != name else None,
        title=title if title not in (name, special_name) else None,
        description=description,
    )


def get_creature_group_info(
    subtype: str, *, data_repo: repo.DataRepo
) -> processed_types.CreatureGroupInfo:
    """Get all creatures in one codex subType group, in archive order."""
    entries = sorted(
        (
            entry
            for entry in data_repo.load_animal_codex_excel_config_data().values()
            if entry["subType"] == subtype and not entry["isDisuse"]
        ),
        key=lambda entry: (entry["sortOrder"], entry["id"]),
    )
    if not entries:
        raise ValueError(f"No creatures found for codex subType {subtype!r}")

    return processed_types.CreatureGroupInfo(
        subtype=subtype,
        type_label=localization.get_creature_type_label(
            entries[0]["type"], language=data_repo.language
        ),
        subtype_label=localization.get_creature_subtype_label(
            subtype, language=data_repo.language
        ),
        creatures=[
            _get_creature_info(entry["id"], data_repo=data_repo) for entry in entries
        ],
    )


def render_creature_group(
    group_info: processed_types.CreatureGroupInfo,
) -> processed_types.RenderedItem:
    """Render one codex subType group of creatures into a single RAG-suitable file."""
    group_id = int(
        hashlib.sha256(group_info.subtype.encode("utf-8")).hexdigest()[:12], base=16
    )
    filename = f"{group_id}_{group_info.subtype}.txt"
    title = group_info.subtype_label

    content_lines = [f"# {title} ({group_info.type_label})\n"]
    for creature in group_info.creatures:
        content_lines.append(f"## {creature.name}")
        if creature.special_name is not None:
            content_lines.append(creature.special_name)
        if creature.title is not None:
            content_lines.append(f"Also known as: {creature.title}")
        content_lines.append("")
        content_lines.append(creature.description)
        content_lines.append("")

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_CREATURE,
            title=title,
            id=group_id,
            relative_path=f"{text_types.TextCategory.AGD_CREATURE.value}/{filename}",
        ),
        content="\n".join(content_lines).rstrip(),
    )
