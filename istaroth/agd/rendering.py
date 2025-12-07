"""Rendering functions for converting AGD content to RAG-suitable text format."""

import hashlib
import pathlib
from collections import defaultdict

from istaroth import utils
from istaroth.agd import localization, talk_parsing, text_utils, types
from istaroth.text import types as text_types


class _TalkTextGraph:
    """Graph structure for talk dialog items with nextDialogs relationships."""

    def __init__(self, talk: types.TalkInfo) -> None:
        """Build graph structure from talk dialog items."""
        self.dialog_id_to_text: dict[int, types.TalkText] = {}
        self.graph: dict[int, list[int]] = defaultdict(list)
        self.incoming_edges: dict[int, int] = defaultdict(int)
        self.outgoing_edges: dict[int, int] = defaultdict(int)

        for talk_text in talk.text:
            dialog_id = talk_text.dialog_id
            self.dialog_id_to_text[dialog_id] = talk_text

            for next_id in talk_text.next_dialog_ids:
                self.graph[dialog_id].append(next_id)
                self.incoming_edges[next_id] += 1
                self.outgoing_edges[dialog_id] += 1

        self.graph = dict(self.graph)
        self.incoming_edges = dict(self.incoming_edges)
        self.outgoing_edges = dict(self.outgoing_edges)

    def find_entrypoint(self, talk: types.TalkInfo) -> int:
        """Find entry points (dialogs with no incoming edges or first dialog)."""
        entrypoints = []

        # Find dialogs with no incoming edges
        all_dialog_ids = {text.dialog_id for text in talk.text}
        for dialog_id in all_dialog_ids:
            if self.incoming_edges.get(dialog_id, 0) == 0:
                entrypoints.append(dialog_id)

        assert (
            len(entrypoints) == 1
        ), f"Expected exactly one entrypoint, found {len(entrypoints)}: {entrypoints}"
        return entrypoints[0]


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
    filename = f"{metadata.localization_id}_{safe_title}.txt"

    # Format content with title header
    rendered_content = f"# {metadata.title}\n\n{content}"

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_READABLE,
            title=metadata.title,
            id=metadata.localization_id,
            relative_path=f"{text_types.TextCategory.AGD_READABLE.value}/{filename}",
        ),
        content=rendered_content,
    )


def _render_dialog_line(
    talk_text: types.TalkText, language: localization.Language
) -> str | None:
    """Render a single dialog line if it should not be skipped.

    Returns:
        Formatted line string or None if dialog should be skipped
    """
    if text_utils.should_skip_text(talk_text.message, language):
        return None
    return f"{talk_text.role}: {talk_text.message}"


def _process_branch(
    branch_start_id: int,
    graph: _TalkTextGraph,
    rendered: set[int],
    language: localization.Language,
) -> tuple[list[str], int | None]:
    """Process a single branch until convergence point.

    Follows the branch from branch_start_id, rendering all dialogs until hitting
    a convergence point (dialog with 2+ incoming edges). Asserts that the branch
    doesn't further branch.

    Args:
        branch_start_id: Starting dialog ID for this branch
        graph: TalkTextGraph object containing graph structure
        rendered: Set of already rendered dialog IDs
        language: Language for filtering

    Returns:
        Tuple of (unindented rendered lines, convergence_point_id or None if end of path)
    """
    lines: list[str] = []
    current_id = branch_start_id

    while True:
        assert current_id not in rendered, f"Dialog {current_id} already rendered"

        # Check if this is a convergence point
        if graph.incoming_edges.get(current_id, 0) > 1:
            return lines, current_id

        rendered.add(current_id)

        if line := _render_dialog_line(graph.dialog_id_to_text[current_id], language):
            lines.append(line)

        # Get next dialogs
        next_dialog_ids = graph.graph.get(current_id, [])

        if not next_dialog_ids:
            # End of path
            return lines, None

        # Assert no further branching in this branch
        assert (
            len(next_dialog_ids) == 1
        ), f"Branch further branches at dialog {current_id}: {next_dialog_ids}"

        current_id = next_dialog_ids[0]


