import abc

import attrs
from langchain_core.documents import Document

from istaroth.rag import document_store, types


class Reranker(abc.ABC):
    """Abstract base class for reranking strategies."""

    @abc.abstractmethod
    def rerank(
        self, results: list[list[types.ScoredDocument]], weights: list[float]
    ) -> list[types.ScoredDocument]:
        """Rerank multiple lists of scored documents into a single ranked list."""
        ...


@attrs.define
class RRFReranker(Reranker):
    """Reranker using Reciprocal Rank Fusion."""

    k: int = 60

    def rerank(
        self, results: list[list[types.ScoredDocument]], weights: list[float]
    ) -> list[types.ScoredDocument]:
        """Combine multiple retrieval results using reciprocal rank fusion.

        Args:
            results: List of result lists from different retrievers
            weights: Weights for each retriever
            k: Constant added to rank (default 60)

        Returns:
            Fused results sorted by score
        """
        doc_scores: dict[str, tuple[float, Document]] = {}

        assert len(results) == len(weights)
        for retriever_results, weight in zip(results, weights):
            for rank, scored_doc in enumerate(retriever_results, 1):
                score = weight / (self.k + rank)
                content = scored_doc.document.page_content
                if content in doc_scores:
                    # Update score, keep first document encountered
                    doc_scores[content] = (
                        doc_scores[content][0] + score,
                        doc_scores[content][1],
                    )
                else:
                    doc_scores[content] = (score, scored_doc.document)

        # Sort by combined score (highest first) and return with document
        sorted_results = sorted(doc_scores.items(), key=lambda x: x[1][0], reverse=True)
        return [
            types.ScoredDocument(document=doc, score=score)
            for _, (score, doc) in sorted_results
        ]
