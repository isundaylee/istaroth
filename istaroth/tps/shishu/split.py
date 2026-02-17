"""Split markdown by level-2 heading - each ## starts a new chapter."""

import re
from pathlib import Path

from istaroth import utils

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_H2_RE = re.compile(r"^#{1,2}\s+(.+)$")

_SENTINEL_START = "提瓦特基本设定"
_SENTINEL_END = "其他内容"


def _clean_title(raw: str) -> str:
    """Strip HTML tags and collapse whitespace from a heading title."""
    return re.sub(r"\s+", " ", _HTML_TAG_RE.sub("", raw)).strip()


def _find_heading(headings: list[tuple[int, str]], needle: str) -> int:
    """Return index into headings list whose title contains needle, or raise."""
    for i, (_, title) in enumerate(headings):
        if needle in title:
            return i
    raise ValueError(f"Could not find heading containing {needle!r}")


def split_markdown_by_headings(
    md_path: str | Path,
    out_dir: str | Path,
) -> int:
    """Split markdown on ## headings, cleaning HTML spans. Returns number of files written."""
    md_path = Path(md_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = md_path.read_text(encoding="utf-8").splitlines()

    headings: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if m := _H2_RE.match(line):
            headings.append((i, _clean_title(m.group(1))))

    start_i = _find_heading(headings, _SENTINEL_START)
    end_i = _find_heading(headings, _SENTINEL_END)

    # "前言": everything before _SENTINEL_START
    preamble = "\n".join(lines[: headings[start_i][0]])
    # "其他内容": everything from _SENTINEL_END heading to EOF
    other = "\n".join(lines[headings[end_i][0] :])
    # Main chapters: from start_i up to (not including) end_i
    main_headings = headings[start_i:end_i]

    chapters: list[tuple[str, str]] = [("前言", preamble)]
    for idx, (line_idx, title) in enumerate(main_headings):
        end_line = (
            main_headings[idx + 1][0]
            if idx + 1 < len(main_headings)
            else headings[end_i][0]
        )
        chapters.append((title, "\n".join(lines[line_idx:end_line])))
    chapters.append((_SENTINEL_END, other))

    pad = len(str(len(chapters)))
    for idx, (title, chunk) in enumerate(chapters):
        part = utils.make_safe_filename_part(title, max_length=75) or "untitled"
        fname = f"{idx + 1:0{pad}d}_{part}.md"
        (out_dir / fname).write_text(chunk + "\n", encoding="utf-8")

    return len(chapters)
