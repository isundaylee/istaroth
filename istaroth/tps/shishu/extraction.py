"""PDF extraction to markdown using pymupdf4llm."""

import re
from pathlib import Path

import pymupdf4llm


def pdf_to_markdown(pdf_path: str | Path, *, show_progress: bool = False) -> str:
    """Convert PDF to markdown text. Removes page-number lines and collapses excessive newlines."""
    text = pymupdf4llm.to_markdown(str(pdf_path), show_progress=show_progress)
    lines = [
        line for line in text.splitlines() if not re.fullmatch(r"\d+", line.strip())
    ]
    return re.sub(r"\n{2,}", "\n", "\n".join(lines))
