"""Processing functions for AGD data."""

import itertools
import json
import pathlib
import typing

from istaroth.agd import localization, repo, talk_parsing, text_utils, types

# Priority of the signals that hint where a quest talk plays, lowest to highest.
# FINISH_PLOT is a plot marker whose param often collides with an unrelated talk
# id via the shared <questId><incremental> numbering, so it is least reliable.
# COMPLETE_TALK / COMPLETE_ANY_TALK name the talk that completes a step, so they
# are authoritative. A talk's beginCond names where it actually starts playing,
# so it wins outright when it confirms a step that already references the talk.
_HINT_PRIORITY_FINISH_PLOT = 1
_HINT_PRIORITY_COMPLETE_TALK = 2
_HINT_PRIORITY_BEGIN_COND = 3


class _PlacementHint(typing.NamedTuple):
    """A candidate quest step (`order`) for a talk, with its signal `priority`."""

    order: int
    priority: int


def get_readable_metadata(
    readable_path: str, *, data_repo: repo.DataRepo
) -> types.ReadableMetadata:
    """Retrieve metadata for a readable file."""
    # Extract readable identifier from path (e.g., "Book100" or "Weapon11101" from path)
    language_short = data_repo.language_short
    path_obj = pathlib.Path(readable_path)
    readable_stem = path_obj.stem
    readable_id = readable_stem.removesuffix(f"_{language_short}")

    # Load required data files
    localization_data = data_repo.load_localization_excel_config_data()
    document_data = data_repo.load_document_excel_config_data()
    text_map = data_repo.load_text_map()

    # Step 1: Find localization ID for the readable
    for entry in localization_data:
        # Look through all fields to find one with a path ending in the target language_short
        for _, path_value in entry.items():
            if not isinstance(path_value, str):
                continue

            # CHS format: ART/UI/Readable/CHS/Book711
            # ENG format: ART/UI/Readable/EN/Book711_EN
            path = pathlib.Path(path_value)
            if (
                # Is it the right readable?
                (path.name == readable_stem)
                # Is it the right language?
                and (
                    path_value.endswith(f"_{language_short}")
                    or (language_short in path.parts)
                )
            ):
                localization_id = entry["id"]
                break
        else:
            continue
        break
    else:
        raise ValueError(f"Localization ID not found for readable: {readable_id}")

    # Step 2: Find document entry using localization ID
    for doc_item in document_data:
        if localization_id in list(
            itertools.chain(
                doc_item.get("CUSTOM_addlLocalID", []),
                doc_item["questContentLocalizedId"],
                doc_item["questIDList"],
            )
        ):
            # Step 3: Get title from document's titleTextMapHash
            title_hash = str(doc_item["titleTextMapHash"])
            title = text_map.get(title_hash, "Unknown Title")
            break
    else:
        title = f"Unknown Title"

    return types.ReadableMetadata(localization_id=localization_id, title=title)


def get_talk_info_by_id(
    talk_id_str: str, *, data_repo: repo.DataRepo
) -> types.TalkInfo:
    """Retrieve talk information by talk ID."""
    # Get talk file path through tracker (this automatically tracks access)
    talk_tracker = data_repo.build_talk_tracker()
    talk_file_path = talk_tracker.get_talk_file_path(talk_id_str)

    if talk_file_path is None:
        raise ValueError(f"Talk ID {talk_id_str} not found")

    return get_talk_info(talk_file_path, data_repo=data_repo)


def get_talk_info(talk_path: str, *, data_repo: repo.DataRepo) -> types.TalkInfo:
    """Retrieve talk information from talk file."""
    # Load talk data
    talk_data = data_repo.load_talk_data(talk_path)

    if (dialog_list := talk_data.get("dialogList")) is None:
        return types.TalkInfo(text=[])

    # Load supporting data
    text_map = data_repo.load_text_map()

    # Get cached mappings
    npc_id_to_name = data_repo.get_npc_id_to_name_mapping()
    dialog_id_to_role_hash = data_repo.get_dialog_id_to_role_name_hash_mapping()

    # Get localized role names for fallbacks
    localized_roles = localization.get_localized_role_names(data_repo.language)

    def _get_role_name_by_text_map_hash(
        dialog_item: types.TalkDialogItem,
    ) -> str | None:
        dialog_id = dialog_item["id"]
        role_name_hash = dialog_item.get(
            "talkRoleNameTextMapHash"
        ) or dialog_id_to_role_hash.get(dialog_id)

        return (
            None
            if role_name_hash is None
            else text_map.get_optional(str(role_name_hash))
        )

    def _get_role_name_by_role(talk_role: types.TalkRole) -> str | None:
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

    def _get_role_name(dialog_item: types.TalkDialogItem) -> str:
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

        return (
            by_name_hash or by_role or f"{localized_roles.unknown_role} ({role_type})"
        )

    # Process dialog items
    talk_texts = []
    for dialog_item in dialog_list:
        content_hash = str(dialog_item["talkContentTextMapHash"])
        next_dialog_ids = dialog_item.get("nextDialogs", [])
        talk_texts.append(
            types.TalkText(
                role=_get_role_name(dialog_item),
                message=text_map.get(content_hash, f"Missing text ({content_hash})"),
                next_dialog_ids=next_dialog_ids,
                dialog_id=dialog_item["id"],
            )
        )

    return types.TalkInfo(text=talk_texts)