def _render_dialog_with_branches(
    dialog_id: int,
    graph: _TalkTextGraph,
    rendered: set[int],
    language: localization.Language,
) -> list[str]:
    """Render dialog following single paths until branching, then process branches.

    Args:
        dialog_id: Current dialog ID to render
        graph: TalkTextGraph object containing graph structure
        visited: Set of visited dialog IDs in current path (for cycle detection)
        rendered: Set of already rendered dialog IDs
        language: Language for filtering
    """
    lines: list[str] = []
    current_id = dialog_id

    # Follow single next dialogues until we hit multiple next dialogues
    while True:
        assert current_id not in rendered, f"Dialog {current_id} already rendered"

        rendered.add(current_id)
        if line := _render_dialog_line(graph.dialog_id_to_text[current_id], language):
            lines.append(line)

        # Get next dialogs
        next_dialog_ids = graph.graph.get(current_id, [])

        # Case 1: we're done
        if not next_dialog_ids:
            break

        # Case 2: we have a single next dialog
        if len(next_dialog_ids) == 1:
            current_id = next_dialog_ids[0]
            continue

        # Case 3: we have multiple next dialogs
        # Process each branch until (but not including) a convergence point
        conv_points: list[int | None] = []

        for i, branch_start_id in enumerate(next_dialog_ids, 1):
            option_label = f"Option {i}:"
            option_indent = "    "
            lines.append(f"{option_indent}{option_label}")

            branch_lines, conv_point = _process_branch(
                branch_start_id, graph, rendered, language
            )
            branch_indent = "    " * 2
            lines.extend(
                f"{branch_indent}{branch_line}" for branch_line in branch_lines
            )
            conv_points.append(conv_point)

        # Assert all convergence points match
        assert (
            len(set(conv_points)) <= 1
        ), f"Branches converge at different points: {conv_points}"

        # Continue from convergence point if it exists
        conv_point = next(iter(conv_points))
        if conv_point is None:
            break

        current_id = conv_point

    return lines


