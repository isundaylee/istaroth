"""Blossom (Rich Ore Reserve) intel-talk processing and rendering."""

from istaroth import utils
from istaroth.agd import (
    agd_types,
    first_seen,
    id_types,
    issues,
    localization,
    processed_types,
    repo,
)
from istaroth.agd.renderables import _talk as _talk
from istaroth.text import types as text_types

_INTEL_SHOW_TYPE = "BLOSSOM_SHOWTYPE_NPCTALK"


def _resolve_text(data_repo: repo.DataRepo, text_hash: id_types.TextMapHash) -> str:
    if (text := data_repo.build_text_map_tracker().get_optional(text_hash)) is None:
        raise ValueError(f"Unresolvable text map hash {text_hash}")
    return text


def _intel_rows(
    data_repo: repo.DataRepo,
) -> list[tuple[agd_types.BlossomRefreshExcelConfigDataItem, list[id_types.TalkId]]]:
    """(refresh, talk ids) pairs for the NPC-intel blossom talk pools."""
    refreshes = data_repo.load_blossom_refresh_excel_config_data()
    return [
        (refresh, row["talkId"])
        for row in data_repo.load_blossom_talk_excel_config_data()
        if (refresh := refreshes[row["refreshId"]])["clientShowType"]
        == _INTEL_SHOW_TYPE
    ]


def list_city_ids(data_repo: repo.DataRepo) -> list[id_types.CityId]:
    """City ids that have NPC-intel blossom talks."""
    return sorted({refresh["cityId"] for refresh, _ in _intel_rows(data_repo)})


def get_blossom_city_info(
    city_id: id_types.CityId, *, data_repo: repo.DataRepo
) -> processed_types.BlossomCityInfo | None:
    """Assemble a region's blossom intel talks, sectioned by ore-type blurb."""
    names = set[str]()
    # Sections key on the resolved blurb text (not its hash): several refreshes
    # share one blurb (e.g. crystal pools at different unlock levels), and even
    # same-text blurbs ship under distinct hashes.
    section_order = dict[str, id_types.BlossomRefreshId]()
    section_talk_ids = dict[str, set[id_types.TalkId]]()
    for refresh, row_talk_ids in _intel_rows(data_repo):
        if refresh["cityId"] != city_id:
            continue
        names.add(_resolve_text(data_repo, refresh["nameTextMapHash"]))
        desc = _resolve_text(data_repo, refresh["descTextMapHash"])
        section_order[desc] = min(section_order.get(desc, refresh["id"]), refresh["id"])
        section_talk_ids.setdefault(desc, set()).update(row_talk_ids)

    # All intel refreshes share the one Rich Ore Reserve name.
    (name,) = names
    city_name = _resolve_text(
        data_repo, data_repo.load_city_config_data()[city_id]["cityNameTextMapHash"]
    )

    sections = list[processed_types.BlossomSection]()
    talk_ids = list[id_types.TalkId]()
    for desc in sorted(section_order, key=section_order.__getitem__):
        talks = list[processed_types.TalkInfo]()
        seen_contents = set[tuple[tuple[str | None, str], ...]]()
        for talk_id in sorted(section_talk_ids[desc]):
            try:
                talk_info = _talk.get_talk_info_by_id(talk_id, data_repo=data_repo)
            except ValueError:
                issues.record(issues.IssueType.MISSING_TALK, str(talk_id))
                continue
            # Require a non-skip line: skip-flagged (dev/test) lines are dropped
            # at render time, so an all-skip talk would emit an empty section.
            # The same intel dialogue repeats verbatim under many talk ids (one
            # per map spawn spot), so keep only the first copy of each script.
            content = tuple(
                (text.role, text.message) for text in talk_info.text if not text.skip
            )
            if content and content not in seen_contents:
                seen_contents.add(content)
                talks.append(talk_info)
                talk_ids.append(talk_id)
        if talks:
            sections.append(
                processed_types.BlossomSection(description=desc, talks=talks)
            )

    if not sections:
        return None

    return processed_types.BlossomCityInfo(
        city_id=city_id,
        title=f"{name} - {city_name}",
        sections=sections,
        talk_ids=talk_ids,
    )


def render_blossom_city(
    blossom_city: processed_types.BlossomCityInfo,
    *,
    language: localization.Language,
    first_seen_index: first_seen.FirstSeenIndex,
) -> processed_types.RenderedItem:
    """Render a region's blossom intel sections into a single file."""
    filename = (
        f"{blossom_city.city_id}_"
        f"{utils.make_safe_filename_part(blossom_city.title)}.txt"
    )

    content_lines = [f"# {blossom_city.title}\n"]
    talk_index = 0
    for section in blossom_city.sections:
        content_lines.append(f"## {section.description}\n")
        for talk in section.talks:
            content_lines.append(f"### Talk {talk_index}\n")
            content_lines.extend(_talk.render_talk_content(talk, language))
            content_lines.append("")
            talk_index += 1

    min_version, max_version = first_seen_index.resolve(
        [
            first_seen.SourceId(first_seen.SourceDomain.TALK, talk_id)
            for talk_id in blossom_city.talk_ids
        ]
    )
    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_BLOSSOM,
            title=blossom_city.title,
            id=blossom_city.city_id,
            relative_path=f"{text_types.TextCategory.AGD_BLOSSOM.value}/{filename}",
            min_version=min_version,
            max_version=max_version,
        ),
        content="\n".join(content_lines).rstrip(),
    )