def _resolve_authoritative_talk(
    talk_id: str, *, data_repo: repo.DataRepo
) -> types.TalkInfo:
    """Resolve a talk pointed at by an authoritative finish condition.

    COMPLETE_TALK / COMPLETE_ANY_TALK name the talk that completes a step, so a
    not-found talk is a genuine upstream data gap: surface it inline as a visible
    placeholder rather than dropping the step or failing the whole quest. Any
    other error (an existing talk that fails to parse) still propagates.
    """
    try:
        return get_talk_info_by_id(talk_id, data_repo=data_repo)
    except ValueError:
        return types.TalkInfo(
            text=[
                types.TalkText(
                    role="[Missing Talk]",
                    message=f"Talk {talk_id} could not be retrieved",
                    next_dialog_ids=[],
                    dialog_id=0,
                )
            ]
        )


def _iter_subquest_talks(
    subquest: types.SubQuestItem, *, data_repo: repo.DataRepo
) -> list[tuple[str, int, types.TalkInfo]]:
    """Return (talk_id, hint_priority, TalkInfo) for talks referenced by finish conditions.

    Only the condition types that genuinely reference a talk are handled;
    everything else is an objective step with no talk. COMPLETE_TALK and
    COMPLETE_ANY_TALK name the talk that completes the step, so they are
    authoritative pointers and a missing talk becomes a placeholder. FINISH_PLOT
    is a plot-completion marker whose param is only sometimes a real talk id, so
    a missing talk is skipped instead. See the ``_HINT_PRIORITY_*`` constants.
    """
    talks: list[tuple[str, int, types.TalkInfo]] = []
    for cond in subquest["finishCond"]:
        match cond.get("damageRatio"):
            case "QUEST_CONTENT_COMPLETE_TALK":
                talk_id = str(cond["param"][0])
                talks.append(
                    (
                        talk_id,
                        _HINT_PRIORITY_COMPLETE_TALK,
                        _resolve_authoritative_talk(talk_id, data_repo=data_repo),
                    )
                )
            case "QUEST_CONTENT_COMPLETE_ANY_TALK":
                talks.extend(
                    (
                        talk_id,
                        _HINT_PRIORITY_COMPLETE_TALK,
                        _resolve_authoritative_talk(talk_id, data_repo=data_repo),
                    )
                    for talk_id in cond["CUSTOM_paramStr"].split(",")
                )
            case "QUEST_CONTENT_FINISH_PLOT":
                talk_id = str(cond["param"][0])
                try:
                    talk_info = get_talk_info_by_id(talk_id, data_repo=data_repo)
                except ValueError:
                    continue
                talks.append((talk_id, _HINT_PRIORITY_FINISH_PLOT, talk_info))
    return talks


def _is_hidden_step(desc_hash: int, *, data_repo: repo.DataRepo) -> bool:
    """Whether a subQuest is a dev/test/hidden step (a ``$HIDDEN``/bridge marker).

    Such steps carry meaningless ``order`` numbers, so a talk's ``beginCond``
    pointing at one is an internal trigger rather than a real playback location.
    The markers live only in the CHS (source) desc text, like quest titles.
    """
    return (
        chs := data_repo.load_source_text_map().get_optional(str(desc_hash))
    ) is not None and text_utils.should_skip_text(chs, localization.Language.CHS)


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
    text = data_repo.load_text_map().get_optional(str(desc_hash))
    return text if text and text.strip() else None


