"""Book series processing and rendering."""

from typing import assert_never

from istaroth import utils
from istaroth.agd import (
    id_types,
    localization,
    processed_types,
    repo,
)
from istaroth.agd.renderables import readable as _readable
from istaroth.text import types as text_types


def _render_volume_annotation(
    series_name: str, index: int, total: int, language: localization.Language
) -> str:
    """Render the per-volume series annotation line in the output language."""
    match language:
        case localization.Language.CHS:
            return f"*{series_name}·第 {index} 卷，共 {total} 卷*"
        case localization.Language.ENG:
            return f"*{series_name} — Volume {index} of {total}*"
        case _:
            assert_never(language)


def render_book(
    content: str, metadata: processed_types.ReadableMetadata
) -> processed_types.RenderedItem:
    """Render book content into RAG-suitable format."""
    safe_title = utils.make_safe_filename_part(metadata.title)
    filename = f"{metadata.localization_id}_{safe_title}.txt"
    rendered_content = f"# {metadata.title}\n\n{content}"

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_BOOK,
            title=metadata.title,
            id=metadata.localization_id,
            relative_path=f"{text_types.TextCategory.AGD_BOOK.value}/{filename}",
        ),
        content=rendered_content,
    )


def render_book_series(
    series_info: processed_types.BookSeriesInfo, language: localization.Language
) -> processed_types.RenderedItem:
    """Render a multi-volume book series into a single RAG-suitable file.

    Volumes render in reading order under one series header, each prefixed with an
    annotation line naming the series and the volume's position so a chunk retrieved
    in isolation still carries its series context.
    """
    safe_name = utils.make_safe_filename_part(series_info.series_name)
    filename = f"{series_info.suit_id}_{safe_name}.txt"

    total = len(series_info.volumes)
    content_parts = [f"# {series_info.series_name}"]
    for index, volume in enumerate(series_info.volumes, start=1):
        annotation = _render_volume_annotation(
            series_info.series_name, index, total, language
        )
        content_parts.append(f"## {volume.title}\n\n{annotation}\n\n{volume.content}")

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_BOOK,
            title=series_info.series_name,
            id=series_info.suit_id,
            relative_path=f"{text_types.TextCategory.AGD_BOOK.value}/{filename}",
        ),
        content="\n\n".join(content_parts),
    )


def get_book_series_info(
    suit_id: id_types.BookSuitId, *, data_repo: repo.DataRepo
) -> processed_types.BookSeriesInfo | None:
    """Assemble a multi-volume book series: its name and ordered volume bodies.

    Reading each volume's content marks it accessed, keeping the per-volume files
    out of the standalone Books and generic Readables catch-alls. A grouped volume
    whose readable file is missing raises rather than being silently dropped;
    empty/placeholder/test volumes are filtered the same way standalone books are.
    Returns None if no volume survives filtering.
    """
    if (filenames := data_repo.build_book_series_mapping().get(suit_id)) is None:
        raise ValueError(f"Book suit {suit_id} is not a multi-volume series")

    suit = data_repo.load_book_suit_excel_config_data()[suit_id]
    if (
        series_name := data_repo.text_map_tracker().get_optional(
            suit["suitNameTextMapHash"]
        )
    ) is None:
        raise ValueError(f"Missing series name for book suit {suit_id}")

    volumes = []
    for filename in filenames:
        if (
            loaded := _readable.load_readable(
                f"Readable/{data_repo.language_short}/{filename}", data_repo=data_repo
            )
        ) is None:
            continue
        content, metadata = loaded
        volumes.append(
            processed_types.BookVolumeInfo(title=metadata.title, content=content)
        )
    if not volumes:
        return None
    return processed_types.BookSeriesInfo(
        suit_id=suit_id, series_name=series_name, volumes=volumes
    )
