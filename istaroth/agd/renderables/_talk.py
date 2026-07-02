"""Shared dialogue engine + talk processing and rendering."""

import pathlib
from collections import defaultdict
from typing import Iterator

from istaroth import utils
from istaroth.agd import (
    agd_types,
    id_types,
    issues,
    localization,
    processed_types,
    repo,
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
        """Find entry points (dialogs with no incoming edges)."""
        entrypoints = []
        all_dialog_ids = {text.dialog_id for text in talk.text}
        for dialog_id in all_dialog_ids:
            if self.incoming_edges.get(dialog_id, 0) == 0:
                entrypoints.append(dialog_id)
        if entrypoints:
            return sorted(entrypoints)
        return [min(min(cycle) for cycle in self._find_cycles())]

    def _find_cycles(self) -> list[set[id_types.DialogId]]:
        """Find all unique cycles in the graph using DFS."""
        visited = set[id_types.DialogId]()
        rec_stack = set[id_types.DialogId]()
        cycles = []

        def dfs(node: id_types.DialogId, path: list[id_types.DialogId]) -> None:
            if node in rec_stack:
                cycle_start_idx = path.index(node)
                cycle = set(path[cycle_start_idx:])
                if cycle not in cycles:
                    cycles.append(cycle)
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
        talk_file_path: Relative path like "BinOutput/Talk/Quest/123.json" or
            "BinOutput/Talk/456.json"

    Returns:
        Talk type: "quest", "npc", "root", etc.
    """
    path = pathlib.Path(talk_file_path)
    assert path.parts[0] == "BinOutput"
    assert path.parts[1] == "Talk"
    if len(path.parts) >= 4:
        return path.parts[2].lower()
    elif len(path.parts) == 3:
        return "root"
    else:
        raise ValueError(f"Invalid talk file path {talk_file_path}")


def _render_dialog_line(
    talk_text: processed_types.TalkText, language: localization.Language
) -> str | None:
    """Render a single dialog line if it should not be skipped.

    Returns:
        Formatted line string or None if dialog should be skipped
    """
    if talk_text.skip or text_utils.should_skip_text(talk_text.message, language):
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
    path_offered: list[set[int]] = [set(next_dialog_ids) for _ in next_dialog_ids]
    cycle_pis = set[int]()
    dialog_paths = defaultdict[int | None, set[int]](set)
    dialog_paths.update({di: {i} for i, di in enumerate(next_dialog_ids)})

    seeds = set(next_dialog_ids)

    def _reachable(start: int) -> set[int]:
        seen = set[int]()
        stack = [start]
        while stack:
            for nxt in graph.graph.get(stack.pop(), []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def _advance(pi: int) -> None:
        path = paths[pi]
        curr_di = path[-1]
        assert curr_di is not None, "Cannot advance an ended path"
        next_dis = graph.graph.get(curr_di, [])
        if not next_dis:
            path.append(None)
            assert pi not in dialog_paths[None], f"Path ended multiple times"
            dialog_paths[None].add(pi)
            return
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
            if di_to_extend in rendered:
                cycle_pis.add(pi_to_extend)
                continue
            dialog_paths[di_to_extend].add(pi_to_extend)

    while True:
        assert cycle_pis < set(range(len(paths))), f"All paths ended in cycles"
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
        rendered: Set of already rendered dialog IDs
        language: Language for filtering
    """
    lines: list[str] = []
    current_id: id_types.DialogId | None = dialog_id

    while current_id is not None:
        if current_id in rendered:
            lines.append(f"[Circling back to a previous dialog]")
            return lines
        rendered.add(current_id)
        if current_id in graph.dialog_id_to_text:
            if line := _render_dialog_line(
                graph.dialog_id_to_text[current_id], language
            ):
                lines.append(line)
        else:
            issues.record(issues.IssueType.MISSING_DIALOG, str(current_id))
            lines.append(f"[Missing Dialog {current_id}]")
            return lines
        next_dialog_ids = graph.graph.get(current_id, [])
        if not next_dialog_ids:
            break
        if len(next_dialog_ids) == 1:
            current_id = next_dialog_ids[0]
            continue
        current_id, branch_lines_list = _process_branch(
            next_dialog_ids, graph, rendered, language
        )
        if len(branch_lines_list) == 1:
            lines.extend(branch_lines_list[0])
        else:
            for i, branch_lines in enumerate(branch_lines_list, 1):
                lines.append("")
                lines.append(f"Option {i}:")
                lines.append("")
                lines.extend(f"> {branch_line}" for branch_line in branch_lines)
            lines.append("")

    return lines


def render_talk_content(
    talk: processed_types.TalkInfo, language: localization.Language
) -> list[str]:
    """Render talk dialog to lines with branching support."""
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

    # Generate filename - use first non-skipped, non-empty dialog line's message
    first_message = next(
        (text.message for text in talk.text if not text.skip and text.message.strip()),
        None,
    )
    if first_message is not None:
        # Take first 50 characters and clean for filename
        safe_title = utils.make_safe_filename_part(first_message)
        filename = f"{talk_id}_{safe_title}.txt"
        title = first_message[:100] if len(first_message) > 100 else first_message
    else:
        filename = f"{talk_id}_empty.txt"
        title = "Empty Talk"

    # Render content
    content_lines = ["# Talk Dialog\n"]
    content_lines.extend(render_talk_content(talk, language))

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


def get_talk_info(
    talk_path: str, *, data_repo: repo.DataRepo
) -> processed_types.TalkInfo:
    """Retrieve talk information from talk file."""
    # Load talk data
    talk_data = data_repo.load_talk_data(talk_path)

    if (dialog_list := talk_data.get("dialogList")) is None:
        return processed_types.TalkInfo(text=[])

    # Load supporting data
    text_map = data_repo.text_map_tracker()

    # Get cached mappings
    npc_id_to_name = data_repo.get_npc_id_to_name_mapping()
    dialog_id_to_role_hash = data_repo.get_dialog_id_to_role_name_hash_mapping()

    # Get localized role names for fallbacks
    localized_roles = localization.get_localized_role_names(data_repo.language)

    def _get_role_name_by_text_map_hash(
        dialog_item: agd_types.TalkDialogItem,
    ) -> str | None:
        dialog_id = dialog_item["id"]
        role_name_hash = dialog_item.get(
            "talkRoleNameTextMapHash"
        ) or dialog_id_to_role_hash.get(dialog_id)
        return (
            None
            if role_name_hash is None
            else text_map.get_current_optional(role_name_hash)
        )

    def _get_role_name_by_role(talk_role: agd_types.TalkRole) -> str | None:
        role_type = talk_role.get("type")
        match role_type:
            case "TALK_ROLE_NPC":
                npc_id = talk_role.get("_id", talk_role.get("id"))
                return npc_id_to_name.get(npc_id) if npc_id is not None else None
            case "TALK_ROLE_PLAYER":
                return localized_roles.player
            case "TALK_ROLE_MATE_AVATAR":
                return localized_roles.mate_avatar
            case "TALK_ROLE_NEED_CLICK_BLACK_SCREEN" | "TALK_ROLE_BLACK_SCREEN":
                return localized_roles.black_screen
            case _:
                return None

    def _get_role_name(dialog_item: agd_types.TalkDialogItem) -> str | None:
        talk_role = dialog_item["talkRole"]
        role_type = talk_role.get("type")

        by_role = _get_role_name_by_role(talk_role)
        by_name_hash = _get_role_name_by_text_map_hash(dialog_item)

        # If both are available, return one if they match or both otherwise.
        if (by_role is not None) and (by_name_hash is not None):
            if by_role == by_name_hash:
                return by_role
            else:
                return f"{by_role} ({by_name_hash})"
        if (resolved := by_name_hash or by_role) is not None:
            return resolved

        # TALK_ROLE_NONE is speaker-less narration / stage directions; render the
        # message with no role prefix.
        if role_type == "TALK_ROLE_NONE":
            return None
        issues.record(
            issues.IssueType.UNKNOWN_ROLE,
            f"dialog {dialog_item['id']} role {role_type}",
        )
        return f"{localized_roles.unknown_role} ({role_type})"

    # Process dialog items
    talk_texts = []
    for dialog_item in dialog_list:
        content_hash = dialog_item["talkContentTextMapHash"]
        next_dialog_ids = dialog_item.get("nextDialogs", [])
        skip = False
        if (message := text_map.get_optional(content_hash)) is None:
            # An untranslated hash may still be a CHS-only dev/test placeholder
            # (never translated into any language) rather than genuinely missing
            # text; check the source text before flagging it as missing.
            if (
                chs := data_repo.source_text_map_tracker().get_optional(content_hash)
            ) is not None and text_utils.should_skip_text(
                chs, localization.Language.CHS
            ):
                skip = True
                message = chs
            else:
                issues.record(issues.IssueType.MISSING_TEXT, str(content_hash))
                message = f"Missing text ({content_hash})"
        talk_texts.append(
            processed_types.TalkText(
                role=_get_role_name(dialog_item),
                message=message,
                next_dialog_ids=next_dialog_ids,
                dialog_id=dialog_item["id"],
                skip=skip,
            )
        )

    return processed_types.TalkInfo(text=talk_texts)


def get_talk_info_by_id(
    talk_id: id_types.TalkId, *, data_repo: repo.DataRepo
) -> processed_types.TalkInfo:
    """Retrieve talk information by talk ID."""
    talk_tracker = data_repo.talk_tracker()
    talk_file_path = talk_tracker.get_talk_file_path(talk_id)

    if talk_file_path is None:
        raise ValueError(f"Talk ID {talk_id} not found")

    return get_talk_info(talk_file_path, data_repo=data_repo)


def resolve_authoritative_talk(
    talk_id: id_types.TalkId, *, data_repo: repo.DataRepo
) -> processed_types.TalkInfo:
    """Resolve a talk pointed at by an authoritative finish condition.

    COMPLETE_TALK / COMPLETE_ANY_TALK name the talk that completes a step, so a
    not-found talk is a genuine upstream data gap: surface it inline as a visible
    placeholder rather than dropping the step or failing the whole quest. Any
    other error (an existing talk that fails to parse) still propagates.
    """
    try:
        return get_talk_info_by_id(talk_id, data_repo=data_repo)
    except ValueError:
        issues.record(issues.IssueType.MISSING_TALK, str(talk_id))
        return processed_types.TalkInfo(
            text=[
                processed_types.TalkText(
                    role="[Missing Talk]",
                    message=f"Talk {talk_id} could not be retrieved",
                    next_dialog_ids=[],
                    dialog_id=0,
                    skip=False,
                )
            ]
        )
