"""Rendering functions for converting AGD content to RAG-suitable text format."""

import hashlib
import pathlib
from collections import defaultdict
from typing import Iterator, assert_never

from istaroth import utils
from istaroth.agd import (
    id_types,
    issues,
    localization,
    processed_types,
    talk_parsing,
    text_utils,
)
from istaroth.text import types as text_types


class _TalkTextGraph:
    """Graph structure for talk dialog items with nextDialogs relationships."""

    def __init__(self, talk: processed_types.TalkInfo) -> None:
        """Build graph structure from talk dialog items."""
        self.dialog_id_to_text: dict[id_types.DialogId, processed_types.TalkText] = {}
        self.graph: dict[id_types.DialogId, list[id_types.DialogId]] = defaultdict(list)
        self.incoming_edges: dict[id_types.DialogId, int] = defaultdict(int)
        self.outgoing_edges: dict[id_types.DialogId, int] = defaultdict(int)

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

    def find_entrypoints(
        self, talk: processed_types.TalkInfo
    ) -> list[id_types.DialogId]:
        """Find entry points (dialogs with no incoming edges).

        If no entry points are found, falls back to finding cycles and using
        the smallest dialog ID from each cycle as an entry point.
        """
        entrypoints = []

        # Find dialogs with no incoming edges
        all_dialog_ids = {text.dialog_id for text in talk.text}
        for dialog_id in all_dialog_ids:
            if self.incoming_edges.get(dialog_id, 0) == 0:
                entrypoints.append(dialog_id)

        if entrypoints:
            return sorted(entrypoints)

        # Fallback: find all cycles and use smallest dialog ID from them
        return [min(min(cycle) for cycle in self._find_cycles())]

    def _find_cycles(self) -> list[set[id_types.DialogId]]:
        """Find all unique cycles in the graph.

        Uses DFS to detect cycles. When a back edge is found, extracts the cycle.

        Returns:
            List of sets, where each set contains the dialog IDs in a cycle.
        """
        visited = set[id_types.DialogId]()
        rec_stack = set[id_types.DialogId]()
        cycles = []

        def dfs(node: id_types.DialogId, path: list[id_types.DialogId]) -> None:
            if node in rec_stack:
                # Found a cycle - extract it
                cycle_start_idx = path.index(node)
                cycle = set(path[cycle_start_idx:])
                # Only add if we haven't seen this cycle before
                if cycle not in cycles:
                    cycles.append(cycle)
                # Continue exploring to find other cycles
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for next_node in self.graph.get(node, []):
                dfs(next_node, path)

            path.pop()
            rec_stack.remove(node)

        for dialog_id in self.dialog_id_to_text:
            if dialog_id not in visited:
                dfs(dialog_id, [])

        return cycles


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
    content: str, metadata: processed_types.ReadableMetadata
) -> processed_types.RenderedItem:
    """Render readable content into RAG-suitable format."""
    # Generate filename based on title
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"{metadata.localization_id}_{safe_title}.txt"

    # Format content with title header
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


def render_book(
    content: str, metadata: processed_types.ReadableMetadata
) -> processed_types.RenderedItem:
    """Render book content into RAG-suitable format."""
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"{metadata.localization_id}_{safe_title}.txt"
    rendered_content = f"# {metadata.title}\n\n{content}"

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_BOOK,
            title=metadata.title,
            id=metadata.localization_id,
            relative_path=f"{text_types.TextCategory.AGD_BOOK.value}/{filename}",
        ),
        content=rendered_content,
    )


def _render_volume_annotation(
    series_name: str, index: int, total: int, language: localization.Language
) -> str:
    """Render the per-volume series annotation line in the output language."""
    match language:
        case localization.Language.CHS:
            return f"*{series_name}·第 {index} 卷，共 {total} 卷*"
        case localization.Language.ENG:
            return f"*{series_name} — Volume {index} of {total}*"
        case _:
            assert_never(language)


