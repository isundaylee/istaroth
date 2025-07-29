#!/usr/bin/env python3
"""HTTP/WebSocket MCP server for Istaroth RAG functionality."""

import pathlib
import sys

from fastmcp import FastMCP
from langsmith import traceable

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.rag import embedding

# Create an MCP server
mcp = FastMCP("istaroth")


@mcp.tool()  # type: ignore[misc]
@traceable(name="mcp_retrieve")  # type: ignore[misc]
def retrieve(query: str, k: int = 5, show_scores: bool = False) -> str:
    """Retrieve similar documents from Istaroth RAG document store"""
    try:
        store = embedding.DocumentStore.from_env()

        if store.num_documents == 0:
            return "Error: No documents in store. Please add documents first."

        results = store.search(query, k=k)

        if not results:
            return "No results found."

        output_lines = [
            f"Retrieved {len(results)} documents for query: '{query}'",
            "",
        ]

        for i, (text, score) in enumerate(results):
            if show_scores:
                output_lines.append(f"Document {i + 1} (similarity: {score:.4f}):")
            else:
                output_lines.append(f"Document {i + 1}:")

            # Show first few lines of the document
            lines = text.strip().split("\n")
            preview_lines = lines[:3] if len(lines) > 3 else lines
            for line in preview_lines:
                output_lines.append(f"  {line}")

            if len(lines) > 3:
                output_lines.append("  ...")
            output_lines.append("")

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error retrieving documents: {e}"


if __name__ == "__main__":
    mcp.run()
