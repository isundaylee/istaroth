#!/usr/bin/env python3
"""Entry point for Istorath MCP server."""

import asyncio
import pathlib
import sys

import mcp.server.stdio

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.mcp import server


async def main() -> None:
    """Run the MCP server."""
    server_instance = server.create_server()

    # Use stdio transport for MCP
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server_instance.run(
            read_stream, write_stream, server_instance.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
