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
        "Use this when you need to find information about characters, "
        "locations, events, or game mechanics."
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


@tools.tool
def web_search(query: str) -> str:
    """Search the web for information (placeholder)."""
    # Placeholder implementation
    return f"Web search results for '{query}' would appear here. (Not yet implemented)"


def create_python_repl_tool() -> Tool:
    """Create Python REPL tool for code execution."""
    from langchain_experimental.tools import PythonREPLTool

    python_repl = PythonREPLTool()
    return Tool(
        name="python_repl",
        description="Execute Python code for calculations, data processing, or analysis",
        func=python_repl.run,
    )


def get_default_tools(
    doc_store: document_store.DocumentStore,
) -> list[BaseTool]:
    """Get default tools for reasoning."""
    return [DocumentRetrievalTool(doc_store)]
