"""Type definitions for RAG (Retrieval-Augmented Generation) module."""

from typing import TypedDict

import attrs
from langchain_core.documents import Document


class DocumentMetadata(TypedDict):
    """Metadata for document chunks in the RAG pipeline."""

    source: str
    type: str
    filename: str
    file_id: str
    chunk_index: int


@attrs.define
class ScoredDocument:
    """Document with similarity score."""

    document: Document
    score: float
