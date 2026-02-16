"""PDF extraction to markdown using marker-pdf."""

import re
from pathlib import Path

from marker import models as marker_models
from marker import output as marker_output
from marker.converters import pdf as marker_pdf


def pdf_to_markdown(pdf_path: str | Path) -> str:
    """Convert PDF to markdown text. Removes page-number lines and collapses excessive newlines."""
    converter = marker_pdf.PdfConverter(artifact_dict=marker_models.create_model_dict())
    rendered = converter(str(pdf_path))
    text, _, _ = marker_output.text_from_rendered(rendered)
    lines = [
        line for line in text.splitlines() if not re.fullmatch(r"\d+", line.strip())
    ]
    return re.sub(r"\n{2,}", "\n", "\n".join(lines))
