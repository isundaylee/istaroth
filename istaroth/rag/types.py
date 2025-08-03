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


@attrs.define
class RetrieveOutput:
    """Output from document retrieval containing all scored document groups."""

    results: list[tuple[float, list[Document]]]

    @property
    def total_documents(self) -> int:
        """Total number of documents in the results."""
        return sum(len(docs) for _, docs in self.results)
