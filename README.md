# Istaroth

Istaroth is a Retrieval-Augmented Generation (RAG) system for Genshin Impact that extracts, cleans, and structures textual content to answer lore questions about the world of Teyvat.

Special thanks to Dimbreath for his wonderful work on AnimeGameData!

## Texts Included

- Quests
- Readables (weapons, artifacts, books, misc map texts)
- Character stories
- Character voicelines
- Material texts
- Shishu (诗漱) lore manual (third-party)

## Getting Started

### Python Environment Setup

Requires **Python 3.12** (see `.python-version`) and [uv](https://docs.astral.sh/uv/).

```bash
uv sync              # creates .venv and installs all dependencies
pre-commit install   # if you plan on doing development
```

After changing dependencies, regenerate the Docker export files:

```bash
uv export --frozen --only-group ml --no-hashes --no-emit-project -o requirements-ml.txt
uv export --frozen --no-group dev --no-group ml --no-hashes --no-emit-project -o requirements-app.txt
```

### Checkpoint

A checkpoint currently mainly consists of the vectorstore and various other data stores containing cleaned game texts. You can either grab a pre-trained checkpoint from the [release page](https://github.com/isundaylee/istaroth/releases), or build your own following the instructions in [DEVELOPMENT.md](DEVELOPMENT.md). If you grab a pre-trained checkpoint, be sure to use it with the corresponding Git commit hash.

## Web UI

See [DEVELOPMENT.md](DEVELOPMENT.md#docker-compose-dev) for instructions on launching the web UI via Docker Compose.

## MCP Server

Istaroth provides an MCP (Model Context Protocol) server that enables Claude to query the RAG system directly. For the list of MCP tools and their parameters, see `scripts/mcp_server.py`. See `.env.common.example` and `.env.mcp.example` for the env vars used to configure the MCP server. Three deployment options are available below.

### Option 1: Quick Start with Docker

Launch a prebuilt server with a single command:

```bash
docker run -p 8000:8000 isundaylee/istaroth:latest
```

- Defaults to Chinese checkpoint on first startup - customize with `ISTAROTH_CHECKPOINT_URL` environment variable.
- Follow [Remote Setup](#remote-mcp-server-httpwebsocket) instructions below to integrate with Claude

### Option 2: Local MCP Server (stdio)

```bash
# Configure environment variables
cp .env.common.example .env.common
cp .env.mcp.example .env.mcp
# Edit .env.common and .env.mcp to set your environment variables

# Add to Claude Code
claude mcp add istaroth /path/to/istaroth/scripts/mcp_wrapper.sh

# Restart Claude Code
```

### Option 3: Remote MCP Server (HTTP/WebSocket)

```bash
# Start the server
fastmcp run scripts/mcp_server.py --transport=streamable-http

# Add to Claude Code
claude mcp add istaroth --transport=http http://127.0.0.1:8000/mcp/

# Restart Claude Code
```

## Example Query

See `examples` folder in the repo for some example conversations of using Istaroth MCP server with local Claude Code.
