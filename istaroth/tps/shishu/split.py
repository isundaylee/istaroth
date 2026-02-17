"""Split markdown by level-2 heading - each ## starts a new chapter."""

import re
from pathlib import Path

from istaroth import utils

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_H2_RE = re.compile(r"^#{1,2}\s+(.+)$")


def _clean_title(raw: str) -> str:
    """Strip HTML tags and collapse whitespace from a heading title."""
    return re.sub(r"\s+", " ", _HTML_TAG_RE.sub("", raw)).strip()


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

    pad = len(str(len(headings)))
    for idx, (start_idx, title) in enumerate(headings):
        end_idx = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        chunk_start = 0 if idx == 0 else start_idx
        chunk = "\n".join(lines[chunk_start:end_idx])
        part = utils.make_safe_filename_part(title, max_length=75) or "untitled"
        fname = f"{idx + 1:0{pad}d}_{part}.md"
        (out_dir / fname).write_text(chunk + "\n", encoding="utf-8")

    return len(headings)
