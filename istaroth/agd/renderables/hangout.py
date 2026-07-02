"""Hangout (Coop) processing and rendering."""

import pathlib
import typing

from istaroth import utils
from istaroth.agd import (
    coop_graph,
    id_types,
    issues,
    localization,
    processed_types,
    repo,
)
from istaroth.agd.renderables import _talk as _talk
from istaroth.text import types as text_types


def _parse_cond_grp(raw: dict[str, typing.Any]) -> processed_types.CondGrp:
    """Convert a raw deobfuscated cond-group dict into a CondGrp attrs."""
    return processed_types.CondGrp(
        logic=raw["condCombType"],
        conds=[
            processed_types.CondEntry(type=e["type"], param=list(e["param"]))
            for e in raw["coopCondList"]
        ],
    )


def _resolve_coop_steps(
    play_steps: list[coop_graph.PlayStep],
    *,
    local_talk_id_to_path: dict[id_types.CoopNodeId, str],
    seen: set[id_types.CoopNodeId],
    text_map: repo.TextMapTracker,
    dialog_content_hashes: dict[id_types.DialogId, id_types.TextMapHash],
    data_repo: repo.DataRepo,
) -> list[processed_types.CoopStep]:
    """Resolve a Coop story's play-order graph steps into renderable steps."""
    steps: list[processed_types.CoopStep] = []
    for play_step in play_steps:
        match play_step:
            case coop_graph.TalkStep(local_talk_id=local_talk_id):
                if (path := local_talk_id_to_path.get(local_talk_id)) is None:
                    continue
                seen.add(local_talk_id)
                if (talk_info := _talk.get_talk_info(path, data_repo=data_repo)).text:
                    steps.append(
                        processed_types.CoopStep(
                            talk=talk_info, choice=None, ending=None
                        )
                    )
            case coop_graph.ChoiceStep(branches=branches):
                options = []
                for branch in branches:
                    prompt = (
                        text_map.get_optional(content_hash)
                        if branch.dialog_id is not None
                        and (
                            content_hash := dialog_content_hashes.get(branch.dialog_id)
                        )
                        else None
                    )
                    branch_steps = _resolve_coop_steps(
                        branch.steps,
                        local_talk_id_to_path=local_talk_id_to_path,
                        seen=seen,
                        text_map=text_map,
                        dialog_content_hashes=dialog_content_hashes,
                        data_repo=data_repo,
                    )
                    cond = _parse_cond_grp(branch.cond_grp) if branch.cond_grp else None
                    show_cond = (
                        _parse_cond_grp(branch.show_cond) if branch.show_cond else None
                    )
                    enable_cond = (
                        _parse_cond_grp(branch.enable_cond)
                        if branch.enable_cond
                        else None
                    )
                    options.append(
                        processed_types.CoopChoiceOption(
                            prompt=prompt,
                            steps=branch_steps,
                            cond=cond,
                            show_cond=show_cond,
                            enable_cond=enable_cond,
                        )
                    )
                if options:
                    steps.append(
                        processed_types.CoopStep(
                            talk=None,
                            choice=processed_types.CoopChoice(options=options),
                            ending=None,
                        )
                    )
            case coop_graph.EndStep(save_point_id=save_point_id):
                steps.append(
                    processed_types.CoopStep(
                        talk=None,
                        choice=None,
                        ending=processed_types.EndingInfo(save_point_id=save_point_id),
                    )
                )
    return steps


def get_hangout_info(
    quest_id: id_types.QuestId, *, data_repo: repo.DataRepo
) -> processed_types.HangoutInfo | None:
    """Assemble a hangout quest's play-ordered Coop story dialogue, or None if empty.

    ``quest_id`` is always a hangout quest (the ``Hangouts`` renderable discovers
    them from ``build_hangout_quest_to_stories``), so its stories and main-quest
    entry are indexed strictly.
    """
    stories = data_repo.build_hangout_quest_to_stories()[quest_id]

    text_map = data_repo.text_map_tracker()
    main_quest = data_repo.load_main_quest_excel_config_data()[quest_id]
    quest_title = (
        text_map.get_optional(main_quest["titleTextMapHash"]) or f"Hangout {quest_id}"
    )

    primary_character: str | None = None
    if (
        avatar_id := data_repo.build_coop_chapter_to_avatar_mapping().get(
            main_quest["chapterId"]
        )
    ) is not None:
        primary_character = data_repo.build_avatar_id_to_name_mapping().get(avatar_id)

    coop_story_mapping = data_repo.build_coop_story_mapping()
    graph_mapping = data_repo.build_coop_story_graph_mapping()
    dialog_content_hashes = data_repo.get_dialog_id_to_content_hash_mapping()

    story_infos: list[processed_types.CoopStoryInfo] = []
    for coop_story_id in stories:
        local_talk_id_to_path = {
            int(pathlib.Path(path).stem.split("_", 1)[1]): path
            for path in coop_story_mapping[coop_story_id]
        }
        seen: set[id_types.CoopNodeId] = set()
        steps = (
            _resolve_coop_steps(
                coop_graph.walk_play_order(graph),
                local_talk_id_to_path=local_talk_id_to_path,
                seen=seen,
                text_map=text_map,
                dialog_content_hashes=dialog_content_hashes,
                data_repo=data_repo,
            )
            if (graph := graph_mapping.get(coop_story_id)) is not None
            else []
        )

        for local_talk_id, path in sorted(local_talk_id_to_path.items()):
            if local_talk_id in seen:
                continue
            if (talk_info := _talk.get_talk_info(path, data_repo=data_repo)).text:
                steps.append(
                    processed_types.CoopStep(talk=talk_info, choice=None, ending=None)
                )

        if steps:
            story_infos.append(
                processed_types.CoopStoryInfo(coop_story_id=coop_story_id, steps=steps)
            )

    if not story_infos:
        return None

    return processed_types.HangoutInfo(
        quest_id=quest_id,
        quest_title=quest_title,
        primary_character=primary_character,
        stories=story_infos,
    )


def _render_cond(cond: processed_types.CondGrp) -> str:
    """Render a CondGrp into a human-readable inline string."""
    parts = [_render_cond_entry(e) for e in cond.conds]
    joiner = (
        " and "
        if cond.logic == "LOGIC_AND"
        else " or " if cond.logic == "LOGIC_OR" else ", "
    )
    return joiner.join(parts)


def _render_cond_entry(entry: processed_types.CondEntry) -> str:
    """Render a single cond entry as TYPE [param, ...]."""
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

        next_marker = "*→ End of conversation*"
        for step in option.steps:
            if step.talk is not None:
                lines.extend(_talk.render_talk_content(step.talk, language))
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
            talk_lines = _talk.render_talk_content(step.talk, language)
            if talk_lines:
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

        fork_counter: list[int] = [0]
        fork_map = _assign_fork_numbers(story.steps, fork_counter)
        content_lines.extend(_render_coop_steps(story.steps, language, fork_map))

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_HANGOUT,
            title=title,
            id=hangout.quest_id,
            relative_path=f"{text_types.TextCategory.AGD_HANGOUT.value}/{filename}",
        ),
        content="\n".join(content_lines).rstrip(),
    )
