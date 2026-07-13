# MCP Server

Istaroth provides an MCP (Model Context Protocol) server that enables Claude to query the RAG system directly. For the list of MCP tools and their parameters, see `scripts/mcp_server.py`. See `.env.common.example` and `.env.mcp.example` for the env vars used to configure the MCP server. Three deployment options are available below.

## Option 1: Quick Start with Docker

Launch a prebuilt server with a single command. This downloads the latest Chinese (`chs`) checkpoint into a persistent named volume, then starts the MCP server against it:

```bash
docker run -p 8000:8000 -v istaroth-checkpoint:/data/checkpoint -e ISTAROTH_MCP_LANGUAGE=CHS isundaylee/istaroth:latest \
  sh -c "python scripts/checkpoint_tools.py download chs /data/checkpoint/chs && fastmcp run scripts/mcp_server.py --transport=streamable-http --host=0.0.0.0 --port=8000"
```

- The `istaroth-checkpoint` volume persists the checkpoint, so subsequent runs skip the download.
- To serve a different language, swap `chs` for another language (e.g. `eng`) in the download command and set both `ISTAROTH_DOCUMENT_STORE_SET` and `ISTAROTH_MCP_LANGUAGE` accordingly (e.g. `-e ISTAROTH_DOCUMENT_STORE_SET=ENG:/data/checkpoint/eng -e ISTAROTH_MCP_LANGUAGE=ENG`).
- Follow [Remote Setup](#option-3-remote-mcp-server-httpwebsocket) instructions below to integrate with Claude

## Option 2: Local MCP Server (stdio)

```bash
# Configure environment variables
cp .env.common.example .env.common
cp .env.mcp.example .env.mcp
# Edit .env.common and .env.mcp to set your environment variables

# Add to Claude Code
claude mcp add istaroth /path/to/istaroth/scripts/mcp_wrapper.sh

# Restart Claude Code
```

## Option 3: Remote MCP Server (HTTP/WebSocket)

```bash
# Start the server
fastmcp run scripts/mcp_server.py --transport=streamable-http

# Add to Claude Code
claude mcp add istaroth --transport=http http://127.0.0.1:8000/mcp/

# Restart Claude Code
```

## Example Query

See the `examples` folder in the repo for some example conversations of using the Istaroth MCP server with local Claude Code.
