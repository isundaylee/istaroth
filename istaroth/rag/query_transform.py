"""Query transformation interfaces and implementations for RAG pipeline."""

from abc import ABC, abstractmethod


class QueryTransformer(ABC):
    """Abstract base class for query transformers."""

    @abstractmethod
    def transform(self, query: str) -> list[str]:
        """Transform a single query into a list of queries.

        Args:
            query: The input query string

        Returns:
            List of transformed query strings
        """
        pass


class IdentityTransformer(QueryTransformer):
    """Identity transformer that returns the original query unchanged."""

    def transform(self, query: str) -> list[str]:
        """Return the original query as a single-item list."""
        return [query]
