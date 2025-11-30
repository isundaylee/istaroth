"""Type definitions for RAG (Retrieval-Augmented Generation) module."""

import os
from typing import Any, TypedDict

import attrs
from langchain_core.documents import Document


class DocumentMetadata(TypedDict):
    """Metadata for document chunks in the RAG pipeline."""

    source: str
    type: str
    path: str
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
class RetrieveQuery:
    query: str
    k: int
    chunk_context: int

    def to_dict(self) -> dict[str, Any]:
        """Convert RetrieveQuery to dictionary for serialization."""
        return {
            "query": self.query,
            "k": self.k,
            "chunk_context": self.chunk_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrieveQuery":
        """Create RetrieveQuery from dictionary."""
        return cls(
            query=data["query"],
            k=data["k"],
            chunk_context=data["chunk_context"],
        )


@attrs.define
class RetrieveOutput:
    """Output from document retrieval containing all scored document groups."""

    query: RetrieveQuery
    results: list[tuple[float, list[Document]]]

    @property
    def total_documents(self) -> int:
        """Total number of documents in the results."""
        return sum(len(docs) for _, docs in self.results)

    def to_langsmith_output(self, formatted_output: str | None) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "formatted_output": formatted_output,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert RetrieveOutput to dictionary for serialization."""
        return {
            "query": self.query.to_dict(),
            "env": {k: v for k, v in os.environ.items() if k.startswith("ISTAROTH_")},
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
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrieveOutput":
        """Create RetrieveOutput from dictionary."""
        query = RetrieveQuery.from_dict(data["query"])
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

        return cls(query=query, results=results)


@attrs.define
class CombinedRetrieveOutput:
    """Combined output from multiple retrieval queries with deduplication."""

    queries: list[RetrieveQuery]
    results: list[tuple[float, list[Document]]]

    @classmethod
    def from_multiple_outputs(
        cls, outputs: list[RetrieveOutput]
    ) -> "CombinedRetrieveOutput":
        """Combine multiple RetrieveOutputs, deduplicating results."""
        if not outputs:
            raise ValueError("At least one RetrieveOutput is required")

        # Group results by file_id, collecting all unique chunks
        # file_id -> (max_score, dict of chunk_index -> Document)
        file_groups = dict[str, tuple[float, dict[int, Document]]]()

        for output in outputs:
            for score, docs in output.results:
                if not docs:
                    continue

                file_id = docs[0].metadata["file_id"]

                if file_id not in file_groups:
                    file_groups[file_id] = (score, {})

                # Update max score for this file
                file_groups[file_id] = (
                    max(file_groups[file_id][0], score),
                    file_groups[file_id][1],
                )

                # Add all unique chunks from this result
                for doc in docs:
                    chunk_index = doc.metadata["chunk_index"]
                    # Only add if we haven't seen this chunk yet
                    if chunk_index not in file_groups[file_id][1]:
                        file_groups[file_id][1][chunk_index] = doc

        # Convert to final results format
        all_results = []
        for file_id, (max_score, chunk_dict) in file_groups.items():
            # Sort chunks by chunk_index for consistent ordering
            sorted_chunks = sorted(chunk_dict.items(), key=lambda x: x[0])
            docs = [doc for _, doc in sorted_chunks]
            all_results.append((max_score, docs))

        # Sort by score (descending)
        all_results.sort(key=lambda x: x[0], reverse=True)

        # Collect all queries
        queries = [output.query for output in outputs]

        return cls(queries=queries, results=all_results)

    @property
    def total_documents(self) -> int:
        """Total number of documents in the results."""
        return sum(len(docs) for _, docs in self.results)