def render_book_series(
    series_info: processed_types.BookSeriesInfo, language: localization.Language
) -> processed_types.RenderedItem:
    """Render a multi-volume book series into a single RAG-suitable file.

    Volumes render in reading order under one series header, each prefixed with an
    annotation line naming the series and the volume's position so a chunk retrieved
    in isolation still carries its series context.
    """
    safe_name = utils.make_safe_filename_part(series_info.series_name)
    filename = f"{series_info.suit_id}_{safe_name}.txt"

    total = len(series_info.volumes)
    content_parts = [f"# {series_info.series_name}"]
    for index, volume in enumerate(series_info.volumes, start=1):
        annotation = _render_volume_annotation(
            series_info.series_name, index, total, language
        )
        content_parts.append(f"## {volume.title}\n\n{annotation}\n\n{volume.content}")

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_BOOK,
            title=series_info.series_name,
            id=series_info.suit_id,
            relative_path=f"{text_types.TextCategory.AGD_BOOK.value}/{filename}",
        ),
        content="\n\n".join(content_parts),
    )


def render_weapon(
    weapon_info: processed_types.WeaponInfo,
) -> processed_types.RenderedItem:
    """Render a weapon's assembled story document into RAG-suitable format."""
    safe_name = utils.make_safe_filename_part(weapon_info.name)
    filename = f"{weapon_info.weapon_id}_{safe_name}.txt"

    content_lines = [f"# {weapon_info.name}\n"]
    if weapon_info.description:
        content_lines.append(f"{weapon_info.description}\n")
    # Join story pages with a markdown horizontal rule so page boundaries survive.
    content_lines.append("\n\n---\n\n".join(weapon_info.story_pages))

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_WEAPON,
            title=weapon_info.name,
            id=int(weapon_info.weapon_id),
            relative_path=f"{text_types.TextCategory.AGD_WEAPON.value}/{filename}",
        ),
        content="\n".join(content_lines),
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


def _render_dialog_line(
    talk_text: processed_types.TalkText, language: localization.Language
) -> str | None:
    """Render a single dialog line if it should not be skipped.

    Returns:
        Formatted line string or None if dialog should be skipped
    """
    if text_utils.should_skip_text(talk_text.message, language):
        return None
    if talk_text.role is None:
        return talk_text.message
    return f"{talk_text.role}: {talk_text.message}"


