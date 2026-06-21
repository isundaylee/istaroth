"""Quest processing and rendering."""

import typing
from collections import defaultdict

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
from istaroth.agd.renderables import _talk as _talk
from istaroth.text import types as text_types

# Priority of the signals that hint where a quest talk plays, lowest to highest.
_HINT_PRIORITY_FINISH_PLOT = 1
_HINT_PRIORITY_COMPLETE_TALK = 2
_HINT_PRIORITY_BEGIN_COND = 3


class _PlacementHint(typing.NamedTuple):
    order: int
    priority: int


def get_chapter_title(
    chapter: agd_types.ChapterExcelConfigDataItem, *, data_repo: repo.DataRepo
) -> str:
    """Resolve a chapter's display title."""
    text_map = data_repo.load_text_map()
    return " ".join(
        p
        for p in [
            text_map.get_optional(chapter["chapterNumTextMapHash"]),
            text_map.get_optional(chapter["chapterTitleTextMapHash"]),
        ]
        if p is not None
    )


def _is_test_or_hidden_title(title_hash: int, *, data_repo: repo.DataRepo) -> bool:
    if (chs_title := data_repo.load_source_text_map().get_optional(title_hash)) is None:
        return False
    return text_utils.should_skip_text(chs_title, localization.Language.CHS)


def _begin_subquest_order(
    talk_item: agd_types.QuestTalkItem, subid_to_order: dict[id_types.SubQuestId, int]
) -> int | None:
    orders = [
        subid_to_order[sub]
        for cond in talk_item["beginCond"]
        if cond["_type"] == "QUEST_COND_STATE_EQUAL"
        and len(param := cond["_param"]) > 1
        and param[1] == "2"
        and (sub := int(param[0])) in subid_to_order
    ]
    return max(orders) if orders else None


def _resolve_step_description(
    desc_hash: int, *, data_repo: repo.DataRepo
) -> str | None:
    if _is_hidden_step(desc_hash, data_repo=data_repo):
        return None
    text = data_repo.load_text_map().get_optional(desc_hash)
    return text if text and text.strip() else None


def _is_hidden_step(desc_hash: int, *, data_repo: repo.DataRepo) -> bool:
    return (
        chs := data_repo.load_source_text_map().get_optional(desc_hash)
    ) is not None and text_utils.should_skip_text(chs, localization.Language.CHS)


def _iter_subquest_talks(
    subquest: agd_types.SubQuestItem, *, data_repo: repo.DataRepo
) -> list[tuple[id_types.TalkId, int, processed_types.TalkInfo]]:
    talks: list[tuple[id_types.TalkId, int, processed_types.TalkInfo]] = []
    for cond in subquest["finishCond"]:
        match cond.get("damageRatio"):
            case "QUEST_CONTENT_COMPLETE_TALK":
                talk_id = cond["param"][0]
                talks.append(
                    (
                        talk_id,
                        _HINT_PRIORITY_COMPLETE_TALK,
                        _talk.resolve_authoritative_talk(talk_id, data_repo=data_repo),
                    )
                )
            case "QUEST_CONTENT_COMPLETE_ANY_TALK":
                talks.extend(
                    (
                        talk_id,
                        _HINT_PRIORITY_COMPLETE_TALK,
                        _talk.resolve_authoritative_talk(talk_id, data_repo=data_repo),
                    )
                    for talk_id in map(int, cond["CUSTOM_paramStr"].split(","))
                )
            case "QUEST_CONTENT_FINISH_PLOT":
                talk_id = cond["param"][0]
                try:
                    talk_info = _talk.get_talk_info_by_id(talk_id, data_repo=data_repo)
                except ValueError:
                    continue
                talks.append((talk_id, _HINT_PRIORITY_FINISH_PLOT, talk_info))
    return talks


