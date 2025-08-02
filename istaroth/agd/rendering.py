"""Rendering functions for converting AGD content to RAG-suitable text format."""

import re

from istaroth.agd import localization, text_utils, types


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


def render_talk(
    talk: types.TalkInfo, *, talk_id: str, language: localization.Language
) -> types.RenderedItem:
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
        filename = f"talk_{safe_title}_{talk_id}.txt"
    else:
        filename = f"talk_empty_{talk_id}.txt"

    # Format content as dialog with role labels
    content_lines = ["# Talk Dialog\n"]

    for talk_text in talk.text:
        if text_utils.should_skip_text(talk_text.message, language):
            continue

        content_lines.append(f"{talk_text.role}: {talk_text.message}")

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_quest(
    quest: types.QuestInfo, language: localization.Language
) -> types.RenderedItem:
    """Render quest information into RAG-suitable format."""
    # Generate filename based on quest title
    safe_title = re.sub(r"[^\w\s-]", "", quest.title[:50])
    safe_title = re.sub(r"\s+", "_", safe_title.strip())
    filename = f"quest_{safe_title}.txt"

    # Format content with quest title and all talks
    content_lines = [f"# {quest.title}\n"]

    # Render main quest progression talks (from subQuests)
    for i, talk in enumerate(quest.talks, 1):
        if len(quest.talks) > 1:  # Only add talk headers if there are multiple talks
            content_lines.append(f"\n## Talk {i}\n")

        for talk_text in talk.text:
            if text_utils.should_skip_text(talk_text.message, language):
                continue
            content_lines.append(f"{talk_text.role}: {talk_text.message}")

    # Render non-subquest talks in a separate section
    if quest.non_subquest_talks:
        content_lines.append("\n## Additional Conversations\n")
        content_lines.append("*Conversations not present as sub-quests.*\n")

        for i, talk in enumerate(quest.non_subquest_talks, 1):
            if len(quest.non_subquest_talks) > 1:
                content_lines.append(f"\n### Additional Talk {i}\n")

            for talk_text in talk.text:
                if text_utils.should_skip_text(talk_text.message, language):
                    continue
                content_lines.append(f"{talk_text.role}: {talk_text.message}")

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_character_story(story_info: types.CharacterStoryInfo) -> types.RenderedItem:
    """Render all character stories into RAG-suitable format."""
    # Generate filename based on character name with collision safeguards
    safe_name = re.sub(r"[^\w\s-]", "", story_info.character_name)
    safe_name = re.sub(r"\s+", "_", safe_name.strip())

    # Add character count for additional uniqueness
    story_count = len(story_info.stories)
    filename = f"character_story_{safe_name}.txt"

    # Format content with character name header and all stories
    content_lines = [f"# {story_info.character_name} - Character Stories\n"]
    content_lines.append(f"*{story_count} stories for this character*\n")

    for i, story in enumerate(story_info.stories, 1):
        content_lines.append(f"## {i}. {story.title}\n")
        content_lines.append(story.content)
        content_lines.append("")  # Add blank line between stories

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_subtitle(
    subtitle_info: types.SubtitleInfo, subtitle_path: str
) -> types.RenderedItem:
    """Render subtitle content into RAG-suitable format."""
    # Generate filename based on subtitle file name
    import pathlib

    path_obj = pathlib.Path(subtitle_path)
    safe_name = re.sub(r"[^\w\s-]", "", path_obj.stem)
    safe_name = re.sub(r"\s+", "_", safe_name.strip())
    filename = f"subtitle_{safe_name}.txt"

    # Format content with subtitle header and all text lines
    content_lines = [f"# Subtitle: {path_obj.stem}\n"]
    content_lines.extend(subtitle_info.text_lines)

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_material(
    material_info: types.MaterialInfo, *, material_id: str
) -> types.RenderedItem:
    """Render material content into RAG-suitable format."""
    # Generate filename based on material name
    safe_name = re.sub(r"[^\w\s-]", "", material_info.name)
    safe_name = re.sub(r"\s+", "_", safe_name.strip())
    filename = f"material_{safe_name}_{material_id}.txt"

    # Format content with material name header and description
    content_lines = [f"# {material_info.name}\n"]
    content_lines.append(material_info.description)

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_voiceline(voiceline_info: types.VoicelineInfo) -> types.RenderedItem:
    """Render voiceline content into RAG-suitable format."""
    # Generate filename based on character name
    safe_name = re.sub(r"[^\w\s-]", "", voiceline_info.character_name)
    safe_name = re.sub(r"\s+", "_", safe_name.strip())
    filename = f"voiceline_{safe_name}.txt"

    # Format content with character name header and all voicelines
    content_lines = [f"# {voiceline_info.character_name} Voicelines\n"]

    for title, content in voiceline_info.voicelines.items():
        content_lines.append(f"## {title}")
        content_lines.append(content)
        content_lines.append("")  # Empty line between voicelines

    rendered_content = "\n".join(content_lines).rstrip()

    return types.RenderedItem(filename=filename, content=rendered_content)
