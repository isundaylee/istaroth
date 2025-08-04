"""Type definitions for RAG (Retrieval-Augmented Generation) module."""

from typing import Any, TypedDict

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

    def to_langsmith_output(self) -> dict[str, Any]:
        return {
            "page_content": self.document.page_content,
            "type": "Document",
            "metadata": {
                **self.document.metadata,
                "score": self.score,
            },
        }


@attrs.define
class RetrieveOutput:
    """Output from document retrieval containing all scored document groups."""

    results: list[tuple[float, list[Document]]]

    @property
    def total_documents(self) -> int:
        """Total number of documents in the results."""
        return sum(len(docs) for _, docs in self.results)

    def to_langsmith_output(self, formatted_output: str) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "formatted_output": formatted_output,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert RetrieveOutput to dictionary for serialization."""
        return {
            "results": [
                {
                    "score": score,
                    "documents": [
                        {
                            "page_content": doc.page_content,
                            "metadata": doc.metadata,
                        }
                        for doc in documents
                    ],
                }
                for score, documents in self.results
            ]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrieveOutput":
        """Create RetrieveOutput from dictionary."""
        results = []
        for result_data in data["results"]:
            score = result_data["score"]
            documents = [
                Document(
                    page_content=doc_data["page_content"],
                    metadata=doc_data["metadata"],
                )
                for doc_data in result_data["documents"]
            ]
            results.append((score, documents))

        return cls(results=results)
