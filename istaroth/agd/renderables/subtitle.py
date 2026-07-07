"""Subtitle processing and rendering."""

import hashlib
import pathlib
import re

from istaroth import text_cleanup, utils
from istaroth.agd import (
    first_seen,
    id_types,
    localization,
    processed_types,
    repo,
    text_utils,
)
from istaroth.text import types as text_types

# Quest-id-shaped digit runs in a subtitle file stem (e.g. the "1204205" of
# "Cs_Inazuma_LQ1204205_IntoTheVoid"); shorter runs are variant/sequence markers.
_QUEST_ID_TOKEN_RE = re.compile(r"\d{4,9}")


def get_subtitle_info(
    subtitle_path: str, *, data_repo: repo.DataRepo
) -> processed_types.SubtitleInfo:
    """Parse subtitle file and extract text lines."""
    subtitle_file_path = data_repo.agd_path / subtitle_path
    content = subtitle_file_path.read_text(encoding="utf-8")

    text_lines = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if line and not line.isdigit() and "-->" not in line:
            text_lines.append(text_cleanup.clean_text_markers(line, data_repo.language))

    return processed_types.SubtitleInfo(text_lines=text_lines)


def _main_quest_title(
    quest_id: id_types.QuestId, *, data_repo: repo.DataRepo
) -> str | None:
    """Main-quest title, or None when unknown, untitled, or dev/test-marked.

    Like quest rendering's hidden-quest check, the ``$UNRELEASED``/``$HIDDEN``
    markers live only in the CHS title text, so screen against the CHS source
    map regardless of the output language.
    """
    main_quest = data_repo.load_main_quest_excel_config_data().get(quest_id)
    if main_quest is None:
        return None
    title_hash = main_quest["titleTextMapHash"]
    chs_title = data_repo.build_source_text_map_tracker().get_optional(title_hash)
    if chs_title is not None and text_utils.should_skip_text(
        chs_title, localization.Language.CHS
    ):
        return None
    return data_repo.build_text_map_tracker().get_optional(title_hash)


def _resolve_quest_title(number: int, *, data_repo: repo.DataRepo) -> str | None:
    """Title of the main quest an id-shaped number points at, or None.

    Cutscene ids and filename tokens encode their trigger site in several
    historical shapes; try each interpretation and keep the first that lands on
    a titled main quest: a sub-quest id, a talk id, a main-quest id, then the
    same with trailing digit pairs stripped (dialog ids are ``talkId*100+n``,
    talk ids ``mainQuestId*100+n``, and some ids append both).
    """
    sub_to_main = data_repo.build_sub_quest_to_main_quest_mapping()
    talk_to_quest = data_repo.build_talk_to_quest_mapping()
    for quest_id in (
        sub_to_main.get(number),
        talk_to_quest.get(number),
        number,
        sub_to_main.get(number // 100),
        talk_to_quest.get(number // 100),
        number // 100,
        number // 10000,
    ):
        if quest_id is not None and (
            title := _main_quest_title(quest_id, data_repo=data_repo)
        ):
            return title
    return None


def build_subtitle_title(subtitle_path: str, *, data_repo: repo.DataRepo) -> str:
    """Document title: owning-quest title plus the file stem as disambiguator.

    Resolution prefers the cutscene files that bind the subtitle (via their
    localization ``subtitleId`` or video names); the many videos with no
    cutscene file in AGD fall back to decoding the quest-id token embedded in
    the filename. When nothing resolves (a handful of system videos like the
    game intro), the bare stem remains the title (issue #74).
    """
    stem = pathlib.Path(subtitle_path).stem
    display_stem = stem.removesuffix(f"_{data_repo.language_short}")
    numbers: list[int] = list(
        data_repo.build_subtitle_stem_to_cutscene_ids_mapping().get(stem, [])
    ) + [
        int(token)
        for token in sorted(
            _QUEST_ID_TOKEN_RE.findall(display_stem), key=len, reverse=True
        )
    ]
    for number in numbers:
        if (title := _resolve_quest_title(number, data_repo=data_repo)) is not None:
            return f"{title} ({display_stem})"
    return display_stem


def render_subtitle(
    subtitle_info: processed_types.SubtitleInfo,
    subtitle_path: str,
    title: str,
    *,
    first_seen_index: first_seen.FirstSeenIndex,
) -> processed_types.RenderedItem:
    """Render subtitle content into RAG-suitable format."""
    subtitle_id = int(
        hashlib.sha256(subtitle_path.encode("utf-8")).hexdigest()[:12], base=16
    )

    path_obj = pathlib.Path(subtitle_path)
    safe_name = utils.make_safe_filename_part(path_obj.stem)
    filename = f"{subtitle_id}_{safe_name}.txt"

    content_lines = [f"# {title}\n"]
    content_lines.extend(subtitle_info.text_lines)

    rendered_content = "\n".join(content_lines)

    min_version, max_version = first_seen_index.resolve(
        [first_seen.subtitle_source_id(subtitle_path)]
    )
    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_SUBTITLE,
            title=title,
            id=subtitle_id,
            relative_path=f"{text_types.TextCategory.AGD_SUBTITLE.value}/{filename}",
            min_version=min_version,
            max_version=max_version,
        ),
        content=rendered_content,
    )
