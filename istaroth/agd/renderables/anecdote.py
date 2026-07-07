"""Anecdote (Odd Encounter) processing and rendering."""

from istaroth import utils
from istaroth.agd import (
    first_seen,
    id_types,
    issues,
    localization,
    processed_types,
    repo,
)
from istaroth.agd.renderables import _talk as _talk
from istaroth.text import types as text_types


def get_anecdote_info(
    anecdote_id: id_types.AnecdoteId, *, data_repo: repo.DataRepo
) -> processed_types.AnecdoteInfo | None:
    """Assemble an anecdote's blurbs and storyboard talks, or None if talk-less."""
    entry = data_repo.load_anecdote_excel_config_data()[anecdote_id]
    text_map = data_repo.build_text_map_tracker()
    quest_to_talks = data_repo.build_storyboard_quest_to_talk_ids_mapping()

    talks = list[processed_types.TalkInfo]()
    talk_ids = list[id_types.TalkId]()
    for quest_id in entry["questIds"]:
        for talk_id in quest_to_talks.get(quest_id, []):
            try:
                talk_info = _talk.get_talk_info_by_id(talk_id, data_repo=data_repo)
            except ValueError:
                issues.record(issues.IssueType.MISSING_TALK, str(talk_id))
                continue
            # Require a non-skip line: skip-flagged (dev/test) lines are dropped
            # at render time, so an all-skip talk would emit an empty section.
            if any(not text.skip for text in talk_info.text):
                talks.append(talk_info)
                talk_ids.append(talk_id)

    if not talks:
        return None

    return processed_types.AnecdoteInfo(
        anecdote_id=anecdote_id,
        title=text_map.get_optional(entry["titleTextMapHash"])
        or f"Anecdote {anecdote_id}",
        teaser=text_map.get_optional(entry["teaserTextMapHash"]),
        description=text_map.get_optional(entry["descTextMapHash"]),
        talks=talks,
        talk_ids=talk_ids,
    )


def render_anecdote(
    anecdote: processed_types.AnecdoteInfo,
    *,
    language: localization.Language,
    first_seen_index: first_seen.FirstSeenIndex,
) -> processed_types.RenderedItem:
    """Render an anecdote's blurbs and dialogue into a single file."""
    filename = (
        f"{anecdote.anecdote_id}_{utils.make_safe_filename_part(anecdote.title)}.txt"
    )

    content_lines = [f"# {anecdote.title}\n"]
    for blurb in (anecdote.teaser, anecdote.description):
        if blurb is not None:
            content_lines.append(blurb)
            content_lines.append("")

    for i, talk in enumerate(anecdote.talks):
        content_lines.append(f"## Talk {i}\n")
        content_lines.extend(_talk.render_talk_content(talk, language))
        content_lines.append("")

    min_version, max_version = first_seen_index.resolve(
        [
            first_seen.SourceId(first_seen.SourceDomain.TALK, talk_id)
            for talk_id in anecdote.talk_ids
        ]
    )
    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ANECDOTE,
            title=anecdote.title,
            id=anecdote.anecdote_id,
            relative_path=f"{text_types.TextCategory.AGD_ANECDOTE.value}/{filename}",
            min_version=min_version,
            max_version=max_version,
        ),
        content="\n".join(content_lines).rstrip(),
    )