def _begin_subquest_order(
    talk_item: types.QuestTalkItem, subid_to_order: dict[int, int]
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


def get_chapter_title(
    chapter: types.ChapterExcelConfigDataItem, *, data_repo: repo.DataRepo
) -> str:
    """Resolve a chapter's display title (chapter number joined with chapter title)."""
    text_map = data_repo.load_text_map()
    return " ".join(
        p
        for p in [
            text_map.get_optional(str(chapter["chapterNumTextMapHash"])),
            text_map.get_optional(str(chapter["chapterTitleTextMapHash"])),
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
        chs_title := data_repo.load_source_text_map().get_optional(str(title_hash))
    ) is None:
        return False
    return text_utils.should_skip_text(chs_title, localization.Language.CHS)


def get_quest_info(
    quest_id: str, *, data_repo: repo.DataRepo
) -> types.QuestInfo | None:
    """Retrieve quest information from quest ID, or None for a test/hidden quest."""
    # Convert quest ID to path
    quest_path = data_repo.build_quest_mapping()[quest_id]
    quest_data = data_repo.load_quest_data(quest_path)
    text_map = data_repo.load_text_map()

    # Resolve quest title and poetic description from their respective hashes.
    title_hash = quest_data["titleTextMapHash"]
    quest_title = text_map.get(str(title_hash), f"Missing title ({title_hash})")

    # Surface the quest description only when it adds something beyond the title:
    # this guard drops empty descriptions and ones that merely repeat the title.
    description = text_map.get_optional(str(quest_data["descTextMapHash"]))
    if description == quest_title:
        description = None

    # Get chapter information
    chapter_title = None
    chapter_id = quest_data["chapterId"]
    if chapter_id:
        chapter_data = data_repo.load_chapter_excel_config_data()

        if (chapter := chapter_data.get(chapter_id)) is None:
            chapter_title = f"Unknown Chapter {chapter_id}"
        else:
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
        str(talk_item["id"]): begin
        for talk_item in quest_data["talks"]
        if (begin := _begin_subquest_order(talk_item, subid_to_order)) is not None
    }

    # Collect every placement hint for every talk, from both sources, into one set.
    # A finish condition names the step a talk COMPLETES (FINISH_PLOT /
    # COMPLETE_TALK priority); a talk's own `beginCond` (from the quest `talks`
    # field) names the step it STARTS playing on — its true location, hence top
    # priority. Track hidden/test steps, whose `order` numbers are meaningless.
    talk_hints: dict[str, list[_PlacementHint]] = {}
    talk_infos: dict[str, types.TalkInfo] = {}
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
    non_subquest_talk_infos: list[types.TalkInfo] = []
    for talk_item in quest_data["talks"]:
        talk_id = str(talk_item["id"])
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
        talk_info = get_talk_info_by_id(talk_id, data_repo=data_repo)
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
        str(talk_item["id"]): idx for idx, talk_item in enumerate(quest_data["talks"])
    }
    placed: dict[str, tuple[int, int, str | None, types.TalkInfo, bool]] = {}
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
                    types.QuestStep(
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
                    types.QuestStep(
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
        if (info := get_talk_info(path, data_repo=data_repo)).text
    ]

    return types.QuestInfo(
        quest_id=quest_id,
        title=quest_title,
        chapter_title=chapter_title,
        description=description,
        steps=steps,
        non_subquest_talks=non_subquest_talk_infos,
        associated_free_talks=associated_free_talks,
    )


def get_character_story_info(
    avatar_id_str: str, *, data_repo: repo.DataRepo
) -> types.CharacterStoryInfo:
    """Get all character story information for a specific character.

    Args:
        avatar_id_str: Avatar ID as string (e.g. "10000032")
        data_repo: Data repository instance
    """
    avatar_id = int(avatar_id_str)

    # Load required data
    text_map = data_repo.load_text_map()
    avatar_data = data_repo.load_avatar_excel_config_data()
    fetter_data = data_repo.load_fetter_story_excel_config_data()

    # Find character name from avatar data
    character_name = "Unknown Character"
    for avatar in avatar_data:
        if avatar["id"] == avatar_id:
            name_hash = avatar.get("nameTextMapHash")
            if name_hash:
                character_name = text_map.get(str(name_hash), "Unknown Character")
            break

    # Collect all stories for this character
    stories = []
    for story in fetter_data:
        if story["avatarId"] == avatar_id:
            # Get story title
            title_hash = story.get("storyTitleTextMapHash")
            title = "Unknown Title"
            if title_hash:
                title = text_map.get(str(title_hash), "Unknown Title")

            # Get story content
            context_hash = story.get("storyContextTextMapHash")
            content = "Story content not found"
            if context_hash:
                content = text_map.get(str(context_hash), "Story content not found")

            stories.append(types.CharacterStory(title=title, content=content))

    return types.CharacterStoryInfo(
        character_name=character_name, stories=stories, avatar_id=avatar_id_str
    )


def get_subtitle_info(
    subtitle_path: str, *, data_repo: repo.DataRepo
) -> types.SubtitleInfo:
    """Parse subtitle file and extract text lines."""
    subtitle_file_path = data_repo.agd_path / subtitle_path
    content = subtitle_file_path.read_text(encoding="utf-8")

    text_lines = []
    for line in content.strip().split("\n"):
        line = line.strip()
        # Skip empty lines, numbers, and timestamp lines
        if line and not line.isdigit() and "-->" not in line:
            text_lines.append(line)

    return types.SubtitleInfo(text_lines=text_lines)


def get_material_info(
    material_id_str: str, *, data_repo: repo.DataRepo
) -> types.MaterialInfo:
    """Get material information for a specific material ID."""

    # Load required data
    text_map = data_repo.load_text_map()
    material_tracker = data_repo.load_material_excel_config_data()

    # Get material data (this automatically tracks access)
    material = material_tracker.get(material_id_str)
    if material is None:
        raise ValueError(f"Material with ID {material_id_str} not found")

    # Get material name
    name_hash = str(material["nameTextMapHash"])
    name = text_map.get(name_hash, "Unknown Material")

    # Get material description
    desc_hash = str(material["descTextMapHash"])
    description = text_map.get(desc_hash, "No description available")

    return types.MaterialInfo(
        material_id=material_id_str, name=name, description=description
    )


def get_voiceline_info(
    avatar_id_str: str, *, data_repo: repo.DataRepo
) -> types.VoicelineInfo:
    """Get all voiceline information for a specific character."""
    avatar_id = int(avatar_id_str)

    # Load required data
    text_map = data_repo.load_text_map()
    avatar_data = data_repo.load_avatar_excel_config_data()
    fetters_data = data_repo.load_fetters_excel_config_data()

    # Find character name from avatar data
    character_name = "Unknown Character"
    for avatar in avatar_data:
        if avatar["id"] == avatar_id:
            name_hash = str(avatar["nameTextMapHash"])
            character_name = text_map.get(name_hash, "Unknown Character")
            break

    # Collect all voicelines for this character
    voicelines = {}
    for fetter in fetters_data:
        if fetter["avatarId"] == avatar_id:
            # Get voiceline title
            title_hash = str(fetter["voiceTitleTextMapHash"])
            title = text_map.get(title_hash, "Unknown Title")

            # Get voiceline content
            content_hash = str(fetter["voiceFileTextTextMapHash"])
            content = text_map.get(content_hash, "")

            if content:  # Only add if there's actual content
                voicelines[title] = content

    return types.VoicelineInfo(
        character_name=character_name, voicelines=voicelines, avatar_id=avatar_id_str
    )


def _get_relic_story_by_story_id(
    story_id: int, *, data_repo: repo.DataRepo
) -> str | None:
    """Resolve a reliquary piece's relic story from its storyId.

    Follows storyId -> DocumentExcelConfigData -> questIDList ->
    LocalizationExcelConfigData -> readable file, returning None when the piece
    has no story (storyId 0, no document, or no readable on disk).
    """
    if story_id == 0:
        return None

    if (
        doc_item := next(
            (
                doc
                for doc in data_repo.load_document_excel_config_data()
                if doc["id"] == story_id
            ),
            None,
        )
    ) is None:
        return None

    localization_ids = set(doc_item["questIDList"])
    language_short = data_repo.language_short
    readables = data_repo.get_readables()
    for entry in data_repo.load_localization_excel_config_data():
        if entry["id"] not in localization_ids:
            continue
        for path_value in entry.values():
            if not isinstance(path_value, str) or not path_value:
                continue
            path = pathlib.Path(path_value)
            if (
                path_value.endswith(f"_{language_short}")
                or language_short in path.parts
            ) and (content := readables.get_content(f"{path.name}.txt")) is not None:
                return content
    return None


def get_artifact_set_info(
    set_id: str, *, data_repo: repo.DataRepo
) -> types.ArtifactSetInfo | None:
    """Get artifact set info, or None if no piece has a story (nothing to render)."""
    # Load required data
    set_data = data_repo.load_reliquary_set_excel_config_data()
    reliquary_data = data_repo.load_reliquary_excel_config_data()
    text_map = data_repo.load_text_map()

    set_id_int = int(set_id)

    # Find the artifact set configuration
    set_config = None
    for set_entry in set_data:
        if set_entry["setId"] == set_id_int:
            set_config = set_entry
            break

    if not set_config:
        # Hard error if set configuration not found
        raise ValueError(f"Artifact set configuration not found for set ID: {set_id}")

    # Get artifact IDs from the set
    artifact_ids = set_config["containsList"]

    # Collect artifact information
    artifacts = list[types.ArtifactInfo]()
    for artifact_id in artifact_ids:
        # Find artifact configuration
        artifact_config = None
        for reliquary in reliquary_data:
            if reliquary["id"] == artifact_id:
                artifact_config = reliquary
                break

        if not artifact_config:
            # Hard error if artifact configuration not found
            raise ValueError(
                f"Artifact configuration not found for artifact ID: {artifact_id} in set {set_id}"
            )

        # Get artifact name and description from text map
        name_hash = str(artifact_config["nameTextMapHash"])
        name = text_map.get(name_hash, f"Unknown Artifact {artifact_id}")

        description = text_map.get(str(artifact_config["descTextMapHash"]), "")

        # Resolve the relic story from the piece's storyId via the document ->
        # localization -> readable chain, rather than assuming the story file
        # number matches the piece's index within the set (which breaks for
        # single-piece "prayer circlet" sets, see issue #65).
        story = (
            _get_relic_story_by_story_id(
                artifact_config["storyId"], data_repo=data_repo
            )
            or ""
        )

        # Create artifact info
        artifact_info = types.ArtifactInfo(
            name=name,
            description=description,
            story=story,
        )
        artifacts.append(artifact_info)

    # Skip sets whose pieces carry no text at all (e.g. hidden set 15000): there is
    # nothing to render, and such sets also lack a set bonus to name them by.
    if not any(artifact.story or artifact.description for artifact in artifacts):
        return None

    # Resolve the set name from the set bonus (equip affix), not the first piece
    affix_id = set_config["equipAffixId"]
    if (
        affix_name_hash := next(
            (
                str(affix["nameTextMapHash"])
                for affix in data_repo.load_equip_affix_excel_config_data()
                if affix["id"] == affix_id
            ),
            None,
        )
    ) is None:
        raise ValueError(f"Equip affix {affix_id} not found for set {set_id}")
    if (set_name := text_map.get_optional(affix_name_hash)) is None:
        raise ValueError(
            f"Set name not found for affix {affix_id} (hash {affix_name_hash}) in set {set_id}"
        )
    return types.ArtifactSetInfo(set_name=set_name, set_id=set_id, artifacts=artifacts)


def get_talk_group_info(
    talk_group_type: talk_parsing.TalkGroupType,
    talk_group_id: str,
    *,
    data_repo: repo.DataRepo,
) -> types.TalkGroupInfo:
    """Get all talk info for talks in an activity group."""
    # Get ActivityGroup JSON file path from mapping
    talk_group_path = data_repo.build_talk_group_mapping()[
        (talk_group_type, talk_group_id)
    ]
    talk_group_data = data_repo.load_talk_group_data(talk_group_path)

    # Extract talk IDs and get talk info for each
    talks = []
    for talk_entry in talk_group_data["talks"]:
        talk_id = str(talk_entry["id"])

        # Get talk info using existing function
        try:
            talk_info = get_talk_info_by_id(talk_id, data_repo=data_repo)
        except Exception:
            raise RuntimeError(f"Failed to get talk info for talk ID: {talk_id}")

        next_talks = list[types.TalkInfo]()
        for next_talk_id in talk_entry.get("nextTalks", []):
            try:
                next_talk_info = get_talk_info_by_id(
                    str(next_talk_id), data_repo=data_repo
                )
            except Exception:
                raise RuntimeError(
                    f"Failed to get talk info for talk ID: {next_talk_id}"
                )
            if next_talk_info.text:
                next_talks.append(next_talk_info)

        # Only include if talk has content
        if talk_info.text:
            talks.append((talk_info, next_talks))

    return types.TalkGroupInfo(talks=talks)
