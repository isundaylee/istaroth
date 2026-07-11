"""Activity (event) loose-talk processing and rendering."""

import collections

from istaroth import utils
from istaroth.agd import first_seen, id_types, localization, processed_types, repo
from istaroth.agd.renderables import _talk as _talk
from istaroth.text import types as text_types

_ACTIVITY_LOAD_TYPE = "TALK_ACTIVITY"


def list_loose_talk_ids_by_activity(
    data_repo: repo.DataRepo, *, used_talk_ids: set[id_types.TalkId]
) -> dict[id_types.ActivityId, list[id_types.TalkId]]:
    """Leftover ``TALK_ACTIVITY`` talk ids grouped by their owning activity.

    For ``TALK_ACTIVITY`` entries the excel ``questId`` field holds the owning
    activity id (every current entry resolves in NewActivityExcelConfigData),
    matching the activity referenced by their ``QUEST_COND_ACTIVITY_CLIENT_COND``
    begin conditions.
    """
    available = data_repo.build_talk_tracker().get_all_ids()
    grouped = collections.defaultdict[id_types.ActivityId, list[id_types.TalkId]](list)
    for entry in data_repo.load_talk_excel_config_data():
        if (
            entry.loadType == _ACTIVITY_LOAD_TYPE
            and (talk_id := entry.id) in available
            and talk_id not in used_talk_ids
        ):
            grouped[entry.questId].append(talk_id)
    return {activity_id: sorted(talk_ids) for activity_id, talk_ids in grouped.items()}


def get_activity_talks_info(
    activity_id: id_types.ActivityId,
    *,
    data_repo: repo.DataRepo,
    used_talk_ids: set[id_types.TalkId],
) -> processed_types.ActivityTalksInfo | None:
    """Assemble an activity's loose talks, or None when none have content."""
    talks = list[processed_types.TalkInfo]()
    talk_ids = list[id_types.TalkId]()
    for talk_id in list_loose_talk_ids_by_activity(
        data_repo, used_talk_ids=used_talk_ids
    )[activity_id]:
        talk_info = _talk.get_talk_info_by_id(talk_id, data_repo=data_repo)
        # Require a non-skip line: skip-flagged (dev/test) lines are dropped at
        # render time, so an all-skip talk would emit an empty section. Loading
        # the talk above still claims its id, so dropped talks don't leak back
        # into the loose Talks pass.
        if talk_info.has_non_skip_text:
            talks.append(talk_info)
            talk_ids.append(talk_id)

    if not talks:
        return None

    return processed_types.ActivityTalksInfo(
        activity_id=activity_id,
        title=data_repo.build_activity_id_to_name_mapping()[activity_id],
        talks=talks,
        talk_ids=talk_ids,
    )


def render_activity_talks(
    activity: processed_types.ActivityTalksInfo,
    *,
    language: localization.Language,
    first_seen_index: first_seen.FirstSeenIndex,
) -> processed_types.RenderedItem:
    """Render an activity's loose talks into a single file."""
    filename = (
        f"{activity.activity_id}_{utils.make_safe_filename_part(activity.title)}.txt"
    )

    content_lines = [f"# {activity.title}\n"]
    for i, talk in enumerate(activity.talks):
        content_lines.append(f"## Talk {i}\n")
        content_lines.extend(_talk.render_talk_content(talk, language))
        content_lines.append("")

    min_version, max_version = first_seen_index.resolve(
        [
            first_seen.SourceId(first_seen.SourceDomain.TALK, talk_id)
            for talk_id in activity.talk_ids
        ]
    )
    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ACTIVITY,
            title=activity.title,
            id=activity.activity_id,
            relative_path=f"{text_types.TextCategory.AGD_ACTIVITY.value}/{filename}",
            min_version=min_version,
            max_version=max_version,
        ),
        content="\n".join(content_lines).rstrip(),
    )