def _process_branch(
    next_dialog_ids: list[id_types.DialogId],
    graph: _TalkTextGraph,
    rendered: set[id_types.DialogId],
    language: localization.Language,
) -> tuple[id_types.DialogId | None, list[list[str]]]:
    """Process multiple branches until convergence point.

    Processes each branch from next_dialog_ids, rendering all dialogs until hitting
    a convergence point (dialog with 2+ incoming edges). Asserts that all branches
    converge at the same point.

    Args:
        next_dialog_ids: List of starting dialog IDs for branches
        graph: TalkTextGraph object containing graph structure
        rendered: Set of already rendered dialog IDs
        language: Language for filtering

    Returns:
        Tuple of (convergence_point_id or None, list of branch lines for each branch)
    """

    paths: list[list[int | None]] = [[di] for di in next_dialog_ids]
    # Per-path set of dialogs already covered (walked into) on this path, seeded
    # with the calling branch's options since those are the paths we start with.
    # A path only follows edges to dialogs not yet in its set; see below.
    path_offered: list[set[int]] = [set(next_dialog_ids) for _ in next_dialog_ids]
    # Path indexes for paths that have back edges (i.e. edges pointing to
    # pre-branch dialogs).
    cycle_pis = set[int]()
    dialog_paths = defaultdict[int | None, set[int]](set)
    dialog_paths.update({di: {i} for i, di in enumerate(next_dialog_ids)})

    seeds = set(next_dialog_ids)

    def _reachable(start: int) -> set[int]:
        """Dialogs reachable from ``start`` by following ``nextDialogs`` edges."""
        seen = set[int]()
        stack = [start]
        while stack:
            for nxt in graph.graph.get(stack.pop(), []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def _advance(pi: int) -> None:
        """Follow path ``pi`` one dialog forward, splitting on multiple edges."""
        path = paths[pi]
        curr_di = path[-1]
        assert curr_di is not None, "Cannot advance an ended path"
        next_dis = graph.graph.get(curr_di, [])

        if not next_dis:
            path.append(None)
            assert pi not in dialog_paths[None], f"Path ended multiple times"
            dialog_paths[None].add(pi)
            return

        # Only follow edges to dialogs not already covered on this path. A
        # covered target is (or will be) rendered by the path that first reached
        # it, so re-walking it merely duplicates content -- and for an "ask about
        # X" menu hub (whose answer tails re-offer the same options) it would
        # enumerate every ordering of the options. This also handles decreasing
        # menus and menus that add an exit option late: only the genuinely new
        # options are followed. When nothing new remains, the path has looped
        # back into already-seen content; stop here (curr_di, the answer tail, is
        # already in ``path`` and still gets rendered).
        uncovered = [di for di in next_dis if di not in path_offered[pi]]
        if not uncovered:
            cycle_pis.add(pi)
            return
        path_offered[pi] |= set(uncovered)

        pis_to_extend = [pi]
        for _ in uncovered[1:]:
            paths.append(path[:])
            new_path_pi = len(paths) - 1
            path_offered.append(set(path_offered[pi]))
            pis_to_extend.append(new_path_pi)
            for di in paths[new_path_pi]:
                assert new_path_pi not in dialog_paths[di], f"Found cycle: {path}"
                dialog_paths[di].add(new_path_pi)

        for pi_to_extend, di_to_extend in zip(pis_to_extend, uncovered):
            paths[pi_to_extend].append(di_to_extend)

            # A dialog already rendered by an earlier branch in this talk is a
            # back edge out of this region; stop. (Re-entries within the region
            # are already excluded by the ``uncovered`` filter above.)
            if di_to_extend in rendered:
                cycle_pis.add(pi_to_extend)
                continue

            dialog_paths[di_to_extend].add(pi_to_extend)

    # First, keep advancing all paths until we find a convergence point.
    while True:
        assert cycle_pis < set(range(len(paths))), f"All paths ended in cycles"

        # If any dialog has been visited by all non-cycle paths, that's our
        # convergence point.
        potential_conv_points = [
            di
            for di, visited_paths in dialog_paths.items()
            if visited_paths >= set(range(len(paths))) - cycle_pis
        ]
        if potential_conv_points:
            assert (
                len(potential_conv_points) == 1
            ) or cycle_pis, f"Multiple convergence points: {potential_conv_points}"
            conv_point = potential_conv_points[0]
            break

        # A path that has reached a convergence node (one with 2+ incoming edges)
        # waits there rather than walking through it: if the first branch to
        # arrive followed the convergence node's own out-edges it would split and
        # emit duplicate options that all share the identical pre-convergence
        # prefix (issue #62). Seeds are never waits -- they are the branch starts
        # we must expand. A path that has ended or looped back is also done.
        #
        # Only wait if the node still has a forward (uncovered) out-edge to
        # reconverge on. A join whose every out-edge is already covered is a
        # back-edge loop (e.g. a wrong-answer menu tail that re-offers the same
        # options); let it advance so the existing cycle handling stops it
        # instead of stalling here and spawning spurious empty options.
        waits: dict[int, int] = {}
        movers: list[int] = []
        for pi in range(len(paths)):
            if pi in cycle_pis or (curr_di := paths[pi][-1]) is None:
                continue
            if (
                curr_di not in seeds
                and graph.incoming_edges.get(curr_di, 0) >= 2
                and any(d not in path_offered[pi] for d in graph.graph.get(curr_di, []))
            ):
                waits[pi] = curr_di
            else:
                movers.append(pi)

        if movers:
            for pi in movers:
                _advance(pi)
            continue

        # Every live path waits at a convergence node, but none is yet shared by
        # all -- they sit at intermediate convergences nested inside the branch.
        # Resume all but the deepest (the node reachable from every other waiting
        # node); the deepest is the real meeting point and keeps waiting. If no
        # single deepest exists, or some path already ended/looped (so the branch
        # never fully reconverges), resume everyone.
        waiting_nodes = set(waits.values())
        deepest = None
        if not cycle_pis and None not in dialog_paths and len(waiting_nodes) > 1:
            deepest = next(
                (
                    node
                    for node in waiting_nodes
                    if all(node in _reachable(o) for o in waiting_nodes - {node})
                ),
                None,
            )
        for pi, node in waits.items():
            if node != deepest:
                _advance(pi)

    lines_list = []
    for pi, path in enumerate(paths):
        branch_lines = []
        for di in path:
            if di == conv_point:
                break

            assert di is not None, "Unexpected None in path"

            if (text := graph.dialog_id_to_text.get(di)) is None:
                issues.record(issues.IssueType.MISSING_DIALOG, str(di))
                branch_lines.append(f"[Missing Dialog {di}]")
            else:
                rendered.add(di)
                if (rendered_text := _render_dialog_line(text, language)) is not None:
                    branch_lines.append(rendered_text)
        else:
            assert pi in cycle_pis, f"Path {pi} did not converge"
            branch_lines.append(f"[Loops back to an already-shown dialog]")

        lines_list.append(branch_lines)

    return conv_point, lines_list


def _render_talk_dialogs(
    dialog_id: id_types.DialogId,
    graph: _TalkTextGraph,
    rendered: set[id_types.DialogId],
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
    current_id: id_types.DialogId | None = dialog_id

    # Follow single next dialogues until we hit multiple next dialogues
    while current_id is not None:
        if current_id in rendered:
            lines.append(f"[Circling back to a previous dialog]")
            return lines

        rendered.add(current_id)

        # Check if dialog exists
        if current_id in graph.dialog_id_to_text:
            if line := _render_dialog_line(
                graph.dialog_id_to_text[current_id], language
            ):
                lines.append(line)
        else:
            issues.record(issues.IssueType.MISSING_DIALOG, str(current_id))
            lines.append(f"[Missing Dialog {current_id}]")
            return lines

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
        current_id, branch_lines_list = _process_branch(
            next_dialog_ids, graph, rendered, language
        )

        if len(branch_lines_list) == 1:
            lines.extend(branch_lines_list[0])
        else:
            # Render each option's lines as a markdown blockquote so the grouping
            # survives markdown rendering (leading-space indentation is stripped by
            # markdown). Blank lines around each quote keep the labels and the
            # convergence tail from being absorbed into a quote via markdown's lazy
            # continuation rule.
            for i, branch_lines in enumerate(branch_lines_list, 1):
                lines.append("")
                lines.append(f"Option {i}:")
                lines.append("")
                lines.extend(f"> {branch_line}" for branch_line in branch_lines)
            lines.append("")

    return lines


def _render_talk_content(
    talk: processed_types.TalkInfo, language: localization.Language
) -> list[str]:
    """Render talk dialog to lines with branching support.

    Args:
        talk: TalkInfo containing dialog items
        language: Language for filtering

    Returns:
        List of rendered dialog lines
    """
    if not talk.text:
        return []

    graph = _TalkTextGraph(talk)
    entrypoints = graph.find_entrypoints(talk)
    assert entrypoints, "No entrypoints found"

    rendered: set[id_types.DialogId] = set()
    all_lines: list[str] = []

    for i, entrypoint in enumerate(entrypoints):
        if i > 0:
            all_lines.append("")

        entrypoint_rendered = set[id_types.DialogId]()
        entrypoint_lines = _render_talk_dialogs(
            entrypoint, graph, entrypoint_rendered, language
        )
        rendered.update(entrypoint_rendered)
        all_lines.extend(entrypoint_lines)

    all_dialog_ids = {text.dialog_id for text in talk.text}
    orphaned_ids = all_dialog_ids - rendered

    if orphaned_ids:
        all_lines.append("")

        for orphaned_id in orphaned_ids:
            text = graph.dialog_id_to_text[orphaned_id]
            if (rendered_text := _render_dialog_line(text, language)) is not None:
                all_lines.append(f"[Orphaned dialog] {rendered_text}")

    return all_lines


def render_talk(
    talk: processed_types.TalkInfo,
    *,
    talk_id: id_types.TalkId,
    talk_file_path: str | None = None,
    language: localization.Language,
) -> processed_types.RenderedItem:
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
    content_lines.extend(_render_talk_content(talk, language))

    rendered_content = "\n".join(content_lines)

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_TALK,
            title=title,
            id=talk_id,
            relative_path=f"{text_types.TextCategory.AGD_TALK.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_quest(
    quest: processed_types.QuestInfo, language: localization.Language
) -> processed_types.RenderedItem:
    """Render quest information into RAG-suitable format."""
    # Generate filename based on quest title
    safe_title = utils.make_safe_filename_part(quest.title)
    filename = f"{quest.quest_id}_{safe_title}.txt"

    # Format content with chapter title (if available) and quest title
    content_lines = []
    if quest.chapter_title:
        content_lines.append(f"(Quest is part of chapter: {quest.chapter_title})\n")
    content_lines.append(f"# {quest.title}\n")
    if quest.description:
        content_lines.append(f"{quest.description}\n")

    # Render quest progression steps in `order`. Talk steps show their dialogue
    # under a `## Talk <order>` header (lead-ins placed via beginCond marked as
    # such); non-dialogue objective steps show only their objective text under a
    # `## Objective <order>` header. Both surface the step's objective text, when
    # present, in parentheses above the body.
    # When several completing talks finish the same subQuest `order` (alternative
    # branches of one step), `## Talk <order>` alone would repeat; number them
    # `(variant N)` to keep headers unique. Lead-ins keep their own suffix.
    variants_per_order: dict[int, int] = defaultdict(int)
    for step in quest.steps:
        if step.talk is not None and not step.is_lead_in:
            variants_per_order[step.order] += 1
    variant_seen: dict[int, int] = defaultdict(int)
    for step in quest.steps:
        if step.talk is not None:
            if step.is_lead_in:
                suffix = " (alternative/additional)"
            elif variants_per_order[step.order] > 1:
                variant_seen[step.order] += 1
                suffix = f" (variant {variant_seen[step.order]})"
            else:
                suffix = ""
            content_lines.append(f"\n## Talk {step.order}{suffix}\n")
            if step.description:
                content_lines.append(f"({step.description})\n")
            content_lines.extend(_render_talk_content(step.talk, language))
        else:
            content_lines.append(f"\n## Objective {step.order}\n")
            if step.description:
                content_lines.append(f"({step.description})\n")

    # Render non-subquest talks in a separate section
    if quest.non_subquest_talks:
        content_lines.append("\n## Additional Conversations\n")
        content_lines.append("*Conversations not present as sub-quests.*\n")

        for i, talk in enumerate(quest.non_subquest_talks, 1):
            if len(quest.non_subquest_talks) > 1:
                content_lines.append(f"\n### Additional Talk {i}\n")

            content_lines.extend(_render_talk_content(talk, language))

    # Render FreeGroup "free talks" attached to this quest by talkId numbering.
    if quest.associated_free_talks:
        content_lines.append("\n## Associated Free Talks\n")
        content_lines.append("*Free talks linked to this quest by talk id.*\n")

        for i, talk in enumerate(quest.associated_free_talks, 1):
            if len(quest.associated_free_talks) > 1:
                content_lines.append(f"\n### Free Talk {i}\n")

            content_lines.extend(_render_talk_content(talk, language))

    rendered_content = "\n".join(content_lines)

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_QUEST,
            title=quest.title,
            id=quest.quest_id,
            relative_path=f"{text_types.TextCategory.AGD_QUEST.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_character_story(
    story_info: processed_types.CharacterStoryInfo,
) -> processed_types.RenderedItem:
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

    # Constellations as a flat list. No Cn prefix: the source data does not give a
    # reliable constellation index (the talents array order and openConfig disagree),
    # so we list them in talents-array order without asserting a number. The
    # Travelers' per-element sets are grouped under ### element subsections.
    if story_info.constellations:
        content_lines.append("## Constellations\n")
        current_element: object = object()  # sentinel so the first item opens a group
        first_group = True
        for constellation in story_info.constellations:
            if constellation.element != current_element:
                current_element = constellation.element
                if constellation.element is not None:
                    if not first_group:
                        content_lines.append("")
                    content_lines.append(f"### {constellation.element}\n")
                first_group = False
            description = " ".join(constellation.description.split())
            content_lines.append(f"{constellation.name}: {description}")
        content_lines.append("")

    rendered_content = "\n".join(content_lines)

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_CHARACTER_STORY,
            title=story_info.character_name,
            id=story_info.avatar_id,
            relative_path=f"{text_types.TextCategory.AGD_CHARACTER_STORY.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_subtitle(
    subtitle_info: processed_types.SubtitleInfo, subtitle_path: str
) -> processed_types.RenderedItem:
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

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_SUBTITLE,
            title=path_obj.stem,
            id=subtitle_id,
            relative_path=f"{text_types.TextCategory.AGD_SUBTITLE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_material(
    material_info: processed_types.MaterialInfo,
) -> processed_types.RenderedItem:
    """Render material content into RAG-suitable format."""
    # Generate filename based on material name
    safe_name = utils.make_safe_filename_part(material_info.name)
    filename = f"{material_info.material_id}_{safe_name}.txt"

    # Format content with material name header and description
    content_lines = [f"# {material_info.name}\n"]
    content_lines.append(material_info.description)

    rendered_content = "\n".join(content_lines)

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_MATERIAL_TYPE,
            title=material_info.name,
            id=material_info.material_id,
            relative_path=f"{text_types.TextCategory.AGD_MATERIAL_TYPE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_achievement_section(
    section_info: processed_types.AchievementSectionInfo,
) -> processed_types.RenderedItem:
    """Render one achievement section into a single text file."""
    filename = (
        f"{section_info.section_id}_"
        f"{utils.make_safe_filename_part(section_info.section_name)}.txt"
    )
    content_lines = [f"# {section_info.section_name}", ""]
    for achievement in section_info.achievements:
        content_lines.extend(
            [f"## {achievement.name}", "", achievement.description, ""]
        )

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ACHIEVEMENT,
            title=section_info.section_name,
            id=section_info.section_id,
            relative_path=(
                f"{text_types.TextCategory.AGD_ACHIEVEMENT.value}/{filename}"
            ),
        ),
        content="\n".join(content_lines).rstrip(),
    )


