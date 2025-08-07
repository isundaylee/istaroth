import abc
import itertools
import os

import attrs
from langchain_cohere import CohereRerank
from langchain_core.documents import Document

from istaroth.rag import types


class Reranker(abc.ABC):
    """Abstract base class for reranking strategies."""

    @abc.abstractmethod
    def rerank(
        self,
        query: str,
        results: list[list[types.ScoredDocument]],
        weights: list[float],
    ) -> list[types.ScoredDocument]:
        """Rerank multiple lists of scored documents into a single ranked list."""
        ...

    @classmethod
    def from_env(cls) -> "Reranker":
        """Get reranker instance based on ISTAROTH_RERANKER environment variable.

        Returns:
            Reranker instance based on environment setting:
            - "rrf": RRFReranker (default)
            - "cohere": CohereReranker

        Raises:
            ValueError: If ISTAROTH_RERANKER has an unknown value
        """
        match (reranker_type := os.environ.get("ISTAROTH_RERANKER", "rrf")):
            case "rrf":
                return RRFReranker()
            case "cohere":
                return CohereReranker()
            case _:
                raise ValueError(f"Unknown ISTAROTH_RERANKER: {reranker_type}")


@attrs.define
class RRFReranker(Reranker):
    """Reranker using Reciprocal Rank Fusion."""

    k: int = 60

    def rerank(
        self,
        query: str,
        results: list[list[types.ScoredDocument]],
        weights: list[float],
    ) -> list[types.ScoredDocument]:
        """Combine multiple retrieval results using reciprocal rank fusion.

        Args:
            query: The original query (not used in RRF)
            results: List of result lists from different retrievers
            weights: Weights for each retriever

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


@attrs.define
class CohereReranker(Reranker):
    """Reranker using Cohere Rerank 3.5 API."""

    model: str = "rerank-v3.5"

    def rerank(
        self,
        query: str,
        results: list[list[types.ScoredDocument]],
        weights: list[float],
    ) -> list[types.ScoredDocument]:
        """Rerank documents using Cohere's rerank API.

        Flattens all results, reranks them with Cohere, and returns top documents.
        """
        # Flatten all results into a single list
        all_scored_docs = list(itertools.chain.from_iterable(results))
        all_docs = [scored_doc.document for scored_doc in all_scored_docs]

        if not all_scored_docs:
            return []

        # Perform reranking with Cohere
        reranker = CohereRerank(model=self.model, top_n=len(all_scored_docs))
        reranked_results = reranker.rerank(query=query, documents=all_docs)

        # Convert back to ScoredDocument format
        return [
            types.ScoredDocument(all_docs[r["index"]], r["relevance_score"])
            for r in reranked_results
        ]
