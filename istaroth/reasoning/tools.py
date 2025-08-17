"""Tools for reasoning pipeline."""

import logging
from typing import Any

from langchain_core import tools
from langchain_core.tools import BaseTool, Tool

from istaroth.rag import document_store, output_rendering

logger = logging.getLogger(__name__)


@tools.tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression (e.g., "2 + 2 * 3")."""
    # Use Python's eval for simple math (be careful in production!)
    # In production, use a safer expression evaluator
    result = eval(expression, {"__builtins__": {}}, {})
    return str(result)


class DocumentRetrievalTool(BaseTool):
    """Document retrieval from RAG store."""

    name: str = "document_retrieval"
    description: str = (
        "Search for relevant documents about Genshin Impact lore. "
        "IMPORTANT: Each query must focus on a SINGLE concept only. "
        "Query format: Either a single keyword (character name, location, item) "
        "OR a single complete sentence/question about one specific topic. "
        "Examples: 'Zhongli', 'What is the Cataclysm?', 'Scaramouche origins'. "
        "Do NOT combine multiple concepts in one query."
    )

    def __init__(self, doc_store: document_store.DocumentStore):
        """Initialize with document store."""
        super().__init__()
        self._doc_store = doc_store

    def _run(self, query: str, k: int = 5) -> str:
        """Execute document retrieval."""
        # Retrieve documents
        retrieve_output = self._doc_store.retrieve(query, k=k)

        # Format results using existing rendering function
        if not retrieve_output.results:
            return "No relevant documents found."

        return output_rendering.render_retrieve_output(retrieve_output.results)

    async def _arun(self, query: str, k: int = 5) -> str:
        """Async version."""
        return self._run(query, k)


def get_default_tools(
    doc_store: document_store.DocumentStore,
) -> list[BaseTool]:
    """Get default tools for reasoning."""
    return [DocumentRetrievalTool(doc_store)]