def _humanize_material_type(material_type: str) -> str:
    """Turn a raw MaterialType enum into a readable title (e.g. MATERIAL_FISH_ROD -> Fish Rod)."""
    return material_type.removeprefix("MATERIAL_").replace("_", " ").title()


def render_materials_by_type(
    material_type: str, materials: list[processed_types.MaterialInfo]
) -> processed_types.RenderedItem:
    """Render multiple materials of the same type into a single RAG-suitable format file."""
    # Generate ID from hash of material type (12 hex chars = 48 bits, safe for JavaScript)
    material_type_id = int(
        hashlib.sha256(material_type.encode("utf-8")).hexdigest()[:12], base=16
    )

    # Generate filename based on material type
    safe_type = utils.make_safe_filename_part(material_type)
    filename = f"{material_type_id}_{safe_type}.txt"

    material_type_name = _humanize_material_type(material_type)

    # Format content with material type header and all materials
    content_lines = [f"# Materials: {material_type_name}\n"]

    # Sort materials by ID for deterministic output
    sorted_materials = sorted(materials, key=lambda x: x.material_id)

    for material_info in sorted_materials:
        content_lines.append(f"## {material_info.name}")
        content_lines.append("")
        content_lines.append(material_info.description)
        content_lines.append("")

    rendered_content = "\n".join(content_lines).rstrip()

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_MATERIAL_TYPE,
            title=material_type_name,
            id=material_type_id,
            relative_path=f"{text_types.TextCategory.AGD_MATERIAL_TYPE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_voiceline(
    voiceline_info: processed_types.VoicelineInfo,
) -> processed_types.RenderedItem:
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

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_VOICELINE,
            title=voiceline_info.character_name,
            id=voiceline_info.avatar_id,
            relative_path=f"{text_types.TextCategory.AGD_VOICELINE.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_creature_group(
    group_info: processed_types.CreatureGroupInfo,
) -> processed_types.RenderedItem:
    """Render one codex subType group of creatures into a single RAG-suitable file."""
    # Hash the subType enum to a JS-safe id (48 bits), mirroring material types.
    group_id = int(
        hashlib.sha256(group_info.subtype.encode("utf-8")).hexdigest()[:12], base=16
    )
    filename = f"{group_id}_{group_info.subtype}.txt"
    # Frontend/manifest title is the clean group name (e.g. "Automatons"); the
    # in-file header keeps the parent type for RAG context, mirroring how material
    # types use a clean title with a decorated "# Materials: ..." header.
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


