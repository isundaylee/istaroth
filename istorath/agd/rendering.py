"""Rendering functions for converting AGD content to RAG-suitable text format."""

import re

from istorath.agd import types


def render_readable(
    content: str, metadata: types.ReadableMetadata
) -> types.RenderedItem:
    """Render readable content into RAG-suitable format."""
    # Generate filename based on title
    # Remove special characters and replace spaces with underscores
    safe_title = re.sub(r"[^\w\s-]", "", metadata.title)
    safe_title = re.sub(r"\s+", "_", safe_title.strip())
    filename = f"readable_{safe_title}.txt"

    # Format content with title header
    rendered_content = f"# {metadata.title}\n\n{content}"

    return types.RenderedItem(filename=filename, content=rendered_content)
