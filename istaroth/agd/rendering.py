"""Rendering functions for converting AGD content to RAG-suitable text format."""

import pathlib

from istaroth import utils
from istaroth.agd import localization, talk_parsing, text_utils, types


def _extract_talk_type_from_path(talk_file_path: str) -> str:
    """Extract talk type from file path.

    Args:
        talk_file_path: Relative path like "BinOutput/Talk/Quest/123.json" or "BinOutput/Talk/456.json"

    Returns:
        Talk type: "quest", "npc", "root", etc.
    """
    path = pathlib.Path(talk_file_path)
    assert path.parts[0] == "BinOutput"
    assert path.parts[1] == "Talk"

    # Expected format: BinOutput/Talk/[subdir]/file.json or BinOutput/Talk/file.json
    if len(path.parts) >= 4:
        # File is in a subdirectory: BinOutput/Talk/Quest/123.json -> "quest"
        return path.parts[2].lower()
    elif len(path.parts) == 3:
        # File is in root Talk directory: BinOutput/Talk/123.json -> "root"
        return "root"
    else:
        raise ValueError(f"Invalid talk file path {talk_file_path}")


def render_readable(
    content: str, metadata: types.ReadableMetadata
) -> types.RenderedItem:
    """Render readable content into RAG-suitable format."""
    # Generate filename based on title
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"readable_{safe_title}_{metadata.localization_id}.txt"

    # Format content with title header
    rendered_content = f"# {metadata.title}\n\n{content}"

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_talk(
    talk: types.TalkInfo,
    *,
    talk_id: str,
    talk_file_path: str | None = None,
    language: localization.Language,
) -> types.RenderedItem:
    """Render talk dialog into RAG-suitable format."""
    # Extract talk type from file path if provided
    talk_type = (
        _extract_talk_type_from_path(talk_file_path) if talk_file_path else "unknown"
    )

    # Generate filename - use first few dialog lines to create a meaningful name
    if talk.text:
        # Use first non-empty message for filename
        first_message = next(
            (text.message for text in talk.text if text.message.strip()),
            "unknown_talk",
        )
        # Take first 50 characters and clean for filename
        safe_title = utils.make_safe_filename_part(first_message)
        filename = f"talk_{talk_type}_{safe_title}_{talk_id}.txt"
    else:
        filename = f"talk_{talk_type}_empty_{talk_id}.txt"

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
    safe_title = utils.make_safe_filename_part(quest.title)
    filename = f"quest_{safe_title}_{quest.quest_id}.txt"

    # Format content with chapter title (if available) and quest title
    content_lines = []
    if quest.chapter_title:
        content_lines.append(f"(Quest is part of chapter: {quest.chapter_title})\n")
    content_lines.append(f"# {quest.title}\n")

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
    safe_name = utils.make_safe_filename_part(story_info.character_name)

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
    safe_name = utils.make_safe_filename_part(path_obj.stem)
    filename = f"subtitle_{safe_name}.txt"

    # Format content with subtitle header and all text lines
    content_lines = [f"# Subtitle: {path_obj.stem}\n"]
    content_lines.extend(subtitle_info.text_lines)

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_material(material_info: types.MaterialInfo) -> types.RenderedItem:
    """Render material content into RAG-suitable format."""
    # Generate filename based on material name
    safe_name = utils.make_safe_filename_part(material_info.name)
    filename = f"material_{safe_name}_{material_info.material_id}.txt"

    # Format content with material name header and description
    content_lines = [f"# {material_info.name}\n"]
    content_lines.append(material_info.description)

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_materials_by_type(
    material_type: str, materials: list[types.MaterialInfo]
) -> types.RenderedItem:
    """Render multiple materials of the same type into a single RAG-suitable format file."""
    # Generate filename based on material type
    safe_type = utils.make_safe_filename_part(material_type)
    filename = f"material_type_{safe_type}.txt"

    # Format content with material type header and all materials
    content_lines = [f"# Materials: {material_type}\n"]

    # Sort materials by ID for deterministic output
    sorted_materials = sorted(materials, key=lambda x: int(x.material_id))

    for material_info in sorted_materials:
        content_lines.append(f"## {material_info.name}")
        content_lines.append("")
        content_lines.append(material_info.description)
        content_lines.append("")

    rendered_content = "\n".join(content_lines).rstrip()

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_voiceline(voiceline_info: types.VoicelineInfo) -> types.RenderedItem:
    """Render voiceline content into RAG-suitable format."""
    # Generate filename based on character name
    safe_name = utils.make_safe_filename_part(voiceline_info.character_name)
    filename = f"voiceline_{safe_name}.txt"

    # Format content with character name header and all voicelines
    content_lines = [f"# {voiceline_info.character_name} Voicelines\n"]

    for title, content in voiceline_info.voicelines.items():
        content_lines.append(f"## {title}")
        content_lines.append(content)
        content_lines.append("")  # Empty line between voicelines

    rendered_content = "\n".join(content_lines).rstrip()

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_artifact_set(artifact_set_info: types.ArtifactSetInfo) -> types.RenderedItem:
    """Render artifact set content into RAG-suitable format."""
    # Generate filename based on set name and ID
    safe_name = utils.make_safe_filename_part(artifact_set_info.set_name)
    filename = f"artifact_set_{safe_name}_{artifact_set_info.set_id}.txt"

    # Format content with set name header and all artifact pieces
    content_lines = [f"# {artifact_set_info.set_name}\n"]

    for i, artifact in enumerate(artifact_set_info.artifacts, 1):
        # Add artifact piece header
        content_lines.append(f"## Piece {i}: {artifact.name}")
        content_lines.append("")

        # Add description if available
        if artifact.description:
            content_lines.append(f"Description: {artifact.description}")

        # Add story if available
        if artifact.story:
            content_lines.append("Story:")
            content_lines.append("")
            content_lines.append(artifact.story)

        content_lines.append("")  # Empty line between pieces

    rendered_content = "\n".join(content_lines).rstrip()

    return types.RenderedItem(filename=filename, content=rendered_content)


def render_talk_group(
    talk_group_type: talk_parsing.TalkGroupType,
    talk_group_id: str,
    talk_group_info: types.TalkGroupInfo,
    language: localization.Language,
) -> types.RenderedItem:
    """Render multiple talks from an activity group into a single file."""
    # Generate filename based on activity ID
    filename = f"talk_group_{talk_group_type}_{talk_group_id}.txt"

    # Format content with activity group header and all talks
    content_lines = [f"# Talk Group: {talk_group_type} - {talk_group_id}\n"]

    for i, (talk, next_talks) in enumerate(talk_group_info.talks):
        content_lines.append(f"## Talk {i}\n")

        # Add talk dialog
        for talk_text in talk.text:
            if text_utils.should_skip_text(talk_text.message, language):
                continue
            content_lines.append(f"{talk_text.role}: {talk_text.message}")
        content_lines.append("")  # Empty line between talks

        # Add followup talks
        for j, next_talk in enumerate(next_talks):
            content_lines.append(f"### Talk {i} related talk {j}\n")
            # Add talk dialog
            for next_talk_text in next_talk.text:
                if text_utils.should_skip_text(next_talk_text.message, language):
                    continue
                content_lines.append(f"{next_talk_text.role}: {next_talk_text.message}")
            content_lines.append("")  # Empty line between talks

    rendered_content = "\n".join(content_lines).rstrip()

    return types.RenderedItem(filename=filename, content=rendered_content)
