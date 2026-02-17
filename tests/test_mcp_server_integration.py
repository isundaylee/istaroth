"""Integration test for MCP server (scripts/mcp_server.py).

Launches the real MCP server as a subprocess via StdioTransport
and exercises tools over the MCP protocol.
"""

import os
import pathlib
import re
import sys

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio(loop_scope="session")
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp import types as mcp_types

_PROJECT_ROOT = pathlib.Path(__file__).parent.parent


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def mcp_client(built_checkpoint_dir: pathlib.Path):
    """Launch the MCP server once and share across all tests in the session."""
    transport = StdioTransport(
        command=sys.executable,
        args=[str(_PROJECT_ROOT / "scripts" / "mcp_server.py")],
        env={
            **os.environ,
            "ISTAROTH_DOCUMENT_STORE_SET": f"CHS:{built_checkpoint_dir}",
            "ISTAROTH_MCP_LANGUAGE": "CHS",
            "ISTAROTH_TRAINING_DEVICE": "cpu",
        },
        cwd=str(_PROJECT_ROOT),
    )
    async with Client(transport=transport) as client:
        yield client


async def test_list_tools(mcp_client: Client) -> None:
    """Server exposes exactly the retrieve and get_file_content tools."""
    tools = await mcp_client.list_tools()
    tool_names = sorted(t.name for t in tools)
    assert tool_names == ["get_file_content", "retrieve"]


async def test_retrieve(mcp_client: Client) -> None:
    """Retrieve tool returns relevant content for a known query."""
    result = await mcp_client.call_tool(
        "retrieve", {"query": "钟离的真实身份", "k": 1, "chunk_context": 0}
    )
    assert not result.is_error
    text = _extract_text(result)
    assert "摩拉克斯" in text


async def test_get_file_content(mcp_client: Client) -> None:
    """Get file content tool returns chunks for a valid file_id from retrieve results."""
    retrieve_result = await mcp_client.call_tool(
        "retrieve", {"query": "钟离", "k": 1, "chunk_context": 0}
    )
    file_id = _extract_file_id(_extract_text(retrieve_result))

    result = await mcp_client.call_tool("get_file_content", {"file_id": file_id})
    assert not result.is_error
    text = _extract_text(result)
    assert "文件ID:" in text
    assert "片段" in text


def _extract_text(result: mcp_types.CallToolResult) -> str:
    """Extract concatenated text from a CallToolResult."""
    return "".join(
        c.text for c in result.content if isinstance(c, mcp_types.TextContent)
    )


def _extract_file_id(retrieve_text: str) -> str:
    """Extract the first file_id (MD5 hash) from retrieve output."""
    if m := re.search(r"文件ID[:：]\s*([a-f0-9]{32})", retrieve_text):
        return m.group(1)
    raise ValueError(f"No file_id found in retrieve output:\n{retrieve_text}")
