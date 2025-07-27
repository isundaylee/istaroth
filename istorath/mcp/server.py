"""MCP server implementing retrieve functionality for Istorath RAG system."""

from typing import Any

from mcp import types
from mcp.server import Server

from istorath.rag import embedding


class IstorathrMCPServer:
    """MCP server for Istorath RAG retrieve functionality."""

    def __init__(self) -> None:
        self._store: embedding.DocumentStore | None = None

    def _get_store(self) -> embedding.DocumentStore:
        """Get or load document store."""
        if self._store is None:
            self._store = embedding.DocumentStore.from_env()

        return self._store

    async def retrieve_documents(
        self, query: str, k: int = 5, show_scores: bool = False
    ) -> str:
        """Retrieve similar documents from the document store."""
        try:
            store = self._get_store()

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


def create_server() -> Server:
    """Create and configure the MCP server."""
    server_instance = Server("istorath-rag")
    istorath_server = IstorathrMCPServer()

    @server_instance.list_tools()  # type: ignore[misc]
    async def list_tools() -> list[types.Tool]:
        """List available tools."""
        return [
            types.Tool(
                name="retrieve",
                description="Retrieve similar documents from Istorath RAG document store",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to find similar documents",
                        },
                        "k": {
                            "type": "integer",
                            "description": "Number of documents to retrieve (default: 5)",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20,
                        },
                        "show_scores": {
                            "type": "boolean",
                            "description": "Whether to show similarity scores (default: false)",
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            )
        ]

    @server_instance.call_tool()  # type: ignore[misc]
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        """Handle tool calls."""
        if name == "retrieve":
            query = arguments["query"]
            k = arguments.get("k", 5)
            show_scores = arguments.get("show_scores", False)

            result = await istorath_server.retrieve_documents(
                query=query, k=k, show_scores=show_scores
            )

            return [types.TextContent(type="text", text=result)]
        else:
            raise ValueError(f"Unknown tool: {name}")

    return server_instance
