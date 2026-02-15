# Istaroth

Istaroth is a Retrieval-Augmented Generation (RAG) system for Genshin Impact that extracts, cleans, and structures textual content to answer lore questions about the world of Teyvat.

Special thanks to Dimbreath for his wonderful work on AnimeGameData!

## Texts Included

- Quests
- Readables (weapons, artifacts, books, misc map texts)
- Character stories
- Character voicelines
- Material texts

## Getting Started

### Python Environment Setup

- Clone repository and install dependencies: `pip install -r requirements.txt`
- Install pre-commit hooks (if you plan on doing development): `pre-commit install`

### Checkpoint

A checkpoint currently mainly consists of the vectorstore and various other data stores containing cleaned game texts. You can either grab a pre-trained checkpoint from the [release page](https://github.com/isundaylee/istaroth/releases), or follow the sections below to train your own. If you grab a pre-trained checkpoint, be sure to use it with the corresponding Git commit hash. Currently pre-trained checkpoints are only provided for the Chinese language.

#### Checkpoint Training

- Set some env vars:
    - `export AGD_PATH="/path/to/AnimeGameData"`
    - `export AGD_LANGUAGE="CHS"` (or `ENG` for English)
- Process AGD data: `scripts/agd_tools.py generate-all /path/to/text/files/output` to extract and clean text files
- Build a checkpoint: `scripts/rag_tools.py build /path/to/text/files/output /path/to/checkpoint/output`

## Web UI

You can either download a checkpoint from the [release page](https://github.com/isundaylee/istaroth/releases) or train your own as described above. After obtaining a checkpoint (e.g., extracted to `tmp/checkpoints/chs`), configure your environment (create `istaroth/.env`):

```bash
export ISTAROTH_DATABASE_URI="sqlite+aiosqlite:///tmp/istaroth.db"
export ISTAROTH_DOCUMENT_STORE_SET="chs:tmp/checkpoints/chs"
export ISTAROTH_TRAINING_DEVICE="cpu"
export ISTAROTH_AVAILABLE_MODELS="all"
```

**Frontend:**

```bash
cd istaroth/frontend
npm install  # First time only
npm run dev -- --host  # Port 5173
```

**Backend:**

```bash
cd istaroth
source env/bin/activate
source .env
python -m istaroth.services.backend --host 0.0.0.0 --port 8000
```

## MCP Server

Istaroth provides an MCP (Model Context Protocol) server that enables Claude to query the RAG system directly. Three deployment options are available:

For the list of MCP tools and their parameters, see `scripts/mcp_server.py`.

### Quick Start with Docker

Launch a prebuilt server with a single command:

```bash
docker run -p 8000:8000 isundaylee/istaroth:latest
```

- Defaults to Chinese checkpoint on first startup
- Customize with `ISTAROTH_CHECKPOINT_URL` environment variable
- Follow [Remote Setup](#remote-mcp-server-httpwebsocket) instructions below to integrate with Claude

### Local MCP Server (stdio)

```bash
# Copy and configure the wrapper
cp scripts/mcp_wrapper.template.sh scripts/mcp_wrapper.sh
# Edit scripts/mcp_wrapper.sh to set environment variables

# Add to Claude Code
claude mcp add istaroth /path/to/istaroth/scripts/mcp_wrapper.sh

# Restart Claude Code
```

### Remote MCP Server (HTTP/WebSocket)

```bash
# Start the server
fastmcp run scripts/mcp_server.py --transport=streamable-http

# Add to Claude Code
claude mcp add istaroth --transport=http http://127.0.0.1:8000/mcp/

# Restart Claude Code
```

### MCP Environment Variables

The MCP server uses the following environment variables:

- `ISTAROTH_DOCUMENT_STORE_SET`: Comma-separated list of language checkpoints, e.g. `CHS:/path/to/chs_checkpoint,ENG:/path/to/eng_checkpoint`.
- `ISTAROTH_MCP_LANGUAGE`: Language for queries, must be one of the supported languages (currently `CHS` or `ENG`).

## Example Query

See `examples` folder in the repo.
