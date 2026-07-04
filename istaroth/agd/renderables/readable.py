"""Shared loader + Readables/Wings/Costumes processing and rendering."""

import pathlib

from istaroth import utils
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
        localization_id := data_repo.build_readable_stem_to_localization_id_mapping().get(
            readable_stem
        )
    ) is None:
        raise ValueError(f"Localization ID not found for readable: {readable_id}")

    title_hash = data_repo.build_localization_id_to_title_hash_mapping().get(
        localization_id
    )
    title = (
        None
        if title_hash is None
        else data_repo.build_text_map_tracker().get_optional(title_hash)
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
    readables = data_repo.build_readables_tracker()
    if (content := readables.get_content(pathlib.Path(readable_path).name)) is None:
        raise FileNotFoundError(f"Readable not found: {readable_path}")
    content = data_repo.build_text_map_tracker().clean_text(content)

    if text_utils.should_skip_readable_content(content, data_repo.language):
        return None

    metadata = get_readable_metadata(readable_path, data_repo=data_repo)
    if text_utils.should_skip_text(metadata.title, data_repo.language):
        return None

    return content, metadata


def render_readable_like(
    content: str,
    metadata: processed_types.ReadableMetadata,
    *,
    category: text_types.TextCategory,
) -> processed_types.RenderedItem:
    """Render readable-style content (readable/wings/costume) into RAG-suitable format."""
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"{metadata.localization_id}_{safe_title}.txt"

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=category,
            title=metadata.title,
            id=metadata.localization_id,
            relative_path=f"{category.value}/{filename}",
        ),
        content=f"# {metadata.title}\n\n{content}",
    )