def render_artifact_set(
    artifact_set_info: processed_types.ArtifactSetInfo,
) -> processed_types.RenderedItem:
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

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ARTIFACT_SET,
            title=artifact_set_info.set_name,
            id=artifact_set_info.set_id,
            relative_path=f"{text_types.TextCategory.AGD_ARTIFACT_SET.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_talk_group(
    talk_group_type: talk_parsing.TalkGroupType,
    talk_group_id: str,
    talk_group_info: processed_types.TalkGroupInfo,
    language: localization.Language,
    *,
    group_name: str | None = None,
) -> processed_types.RenderedItem:
    """Render multiple talks from an activity group into a single file."""
    # Generate filename based on activity ID
    safe_type = utils.make_safe_filename_part(str(talk_group_type))
    filename = f"{talk_group_id}_{safe_type}.txt"

    title = (
        f"{group_name} ({talk_group_type} {talk_group_id})"
        if group_name is not None
        else f"{talk_group_type} - {talk_group_id}"
    )

    # Format content with activity group header and all talks
    content_lines = [f"# Talk Group: {title}\n"]

    for i, (talk, next_talks) in enumerate(talk_group_info.talks):
        content_lines.append(f"## Talk {i}\n")

        # Add talk dialog
        content_lines.extend(_render_talk_content(talk, language))
        content_lines.append("")  # Empty line between talks

        # Add followup talks
        for j, next_talk in enumerate(next_talks):
            content_lines.append(f"### Talk {i} related talk {j}\n")
            # Add talk dialog
            content_lines.extend(_render_talk_content(next_talk, language))
            content_lines.append("")  # Empty line between talks

    rendered_content = "\n".join(content_lines).rstrip()

    # GadgetGroup's TalkGroupId is the composite "<configId>_<groupId>" string
    # (issue #186); collapse to the stable int ``configId * 10**9 + groupId`` to
    # fit ``TextMetadata.id``. Other types carry a single int as str.
    if talk_group_type == "GadgetGroup":
        config_id, group_id = talk_parsing.parse_gadget_group_composite_id(
            talk_group_id
        )
        metadata_id = talk_parsing.gadget_group_composite_id(config_id, group_id)
    else:
        metadata_id = int(talk_group_id)

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_TALK_GROUP,
            title=title,
            id=metadata_id,
            relative_path=f"{text_types.TextCategory.AGD_TALK_GROUP.value}/{filename}",
        ),
        content=rendered_content,
    )


