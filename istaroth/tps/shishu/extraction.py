"""PDF extraction to markdown using pymupdf4llm."""

from pathlib import Path

import pymupdf4llm


def pdf_to_markdown(pdf_path: str | Path, *, show_progress: bool = False) -> str:
    """Convert PDF to markdown text."""
    return pymupdf4llm.to_markdown(str(pdf_path), show_progress=show_progress)
