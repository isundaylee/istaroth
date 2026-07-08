"""Artifact set processing and rendering."""

import pathlib

from istaroth import utils
from istaroth.agd import (
    first_seen,
    id_types,
    issues,
    processed_types,
    repo,
)
from istaroth.agd.renderables import readable as _readable
from istaroth.text import types as text_types


def _get_relic_story_by_story_id(
    story_id: id_types.StoryId, *, data_repo: repo.DataRepo
) -> str | None:
    """Resolve a reliquary piece's relic story from its storyId.

    Follows storyId -> DocumentExcelConfigData -> questIDList ->
    LocalizationExcelConfigData -> readable file, returning None when the piece
    has no story (storyId 0, no document, or no readable on disk).
    """
    if story_id == 0:
        return None

    if (doc_item := data_repo.load_document_excel_config_data().get(story_id)) is None:
        return None

    localization_ids = set(doc_item["questIDList"])
    language_short = data_repo.language_short
    readables = data_repo.build_readables_tracker()
    for entry in data_repo.load_localization_excel_config_data():
        if entry["id"] not in localization_ids:
            continue
        for path_value in entry.values():
            if not isinstance(path_value, str) or not path_value:
                continue
            path = pathlib.Path(path_value)
            if (
                path_value.endswith(f"_{language_short}")
                or language_short in path.parts
            ) and (content := readables.get_content(f"{path.name}.txt")) is not None:
                return content
    return None


def get_artifact_set_info(
    set_id: id_types.ArtifactSetId, *, data_repo: repo.DataRepo
) -> processed_types.ArtifactSetInfo | None:
    """Get artifact set info, or None if no piece has a story."""
    set_data = data_repo.load_reliquary_set_excel_config_data()
    reliquary_data = data_repo.load_reliquary_excel_config_data()
    text_map = data_repo.build_text_map_tracker()

    set_config = None
    for set_entry in set_data:
        if set_entry["setId"] == set_id:
            set_config = set_entry
            break

    if not set_config:
        raise ValueError(f"Artifact set configuration not found for set ID: {set_id}")

    artifact_ids = set_config["containsList"]

    artifacts = list[processed_types.ArtifactInfo]()
    for artifact_id in artifact_ids:
        artifact_config = None
        for reliquary in reliquary_data:
            if reliquary["id"] == artifact_id:
                artifact_config = reliquary
                break

        if not artifact_config:
            raise ValueError(
                f"Artifact configuration not found for artifact ID: {artifact_id} in set {set_id}"
            )

        name = text_map.get_required(artifact_config["nameTextMapHash"])

        description = text_map.get(artifact_config["descTextMapHash"], "")

        story = (
            _get_relic_story_by_story_id(
                artifact_config["storyId"], data_repo=data_repo
            )
            or ""
        )

        artifact_info = processed_types.ArtifactInfo(
            name=name,
            description=description,
            story=story,
        )
        artifacts.append(artifact_info)

    if not any(artifact.story or artifact.description for artifact in artifacts):
        return None

    affix_id = set_config["equipAffixId"]
    if (
        affix_name_hash := next(
            (
                affix["nameTextMapHash"]
                for affix in data_repo.load_equip_affix_excel_config_data()
                if affix["id"] == affix_id
            ),
            None,
        )
    ) is None:
        raise ValueError(f"Equip affix {affix_id} not found for set {set_id}")
    return processed_types.ArtifactSetInfo(
        set_name=text_map.get_required(affix_name_hash),
        set_id=set_id,
        artifacts=artifacts,
    )


def render_artifact_set(
    artifact_set_info: processed_types.ArtifactSetInfo,
    *,
    first_seen_index: first_seen.FirstSeenIndex,
) -> processed_types.RenderedItem:
    """Render artifact set content into RAG-suitable format."""
    safe_name = utils.make_safe_filename_part(artifact_set_info.set_name)
    filename = f"{artifact_set_info.set_id}_{safe_name}.txt"

    content_lines = [f"# {artifact_set_info.set_name}\n"]

    for i, artifact in enumerate(artifact_set_info.artifacts, 1):
        content_lines.append(f"## Piece {i}: {artifact.name}")
        content_lines.append("")
        if artifact.description:
            content_lines.append(f"Description: {artifact.description}")
        if artifact.story:
            content_lines.append("Story:")
            content_lines.append("")
            content_lines.append(artifact.story)
        content_lines.append("")

    rendered_content = "\n".join(content_lines).rstrip()

    min_version, max_version = first_seen_index.resolve(
        [
            first_seen.SourceId(
                first_seen.SourceDomain.ARTIFACT_SET, artifact_set_info.set_id
            )
        ]
    )
    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ARTIFACT_SET,
            title=artifact_set_info.set_name,
            id=artifact_set_info.set_id,
            relative_path=f"{text_types.TextCategory.AGD_ARTIFACT_SET.value}/{filename}",
            min_version=min_version,
            max_version=max_version,
        ),
        content=rendered_content,
    )
