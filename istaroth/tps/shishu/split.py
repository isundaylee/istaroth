"""Split markdown by heading - each heading starts a new chapter."""

import re
from pathlib import Path

from istaroth import utils


def split_markdown_by_headings(
    md_path: str | Path,
    out_dir: str | Path,
) -> int:
    """Split markdown into one file per heading. Returns number of files written."""
    md_path = Path(md_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = md_path.read_text(encoding="utf-8").splitlines()
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$")

    headings: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if m := heading_re.match(line):
            headings.append((i + 1, m.group(2)))

    pad = len(str(len(headings)))
    for idx, (start_ln, title) in enumerate(headings):
        end_ln = headings[idx + 1][0] - 1 if idx + 1 < len(headings) else len(lines)
        start_idx = 0 if idx == 0 else start_ln - 1
        chunk = "\n".join(lines[start_idx:end_ln])
        part = utils.make_safe_filename_part(title, max_length=75) or "untitled"
        fname = f"{idx + 1:0{pad}d}_{part}.md"
        (out_dir / fname).write_text(chunk + "\n", encoding="utf-8")

    return len(headings)
