"""Shared loader + Readables/Wings/Costumes processing and rendering."""

import pathlib

from istaroth import text_cleanup, utils
from istaroth.agd import (
    id_types,
    issues,
    localization,
    processed_types,
    repo,
    text_utils,
)
from istaroth.text import types as text_types


def get_readable_metadata(
    readable_path: str, *, data_repo: repo.DataRepo
) -> processed_types.ReadableMetadata:
    """Retrieve metadata for a readable file."""
    language_short = data_repo.language_short
    readable_stem = pathlib.Path(readable_path).stem
    readable_id = readable_stem.removesuffix(f"_{language_short}")

    if (
        localization_id := data_repo.build_readable_stem_to_localization_id().get(
            readable_stem
        )
    ) is None:
        raise ValueError(f"Localization ID not found for readable: {readable_id}")

    title_hash = data_repo.build_localization_id_to_title_hash().get(localization_id)
    title = (
        None
        if title_hash is None
        else data_repo.load_text_map().get_optional(title_hash)
    )
    if title is None:
        issues.record(issues.IssueType.MISSING_READABLE_TITLE, readable_id)
        title = "Unknown Title"

    return processed_types.ReadableMetadata(
        localization_id=localization_id, title=title
    )


def load_readable(
    readable_path: str, *, data_repo: repo.DataRepo
) -> tuple[str, processed_types.ReadableMetadata] | None:
    """Read and clean a readable's content and metadata.

    Returns None for empty/placeholder/dev-test readables (matching the per-file
    skip rules) so callers can drop them; raises if the file itself is missing.
    Reading the content marks it accessed in the readables tracker.
    """
    readables = data_repo.get_readables()
    if (content := readables.get_content(pathlib.Path(readable_path).name)) is None:
        raise FileNotFoundError(f"Readable not found: {readable_path}")
    content = text_cleanup.clean_text_markers(content, data_repo.language)

    if text_utils.should_skip_readable_content(content, data_repo.language):
        return None

    metadata = get_readable_metadata(readable_path, data_repo=data_repo)
    if text_utils.should_skip_text(metadata.title, data_repo.language):
        return None

    return content, metadata


def render_readable(
    content: str, metadata: processed_types.ReadableMetadata
) -> processed_types.RenderedItem:
    """Render readable content into RAG-suitable format."""
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"{metadata.localization_id}_{safe_title}.txt"
    rendered_content = f"# {metadata.title}\n\n{content}"

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_READABLE,
            title=metadata.title,
            id=metadata.localization_id,
            relative_path=f"{text_types.TextCategory.AGD_READABLE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_wings(
    content: str, metadata: processed_types.ReadableMetadata
) -> processed_types.RenderedItem:
    """Render wings readable content into RAG-suitable format."""
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"{metadata.localization_id}_{safe_title}.txt"
    rendered_content = f"# {metadata.title}\n\n{content}"

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_WINGS,
            title=metadata.title,
            id=metadata.localization_id,
            relative_path=f"{text_types.TextCategory.AGD_WINGS.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_costume(
    content: str, metadata: processed_types.ReadableMetadata
) -> processed_types.RenderedItem:
    """Render costume readable content into RAG-suitable format."""
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"{metadata.localization_id}_{safe_title}.txt"
    rendered_content = f"# {metadata.title}\n\n{content}"

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_COSTUME,
            title=metadata.title,
            id=metadata.localization_id,
            relative_path=f"{text_types.TextCategory.AGD_COSTUME.value}/{filename}",
        ),
        content=rendered_content,
    )