def render_talk(
    talk: types.TalkInfo,
    *,
    talk_id: str,
    talk_file_path: str | None = None,
    language: localization.Language,
) -> types.RenderedItem:
    """Render talk dialog into RAG-suitable format with branching support."""
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
        filename = f"{talk_id}_{safe_title}.txt"
        title = first_message[:100] if len(first_message) > 100 else first_message
    else:
        filename = f"{talk_id}_empty.txt"
        title = "Empty Talk"

    # Render content
    content_lines = ["# Talk Dialog\n"]

    # Build graph structure
    if talk.text:
        graph = _TalkTextGraph(talk)
        entrypoint = graph.find_entrypoint(talk)

        rendered: set[int] = set()
        lines = _render_dialog_with_branches(entrypoint, graph, rendered, language)
        content_lines.extend(lines)

        # Assert all dialogs were rendered (no orphaned dialogs)
        all_dialog_ids = {text.dialog_id for text in talk.text}
        orphaned_ids = all_dialog_ids - rendered
        assert (
            not orphaned_ids
        ), f"Found orphaned dialogs not reachable from entry point: {orphaned_ids}"

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_TALK,
            title=title,
            id=int(talk_id),
            relative_path=f"{text_types.TextCategory.AGD_TALK.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_quest(
    quest: types.QuestInfo, language: localization.Language
) -> types.RenderedItem:
    """Render quest information into RAG-suitable format."""
    # Generate filename based on quest title
    safe_title = utils.make_safe_filename_part(quest.title)
    filename = f"{quest.quest_id}_{safe_title}.txt"

    # Format content with chapter title (if available) and quest title
    content_lines = []
    if quest.chapter_title:
        content_lines.append(f"(Quest is part of chapter: {quest.chapter_title})\n")
    content_lines.append(f"# {quest.title}\n")

    # Render main quest progression talks (from subQuests)
    for order_index, talk in quest.talks:
        if len(quest.talks) > 1:  # Only add talk headers if there are multiple talks
            content_lines.append(f"\n## Talk {order_index}\n")

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

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_QUEST,
            title=quest.title,
            id=int(quest.quest_id),
            relative_path=f"{text_types.TextCategory.AGD_QUEST.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_character_story(story_info: types.CharacterStoryInfo) -> types.RenderedItem:
    """Render all character stories into RAG-suitable format."""
    # Generate filename based on character name with collision safeguards
    safe_name = utils.make_safe_filename_part(story_info.character_name)
    filename = f"{story_info.avatar_id}_{safe_name}.txt"

    # Format content with character name header and all stories
    story_count = len(story_info.stories)
    content_lines = [f"# {story_info.character_name} - Character Stories\n"]
    content_lines.append(f"*{story_count} stories for this character*\n")

    for i, story in enumerate(story_info.stories, 1):
        content_lines.append(f"## {i}. {story.title}\n")
        content_lines.append(story.content)
        content_lines.append("")  # Add blank line between stories

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_CHARACTER_STORY,
            title=story_info.character_name,
            id=int(story_info.avatar_id),
            relative_path=f"{text_types.TextCategory.AGD_CHARACTER_STORY.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_subtitle(
    subtitle_info: types.SubtitleInfo, subtitle_path: str
) -> types.RenderedItem:
    """Render subtitle content into RAG-suitable format."""
    # Generate ID from hash of subtitle path (12 hex chars = 48 bits, safe for JavaScript)
    subtitle_id = int(
        hashlib.sha256(subtitle_path.encode("utf-8")).hexdigest()[:12], base=16
    )

    # Generate filename based on subtitle file name
    path_obj = pathlib.Path(subtitle_path)
    safe_name = utils.make_safe_filename_part(path_obj.stem)
    filename = f"{subtitle_id}_{safe_name}.txt"

    # Format content with subtitle header and all text lines
    content_lines = [f"# Subtitle: {path_obj.stem}\n"]
    content_lines.extend(subtitle_info.text_lines)

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_SUBTITLE,
            title=path_obj.stem,
            id=subtitle_id,
            relative_path=f"{text_types.TextCategory.AGD_SUBTITLE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_material(material_info: types.MaterialInfo) -> types.RenderedItem:
    """Render material content into RAG-suitable format."""
    # Generate filename based on material name
    safe_name = utils.make_safe_filename_part(material_info.name)
    filename = f"{material_info.material_id}_{safe_name}.txt"

    # Format content with material name header and description
    content_lines = [f"# {material_info.name}\n"]
    content_lines.append(material_info.description)

    rendered_content = "\n".join(content_lines)

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_MATERIAL_TYPE,
            title=material_info.name,
            id=int(material_info.material_id),
            relative_path=f"{text_types.TextCategory.AGD_MATERIAL_TYPE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_materials_by_type(
    material_type: str, materials: list[types.MaterialInfo]
) -> types.RenderedItem:
    """Render multiple materials of the same type into a single RAG-suitable format file."""
    # Generate ID from hash of material type (12 hex chars = 48 bits, safe for JavaScript)
    material_type_id = int(
        hashlib.sha256(material_type.encode("utf-8")).hexdigest()[:12], base=16
    )

    # Generate filename based on material type
    safe_type = utils.make_safe_filename_part(material_type)
    filename = f"{material_type_id}_{safe_type}.txt"

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

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_MATERIAL_TYPE,
            title=material_type,
            id=material_type_id,
            relative_path=f"{text_types.TextCategory.AGD_MATERIAL_TYPE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_voiceline(voiceline_info: types.VoicelineInfo) -> types.RenderedItem:
    """Render voiceline content into RAG-suitable format."""
    # Generate filename based on character name
    safe_name = utils.make_safe_filename_part(voiceline_info.character_name)
    filename = f"{voiceline_info.avatar_id}_{safe_name}.txt"

    # Format content with character name header and all voicelines
    content_lines = [f"# {voiceline_info.character_name} Voicelines\n"]

    for title, content in voiceline_info.voicelines.items():
        content_lines.append(f"## {title}")
        content_lines.append(content)
        content_lines.append("")  # Empty line between voicelines

    rendered_content = "\n".join(content_lines).rstrip()

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_VOICELINE,
            title=voiceline_info.character_name,
            id=int(voiceline_info.avatar_id),
            relative_path=f"{text_types.TextCategory.AGD_VOICELINE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_artifact_set(artifact_set_info: types.ArtifactSetInfo) -> types.RenderedItem:
    """Render artifact set content into RAG-suitable format."""
    # Generate filename based on set name and ID
    safe_name = utils.make_safe_filename_part(artifact_set_info.set_name)
    filename = f"{artifact_set_info.set_id}_{safe_name}.txt"

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

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ARTIFACT_SET,
            title=artifact_set_info.set_name,
            id=int(artifact_set_info.set_id),
            relative_path=f"{text_types.TextCategory.AGD_ARTIFACT_SET.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_talk_group(
    talk_group_type: talk_parsing.TalkGroupType,
    talk_group_id: str,
    talk_group_info: types.TalkGroupInfo,
    language: localization.Language,
) -> types.RenderedItem:
    """Render multiple talks from an activity group into a single file."""
    # Generate filename based on activity ID
    safe_type = utils.make_safe_filename_part(str(talk_group_type))
    filename = f"{talk_group_id}_{safe_type}.txt"

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

    return types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_TALK_GROUP,
            title=f"{talk_group_type} - {talk_group_id}",
            id=int(talk_group_id),
            relative_path=f"{text_types.TextCategory.AGD_TALK_GROUP.value}/{filename}",
        ),
        content=rendered_content,
    )
