"""Subtitle processing and rendering."""

import hashlib
import pathlib

from istaroth import text_cleanup, utils
from istaroth.agd import (
    processed_types,
    repo,
)
from istaroth.text import types as text_types


def get_subtitle_info(
    subtitle_path: str, *, data_repo: repo.DataRepo
) -> processed_types.SubtitleInfo:
    """Parse subtitle file and extract text lines."""
    subtitle_file_path = data_repo.agd_path / subtitle_path
    content = subtitle_file_path.read_text(encoding="utf-8")

    text_lines = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if line and not line.isdigit() and "-->" not in line:
            text_lines.append(text_cleanup.clean_text_markers(line, data_repo.language))

    return processed_types.SubtitleInfo(text_lines=text_lines)


def render_subtitle(
    subtitle_info: processed_types.SubtitleInfo, subtitle_path: str
) -> processed_types.RenderedItem:
    """Render subtitle content into RAG-suitable format."""
    subtitle_id = int(
        hashlib.sha256(subtitle_path.encode("utf-8")).hexdigest()[:12], base=16
    )

    path_obj = pathlib.Path(subtitle_path)
    safe_name = utils.make_safe_filename_part(path_obj.stem)
    filename = f"{subtitle_id}_{safe_name}.txt"

    content_lines = [f"# Subtitle: {path_obj.stem}\n"]
    content_lines.extend(subtitle_info.text_lines)

    rendered_content = "\n".join(content_lines)

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_SUBTITLE,
            title=path_obj.stem,
            id=subtitle_id,
            relative_path=f"{text_types.TextCategory.AGD_SUBTITLE.value}/{filename}",
        ),
        content=rendered_content,
    )