def get_quest_info(
    quest_id: id_types.QuestId, *, data_repo: repo.DataRepo
) -> processed_types.QuestInfo | None:
    """Retrieve quest information from quest ID, or None for test/hidden quest."""
    quest_path = data_repo.build_quest_mapping()[quest_id]
    quest_data = data_repo.load_quest_data(quest_path)
    text_map = data_repo.load_text_map()

    title_hash = quest_data["titleTextMapHash"]
    if (quest_title := text_map.get_optional(title_hash)) is None:
        issues.record(issues.IssueType.MISSING_QUEST_TITLE, str(title_hash))
        quest_title = f"Missing title ({title_hash})"

    description = text_map.get_optional(quest_data["descTextMapHash"])
    if description == quest_title:
        description = None

    chapter_title = None
    chapter_id = quest_data["chapterId"]
    if chapter_id:
        chapter_data = data_repo.load_chapter_excel_config_data()
        if (chapter := chapter_data.get(chapter_id)) is None:
            raise ValueError(f"Unknown chapter {chapter_id} for quest {quest_path}")
        chapter_title = get_chapter_title(chapter, data_repo=data_repo)

    subid_to_order = {
        subquest["subId"]: subquest["order"] for subquest in quest_data["subQuests"]
    }
    talk_begin_order = {
        talk_item["id"]: begin
        for talk_item in quest_data["talks"]
        if (begin := _begin_subquest_order(talk_item, subid_to_order)) is not None
    }

    talk_hints: dict[id_types.TalkId, list[_PlacementHint]] = {}
    talk_infos: dict[id_types.TalkId, processed_types.TalkInfo] = {}
    order_to_desc: dict[int, str | None] = {}
    hidden_orders: set[int] = set()
    for subquest in quest_data["subQuests"]:
        order_index = subquest["order"]
        desc = _resolve_step_description(
            subquest["descTextMapHash"], data_repo=data_repo
        )
        assert (
            order_index not in order_to_desc
        ), f"duplicate subQuest order {order_index} in quest {quest_id}"
        order_to_desc[order_index] = desc
        if _is_hidden_step(subquest["descTextMapHash"], data_repo=data_repo):
            hidden_orders.add(order_index)
        for talk_id, priority, talk_info in _iter_subquest_talks(
            subquest, data_repo=data_repo
        ):
            talk_hints.setdefault(talk_id, []).append(
                _PlacementHint(order_index, priority)
            )
            talk_infos.setdefault(talk_id, talk_info)

    finish_orders = {
        talk_id: {hint.order for hint in hints} for talk_id, hints in talk_hints.items()
    }

    non_subquest_talk_infos: list[processed_types.TalkInfo] = []
    for talk_item in quest_data["talks"]:
        talk_id = talk_item["id"]
        begin_anchor = (
            begin
            if (begin := talk_begin_order.get(talk_id)) is not None
            and (begin not in hidden_orders or talk_id not in finish_orders)
            else None
        )
        if talk_id in talk_hints:
            if begin_anchor is not None:
                talk_hints[talk_id].append(
                    _PlacementHint(begin_anchor, _HINT_PRIORITY_BEGIN_COND)
                )
            continue
        talk_info = _talk.get_talk_info_by_id(talk_id, data_repo=data_repo)
        if not talk_info.text:
            continue
        if begin_anchor is not None:
            talk_hints[talk_id] = [
                _PlacementHint(begin_anchor, _HINT_PRIORITY_BEGIN_COND)
            ]
            talk_infos[talk_id] = talk_info
        else:
            non_subquest_talk_infos.append(talk_info)

    talk_order = {
        talk_item["id"]: idx for idx, talk_item in enumerate(quest_data["talks"])
    }
    placed: dict[
        id_types.TalkId, tuple[int, int, str | None, processed_types.TalkInfo, bool]
    ] = {}
    for seq, (talk_id, hints) in enumerate(talk_hints.items()):
        best = max(hints, key=lambda h: (h.priority, -h.order))
        is_lead_in = best.order not in finish_orders.get(talk_id, frozenset())
        placed[talk_id] = (
            best.order,
            talk_order[talk_id] if is_lead_in else seq,
            order_to_desc[best.order],
            talk_infos[talk_id],
            is_lead_in,
        )

    owning_orders = {
        order for order, _, _, _, is_lead_in in placed.values() if not is_lead_in
    }
    objective_steps = [
        (order_index, seq, desc)
        for seq, (order_index, desc) in enumerate(order_to_desc.items())
        if desc is not None and order_index not in owning_orders
    ]

    steps = [
        step
        for _, _, _, step in sorted(
            [
                (
                    order_index,
                    0 if is_lead_in else 1,
                    seq,
                    processed_types.QuestStep(
                        order=order_index,
                        is_lead_in=is_lead_in,
                        description=desc,
                        talk=info,
                    ),
                )
                for order_index, seq, desc, info, is_lead_in in placed.values()
                if info.text
            ]
            + [
                (
                    order_index,
                    2,
                    seq,
                    processed_types.QuestStep(
                        order=order_index,
                        is_lead_in=False,
                        description=desc,
                        talk=None,
                    ),
                )
                for order_index, seq, desc in objective_steps
            ],
            key=lambda item: item[:3],
        )
    ]

    if _is_test_or_hidden_title(title_hash, data_repo=data_repo):
        return None

    associated_free_talks = [
        info
        for path in data_repo.build_free_group_mapping().get(quest_id, [])
        if (info := _talk.get_talk_info(path, data_repo=data_repo)).text
    ]

    return processed_types.QuestInfo(
        quest_id=quest_id,
        title=quest_title,
        chapter_title=chapter_title,
        description=description,
        steps=steps,
        non_subquest_talks=non_subquest_talk_infos,
        associated_free_talks=associated_free_talks,
    )


def render_quest(
    quest: processed_types.QuestInfo, language: localization.Language
) -> processed_types.RenderedItem:
    """Render quest information into RAG-suitable format."""
    safe_title = utils.make_safe_filename_part(quest.title)
    filename = f"{quest.quest_id}_{safe_title}.txt"

    content_lines = []
    if quest.chapter_title:
        content_lines.append(f"(Quest is part of chapter: {quest.chapter_title})\n")
    content_lines.append(f"# {quest.title}\n")
    if quest.description:
        content_lines.append(f"{quest.description}\n")

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
            content_lines.extend(_talk.render_talk_content(step.talk, language))
        else:
            content_lines.append(f"\n## Objective {step.order}\n")
            if step.description:
                content_lines.append(f"({step.description})\n")

    if quest.non_subquest_talks:
        content_lines.append("\n## Additional Conversations\n")
        content_lines.append("*Conversations not present as sub-quests.*\n")
        for i, talk in enumerate(quest.non_subquest_talks, 1):
            if len(quest.non_subquest_talks) > 1:
                content_lines.append(f"\n### Additional Talk {i}\n")
            content_lines.extend(_talk.render_talk_content(talk, language))

    if quest.associated_free_talks:
        content_lines.append("\n## Associated Free Talks\n")
        content_lines.append("*Free talks linked to this quest by talk id.*\n")
        for i, talk in enumerate(quest.associated_free_talks, 1):
            if len(quest.associated_free_talks) > 1:
                content_lines.append(f"\n### Free Talk {i}\n")
            content_lines.extend(_talk.render_talk_content(talk, language))

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
