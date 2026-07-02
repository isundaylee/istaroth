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
    """A candidate quest step (`order`) for a talk, with its signal `priority`."""

    order: int
    priority: int


def get_chapter_title(
    chapter: agd_types.ChapterExcelConfigDataItem, *, data_repo: repo.DataRepo
) -> str:
    """Resolve a chapter's display title (chapter number joined with chapter title)."""
    text_map = data_repo.build_text_map_tracker()
    return " ".join(
        p
        for p in [
            text_map.get_optional(chapter["chapterNumTextMapHash"]),
            text_map.get_optional(chapter["chapterTitleTextMapHash"]),
        ]
        if p is not None
    )


def _is_test_or_hidden_title(title_hash: int, *, data_repo: repo.DataRepo) -> bool:
    """Whether a quest title marks a dev/test/hidden quest to exclude.

    The ``$HIDDEN``/``(test)`` markers live only in the CHS (source) title text,
    so resolve the title against the CHS text map regardless of the output
    language; otherwise non-CHS corpora leak these quests.
    """
    if (
        chs_title := data_repo.build_source_text_map_tracker().get_optional(title_hash)
    ) is None:
        return False
    return text_utils.should_skip_text(chs_title, localization.Language.CHS)


def _begin_subquest_order(
    talk_item: agd_types.QuestTalkItem, subid_to_order: dict[id_types.SubQuestId, int]
) -> int | None:
    """Step order a quest talk begins at (via its ``beginCond``), or None.

    A quest talk plays when ``QUEST_COND_STATE_EQUAL [subId, 2]`` holds (the named
    subquest activated); the remaining beginCond entries are gating conditions
    (quest vars, items, ...) that don't locate the talk. When several activation
    conditions resolve, the talk plays once all hold, i.e. at the latest order.
    Returns None when no activation condition resolves to a subquest of this quest
    (e.g. a cross-quest reference), leaving the talk for non-step placement.
    """
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
    """Resolve a subQuest's objective text, or None when there is none to show.

    A ``0`` hash (the step has no objective), or missing/empty text, yields None;
    test/hidden steps are filtered against the CHS source text (like quest titles)
    so non-CHS corpora exclude the same steps.
    """
    if _is_hidden_step(desc_hash, data_repo=data_repo):
        return None
    text = data_repo.build_text_map_tracker().get_optional(desc_hash)
    return text if text and text.strip() else None


def _is_hidden_step(desc_hash: int, *, data_repo: repo.DataRepo) -> bool:
    """Whether a subQuest is a dev/test/hidden step (a ``$HIDDEN``/bridge marker).

    Such steps carry meaningless ``order`` numbers, so a talk's ``beginCond``
    pointing at one is an internal trigger rather than a real playback location.
    The markers live only in the CHS (source) desc text, like quest titles.
    """
    return (
        chs := data_repo.build_source_text_map_tracker().get_optional(desc_hash)
    ) is not None and text_utils.should_skip_text(chs, localization.Language.CHS)


