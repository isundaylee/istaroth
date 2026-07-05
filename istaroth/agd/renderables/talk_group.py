"""Talk group processing and rendering."""

from typing import assert_never

from istaroth import utils
from istaroth.agd import (
    issues,
    localization,
    processed_types,
    repo,
    talk_parsing,
)
from istaroth.agd.renderables import _talk as _talk
from istaroth.text import types as text_types


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
    for talk_entry in talk_group_data["talks"]:
        talk_id = int(talk_entry["id"])

        try:
            talk_info = _talk.get_talk_info_by_id(talk_id, data_repo=data_repo)
        except ValueError:
            issues.record(issues.IssueType.MISSING_TALK, str(talk_id))
            continue

        next_talks = list[processed_types.TalkInfo]()
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

        if talk_info.text:
            talks.append((talk_info, next_talks))

    return processed_types.TalkGroupInfo(talks=talks)


def render_talk_group(
    talk_group_type: talk_parsing.TalkGroupType,
    talk_group_id: str,
    talk_group_info: processed_types.TalkGroupInfo,
    language: localization.Language,
    *,
    group_name: str | None = None,
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

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_TALK_GROUP,
            title=title,
            id=metadata_id,
            relative_path=f"{text_types.TextCategory.AGD_TALK_GROUP.value}/{filename}",
        ),
        content=rendered_content,
    )
