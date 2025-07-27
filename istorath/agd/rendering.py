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


def render_talk(talk: types.TalkInfo) -> types.RenderedItem:
    """Render talk dialog into RAG-suitable format."""
    # Generate filename - use first few dialog lines to create a meaningful name
    if talk.text:
        # Use first non-empty message for filename
        first_message = next(
            (text.message for text in talk.text if text.message.strip()),
            "unknown_talk",
        )
        # Take first 50 characters and clean for filename
        safe_title = re.sub(r"[^\w\s-]", "", first_message[:50])
        safe_title = re.sub(r"\s+", "_", safe_title.strip())
        filename = f"talk_{safe_title}.txt"
    else:
        filename = "talk_empty.txt"

    # Format content as dialog with role labels
    content_lines = ["# Talk Dialog\n"]

    for talk_text in talk.text:
        content_lines.append(f"{talk_text.role}: {talk_text.message}")

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_quest(quest: types.QuestInfo) -> types.RenderedItem:
    """Render quest information into RAG-suitable format."""
    # Generate filename based on first talk's content
    if quest.talks and quest.talks[0].text:
        first_message = next(
            (text.message for text in quest.talks[0].text if text.message.strip()),
            "unknown_quest",
        )
        # Take first 50 characters and clean for filename
        safe_title = re.sub(r"[^\w\s-]", "", first_message[:50])
        safe_title = re.sub(r"\s+", "_", safe_title.strip())
        filename = f"quest_{safe_title}.txt"
    else:
        filename = "quest_empty.txt"

    # Format content with quest header and all talks
    content_lines = ["# Quest Dialog\n"]

    for i, talk in enumerate(quest.talks, 1):
        if len(quest.talks) > 1:  # Only add talk headers if there are multiple talks
            content_lines.append(f"\n## Talk {i}\n")

        for talk_text in talk.text:
            content_lines.append(f"{talk_text.role}: {talk_text.message}")

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)