def _iter_subquest_talks(
    subquest: agd_types.SubQuestItem, *, data_repo: repo.DataRepo
) -> list[tuple[id_types.TalkId, int, processed_types.TalkInfo]]:
    """Return (talk_id, hint_priority, TalkInfo) for talks referenced by finish conditions.

    Only the condition types that genuinely reference a talk are handled;
    everything else is an objective step with no talk. COMPLETE_TALK and
    COMPLETE_ANY_TALK name the talk that completes the step, so they are
    authoritative pointers and a missing talk becomes a placeholder. FINISH_PLOT
    is a plot-completion marker whose param is only sometimes a real talk id, so
    a missing talk is skipped instead. See the ``_HINT_PRIORITY_*`` constants.
    """
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
    """Retrieve quest information from quest ID, or None for a test/hidden quest."""
    # Convert quest ID to path
    quest_path = data_repo.build_quest_mapping()[quest_id]
    quest_data = data_repo.load_quest_data(quest_path)
    text_map = data_repo.build_text_map_tracker()

    # Resolve quest title and poetic description from their respective hashes.
    title_hash = quest_data["titleTextMapHash"]
    if (quest_title := text_map.get_optional(title_hash)) is None:
        issues.record(issues.IssueType.MISSING_QUEST_TITLE, str(title_hash))
        quest_title = f"Missing title ({title_hash})"

    # Surface the quest description only when it adds something beyond the title:
    # this guard drops empty descriptions and ones that merely repeat the title.
    description = text_map.get_optional(quest_data["descTextMapHash"])
    if description == quest_title:
        description = None

    # Get chapter information
    chapter_title = None
    chapter_id = quest_data["chapterId"]
    if chapter_id:
        chapter_data = data_repo.load_chapter_excel_config_data()

        if (chapter := chapter_data.get(chapter_id)) is None:
            raise ValueError(f"Unknown chapter {chapter_id} for quest {quest_path}")
        chapter_title = get_chapter_title(chapter, data_repo=data_repo)

    # Resolve where each talk a quest declares actually plays. A talk's
    # `beginCond` names the subQuest it starts on (its true playback location);
    # quest `talks` entries provide it. The finish-condition param, NOT the subId,
    # names the talk a step references (subId matches a talk id only by coincidence
    # of the shared <questId><incremental> numbering, so it is an unreliable
    # pointer).
    subid_to_order = {
        subquest["subId"]: subquest["order"] for subquest in quest_data["subQuests"]
    }
    talk_begin_order = {
        talk_item["id"]: begin
        for talk_item in quest_data["talks"]
        if (begin := _begin_subquest_order(talk_item, subid_to_order)) is not None
    }

    # Collect every placement hint for every talk, from both sources, into one set.
    # A finish condition names the step a talk COMPLETES (FINISH_PLOT /
    # COMPLETE_TALK priority); a talk's own `beginCond` (from the quest `talks`
    # field) names the step it STARTS playing on — its true location, hence top
    # priority. Track hidden/test steps, whose `order` numbers are meaningless.
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

    # The orders where each talk completes a step (its finish-condition hints); a
    # talk placed elsewhere (at a beginCond order it does not finish) is a lead-in.
    finish_orders = {
        talk_id: {hint.order for hint in hints} for talk_id, hints in talk_hints.items()
    }

    # Fold every quest-declared talk into the same hint set via its beginCond.
    # beginCond is the talk's true start, so a top-priority hint — except when it
    # points at a hidden/test step (an internal trigger), which is ignored only if
    # the talk has a real finishCond placement to fall back on (otherwise beginCond
    # is the sole signal). A talk with neither a finish condition nor a usable
    # beginCond has no anchor in this quest and is rendered in a separate section.
    non_subquest_talk_infos: list[processed_types.TalkInfo] = []
    for talk_item in quest_data["talks"]:
        talk_id = talk_item["id"]
        # The order to anchor this talk's beginCond hint at, or None for no usable
        # beginCond: a hidden/test trigger is ignored only when a finishCond
        # placement can stand in for it.
        begin_anchor = (
            begin
            if (begin := talk_begin_order.get(talk_id)) is not None
            and (begin not in hidden_orders or talk_id not in finish_orders)
            else None
        )
        # Already hinted by a finish condition: just add the beginCond hint (if
        # any) and move on. Such a talk is anchored to this quest, so it must never
        # fall through to `non_subquest_talk_infos` below.
        if talk_id in talk_hints:
            if begin_anchor is not None:
                talk_hints[talk_id].append(
                    _PlacementHint(begin_anchor, _HINT_PRIORITY_BEGIN_COND)
                )
            continue
        # A talk the quest declares must load; a failure is a genuine data gap.
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

    # Place each talk at its highest-priority hinted step (earliest order breaks
    # ties). A talk placed at a step it does not itself finish is a lead-in there
    # (it plays during the step but another talk completes it). `desc` is that
    # step's objective text. `tiebreak` orders talks sharing a step: completing
    # talks by finishCond discovery order, lead-ins by their order in the quest
    # `talks` field (a lead-in always has a beginCond, so it is listed there).
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

    # A subQuest whose objective text is usable but that no talk *completes*
    # becomes a non-dialogue objective step — covering subQuests with no talk,
    # ones whose only (FINISH_PLOT) talk relocated, and ones hosting only lead-ins,
    # so the step keeps its objective line instead of vanishing with the talk.
    owning_orders = {
        order for order, _, _, _, is_lead_in in placed.values() if not is_lead_in
    }
    objective_steps = [
        (order_index, seq, desc)
        for seq, (order_index, desc) in enumerate(order_to_desc.items())
        if desc is not None and order_index not in owning_orders
    ]

    # Interleave talk and objective steps by `order`. Within one order, lead-ins
    # (group 0) precede the completing talk (group 1). Objectives (group 2) arise
    # only from talk-less subQuests, and `order` is unique per quest (asserted
    # above), so an objective never shares an order with a talk.
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

    # Exclude dev/test/hidden quests. Checked after the talks above are resolved
    # (which marks them accessed) so this quest's dialogue is also kept out of
    # the standalone agd_talk pass, not just out of agd_quest.
    if _is_test_or_hidden_title(title_hash, data_repo=data_repo):
        return None

    # FreeGroup "free talks" attached to this quest by talkId numbering (paths
    # arrive pre-sorted by talkId); rendered in a separate section.
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
            content_lines.extend(_talk.render_talk_content(step.talk, language))
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
            content_lines.extend(_talk.render_talk_content(talk, language))

    # Render FreeGroup "free talks" attached to this quest by talkId numbering.
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
