"""Query transformation interfaces and implementations for RAG pipeline."""

import logging
import os
import typing
from abc import ABC, abstractmethod

import attrs
from langchain_core import language_models
from langchain_google_genai import llms as google_llms

logger = logging.getLogger(__name__)


class QueryTransformer(ABC):
    """Abstract base class for query transformers."""

    @abstractmethod
    def transform(self, query: str) -> list[str]:
        """Transform a single query into a list of queries. The first returned
        query must be the original query."""
        pass

    @classmethod
    def from_env(cls) -> "QueryTransformer":
        """Get query transformer instance based on ISTAROTH_QUERY_TRANSFORMER environment variable.

        Returns:
            QueryTransformer instance based on environment setting:
            - "identity": IdentityTransformer (default)
            - "rewrite": RewriteQueryTransformer

        Raises:
            ValueError: If ISTAROTH_QUERY_TRANSFORMER has an unknown value
        """
        match (qtv := os.environ.get("ISTAROTH_QUERY_TRANSFORMER", "identity")):
            case "identity":
                return IdentityTransformer()
            case "rewrite":
                return RewriteQueryTransformer.create()
            case _:
                raise ValueError(f"Unknown ISTAROTH_QUERY_TRANSFORMER: {qtv}")


class IdentityTransformer(QueryTransformer):
    """Identity transformer that returns the original query unchanged."""

    def transform(self, query: str) -> list[str]:
        """Return the original query as a single-item list."""
        return [query]


@attrs.define
class RewriteQueryTransformer(QueryTransformer):
    """Query transformer that uses Gemini LLM to rewrite queries for improved RAG retrieval."""

    _PROMPT_TEMPLATE: typing.ClassVar[
        str
    ] = """请根据用户的原始问题，生成{num_queries}个语义相近但表达方式不同的问题，这些问题应该能够帮助检索到更全面的相关信息。

原始问题：{query}

要求：
1. 生成的问题应该与原问题语义相近
2. 使用不同的表达方式、关键词或角度
3. 保持问题的核心意图不变
4. 适合用于检索《原神》相关的文档和资料
5. 每个问题占一行，不要添加编号或其他格式

生成的问题："""

    _llm: language_models.BaseLLM = attrs.field()
    _num_queries: int = attrs.field(default=3)

    @classmethod
    def create(
        cls,
        *,
        model: str = "gemini-2.5-flash-lite",
        num_queries: int = 3,
    ) -> "RewriteQueryTransformer":
        """Create a RewriteQueryTransformer with Gemini LLM.

        Args:
            model: Gemini model name to use
            num_queries: Number of rewritten queries to generate

        Returns:
            RewriteQueryTransformer instance
        """
        llm = google_llms.GoogleGenerativeAI(model=model)
        return cls(llm, num_queries)

    def transform(self, query: str) -> list[str]:
        """Transform query into multiple similar queries for improved retrieval.

        Args:
            query: The input query string

        Returns:
            List of rewritten query strings including the original
        """
        if not query.strip():
            return [query]

        # Create prompt for query rewriting using the class template
        prompt = self._PROMPT_TEMPLATE.format(
            query=query, num_queries=self._num_queries - 1
        )

        try:
            # Generate rewritten queries using LLM
            response = self._llm.invoke(prompt)
        except Exception as e:
            logger.warning(f"Failed to rewrite query {query!r}: {e}")
            # Fallback to original query on error
            return [query]
        else:
            # Parse the response to extract individual queries
            rewritten_queries = [
                query,
                *(s for q in response.strip().splitlines() if (s := q.strip())),
            ]

            return rewritten_queries[: self._num_queries]