def _render_cond(cond: processed_types.CondGrp) -> str:
    """Render a ``CondGrp`` into a human-readable inline string."""
    parts = [_render_cond_entry(e) for e in cond.conds]
    joiner = (
        " and "
        if cond.logic == "LOGIC_AND"
        else " or " if cond.logic == "LOGIC_OR" else ", "
    )
    return joiner.join(parts)


def _render_cond_entry(entry: processed_types.CondEntry) -> str:
    """Render a single cond entry as ``TYPE [param, ...]``."""
    return f"{entry.type} {entry.param}"


def _assign_fork_numbers(
    steps: list[processed_types.CoopStep], counter: list[int]
) -> dict[int, int]:
    """Depth-first numbering of all choice steps. Returns ``id(step) -> fork_number``.

    ``counter`` is a single-element ``list[int]`` (mutable container) threaded
    through recursive calls so the counter is shared without a ``nonlocal``
    declaration or a global.
    """
    mapping: dict[int, int] = {}
    for step in steps:
        if step.choice is not None:
            counter[0] += 1
            mapping[id(step)] = counter[0]
            for option in step.choice.options:
                mapping.update(_assign_fork_numbers(option.steps, counter))
    return mapping


def _render_choice_section(
    choice_step: processed_types.CoopStep,
    fork_num: int,
    language: localization.Language,
    fork_map: dict[int, int],
) -> tuple[list[str], list[list[str]]]:
    """Render a ``### Choice N:`` section and return (lines, nested_sections).

    ``nested_sections`` contains fully-rendered ``### Choice N:`` sections for
    choices nested inside branches (to be appended after the current level).
    The nested sections are rendered as separate top-level ``### Choice`` blocks
    that the ``*→ Next: Choice N*`` markers at the end of each branch reference.
    """
    lines: list[str] = []
    nested: list[list[str]] = []

    assert choice_step.choice is not None
    lines.append(f"### Choice {fork_num}")
    lines.append("")

    # Condition annotation for COND branches — shown once above the options.
    for opt in choice_step.choice.options:
        if opt.cond is not None and opt.cond.conds:
            lines.append(f"*Condition: {_render_cond(opt.cond)}*")
            lines.append("")
            break

    for i, option in enumerate(choice_step.choice.options, 1):
        heading = f"#### Branch {i}"
        if option.prompt:
            heading += f": {option.prompt}"
        if option.show_cond and option.show_cond.conds:
            heading += f" (only shown if {_render_cond(option.show_cond)})"
        if option.cond and option.cond.conds:
            heading += f" (applies if {_render_cond(option.cond)})"
        lines.append(heading)
        lines.append("")

        # Render branch content: talks inline, nested choices become → Next pointers.
        # The nested choice's full ### Choice N section is rendered recursively
        # and collected for flat emission after the current choice's branches.
        next_marker = "*→ End of conversation*"
        for step in option.steps:
            if step.talk is not None:
                lines.extend(_render_talk_content(step.talk, language))
            elif step.choice is not None:
                nested_fork_num = fork_map[id(step)]
                next_marker = f"*→ Next: Choice {nested_fork_num}*"

                section_lines, new_nested = _render_choice_section(
                    step, nested_fork_num, language, fork_map
                )
                nested.append(section_lines)
                nested.extend(new_nested)
            elif step.ending is not None:
                next_marker = f"*→ Ending (save point {step.ending.save_point_id})*"

        lines.append(next_marker)
        lines.append("")

    return lines, nested


