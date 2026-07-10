"""Talk group processing and rendering."""

import collections
import re
from typing import assert_never

from istaroth import utils
from istaroth.agd import (
    first_seen,
    id_types,
    issues,
    localization,
    processed_types,
    repo,
    talk_parsing,
)
from istaroth.agd.renderables import _talk as _talk
from istaroth.text import types as text_types

_SPEAKER_TITLE_LIMIT = 3

_COMPOSITE_ROLE_PATTERN = re.compile(r"(.+) \((.+)\)")


def get_talk_group_info(
    talk_group_type: talk_parsing.TalkGroupType,
    talk_group_id: talk_parsing.TalkGroupId,
    *,
    data_repo: repo.DataRepo,
) -> processed_types.TalkGroupInfo:
    """Get all talk info for talks in an activity group."""
    talk_group_path = data_repo.build_talk_group_mapping()[
        (talk_group_type, talk_group_id)
    ]
    talk_group_data = data_repo.load_talk_group_data(talk_group_path)

    talks = []
    talk_ids = list[id_types.TalkId]()
    for talk_entry in talk_group_data["talks"]:
        talk_id = int(talk_entry["id"])

        try:
            talk_info = _talk.get_talk_info_by_id(talk_id, data_repo=data_repo)
        except ValueError:
            issues.record(issues.IssueType.MISSING_TALK, str(talk_id))
            continue

        next_talks = list[processed_types.TalkInfo]()
        next_talk_ids = list[id_types.TalkId]()
        for next_talk_id in talk_entry.get("nextTalks", []):
            try:
                next_talk_info = _talk.get_talk_info_by_id(
                    int(next_talk_id), data_repo=data_repo
                )
            except ValueError:
                issues.record(issues.IssueType.MISSING_TALK, str(next_talk_id))
                continue
            if next_talk_info.text:
                next_talks.append(next_talk_info)
                next_talk_ids.append(int(next_talk_id))

        if talk_info.text:
            talks.append((talk_info, next_talks))
            talk_ids.extend([talk_id, *next_talk_ids])

    return processed_types.TalkGroupInfo(talks=talks, talk_ids=talk_ids)


def derive_speaker_group_name(
    talk_group_info: processed_types.TalkGroupInfo,
    language: localization.Language,
) -> str | None:
    """Title from the group's most talkative named speakers, or None if none.

    Generic speakers (player, Paimon, black-screen text, ``???``,
    unresolved-role and missing-talk placeholders) carry no title signal and
    are dropped; dev/test-named roles arrive already ``skip``-flagged. The top
    ``_SPEAKER_TITLE_LIMIT`` names by line count are joined with `` / ``, with
    a trailing ``...`` when more named speakers exist.
    """
    roles = localization.get_localized_role_names(language)
    generic = {
        roles.player,
        roles.mate_avatar,
        roles.black_screen,
        roles.paimon,
        _talk.MISSING_TALK_ROLE,
        "???",
        "？？？",
    }
    speakers = collections.Counter[str]()
    for talk, next_talks in talk_group_info.talks:
        for talk_info in (talk, *next_talks):
            for talk_text in talk_info.text:
                if talk_text.skip or (name := talk_text.role) is None:
                    continue
                # A role rendered as "X (Y)" is _talk's by-role/by-name-hash
                # mismatch composite; count its more specific half so e.g.
                # "旅行者 (观察花卉)" titles as "观察花卉" and "遗迹的铭文 (铭文)"
                # dedups with a plain "遗迹的铭文".
                if (m := _COMPOSITE_ROLE_PATTERN.fullmatch(name)) is not None:
                    name = m.group(2) if m.group(1) in generic else m.group(1)
                if name in generic or name.startswith(roles.unknown_role):
                    continue
                speakers[name] += 1
    if not speakers:
        return None
    top = [name for name, _ in speakers.most_common(_SPEAKER_TITLE_LIMIT)]
    if len(speakers) > _SPEAKER_TITLE_LIMIT:
        top.append("...")
    return " / ".join(top)


def render_talk_group(
    talk_group_type: talk_parsing.TalkGroupType,
    talk_group_id: str,
    talk_group_info: processed_types.TalkGroupInfo,
    language: localization.Language,
    *,
    group_name: str | None = None,
    first_seen_index: first_seen.FirstSeenIndex,
) -> processed_types.RenderedItem:
    """Render multiple talks from an activity group into a single file."""
    safe_type = utils.make_safe_filename_part(str(talk_group_type))
    filename = f"{talk_group_id}_{safe_type}.txt"

    title = (
        f"{group_name} ({talk_group_type} {talk_group_id})"
        if group_name is not None
        else f"{talk_group_type} - {talk_group_id}"
    )

    content_lines = [f"# Talk Group: {title}\n"]

    for i, (talk, next_talks) in enumerate(talk_group_info.talks):
        content_lines.append(f"## Talk {i}\n")
        content_lines.extend(_talk.render_talk_content(talk, language))
        content_lines.append("")

        for j, next_talk in enumerate(next_talks):
            content_lines.append(f"### Talk {i} related talk {j}\n")
            content_lines.extend(_talk.render_talk_content(next_talk, language))
            content_lines.append("")

    rendered_content = "\n".join(content_lines).rstrip()

    match talk_group_type:
        case "GadgetGroup":
            config_id, group_id = talk_parsing.parse_gadget_group_composite_id(
                talk_group_id
            )
            metadata_id = talk_parsing.gadget_group_composite_id(config_id, group_id)
        case "ActivityGroup":
            metadata_id = talk_parsing.activity_group_metadata_id(int(talk_group_id))
        case "NpcGroup":
            metadata_id = int(talk_group_id)
        case _:
            assert_never(talk_group_type)

    min_version, max_version = first_seen_index.resolve(
        [
            first_seen.SourceId(first_seen.SourceDomain.TALK, talk_id)
            for talk_id in talk_group_info.talk_ids
        ]
    )
    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_TALK_GROUP,
            title=title,
            id=metadata_id,
            relative_path=f"{text_types.TextCategory.AGD_TALK_GROUP.value}/{filename}",
            min_version=min_version,
            max_version=max_version,
        ),
        content=rendered_content,
    )