def _render_coop_steps(
    steps: list[processed_types.CoopStep],
    language: localization.Language,
    fork_map: dict[int, int],
) -> list[str]:
    """Render a hangout story's play-ordered steps with explicit branch routing.

    ``fork_map`` is the output of ``_assign_fork_numbers`` — a mapping from
    ``id(CoopStep)`` to its ``Choice N`` number.
    """
    lines: list[str] = []
    nested_sections: list[list[str]] = []

    for step in steps:
        if step.talk is not None:
            talk_lines = _render_talk_content(step.talk, language)
            if talk_lines:
                # Entry talk in the conversation-level steps gets a ### Talk: header.
                # Talks nested inside branches are inlined without headers.
                title = talk_lines[0].rstrip()
                lines.append(f"### Talk: {title}")
                lines.append("")
                lines.extend(talk_lines)
        elif step.choice is not None:
            fork_num = fork_map[id(step)]
            section_lines, new_nested = _render_choice_section(
                step, fork_num, language, fork_map
            )
            lines.append("")
            lines.extend(section_lines)
            nested_sections.extend(new_nested)
        elif step.ending is not None:
            lines.append("")
            lines.append(f"*→ Ending (save point {step.ending.save_point_id})*")

    for ns in nested_sections:
        lines.append("")
        lines.extend(ns)

    return lines


def render_hangout(
    hangout: processed_types.HangoutInfo, language: localization.Language
) -> processed_types.RenderedItem:
    """Render a hangout quest's Coop story dialogue into RAG-suitable format."""
    title = (
        f"{hangout.primary_character} - {hangout.quest_title}"
        if hangout.primary_character is not None
        else hangout.quest_title
    )
    filename = f"{hangout.quest_id}_{utils.make_safe_filename_part(title)}.txt"

    content_lines = [f"# Hangout: {title}\n"]
    for i, story in enumerate(hangout.stories, 1):
        content_lines.append(f"## Conversation {i}\n")

        # Phase 1: number all forks in the story.
        fork_counter: list[int] = [0]
        fork_map = _assign_fork_numbers(story.steps, fork_counter)

        # Phase 2: render using the fork numbers.
        content_lines.extend(_render_coop_steps(story.steps, language, fork_map))

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_COOP,
            title=title,
            id=hangout.quest_id,
            relative_path=f"{text_types.TextCategory.AGD_COOP.value}/{filename}",
        ),
        content="\n".join(content_lines).rstrip(),
    )
