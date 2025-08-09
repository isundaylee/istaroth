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
- Set required environment variable: `export ISTAROTH_DOCUMENT_STORE="/path/to/document/store"`
- Optional LangSmith tracing: Set `LANGSMITH_API_KEY`, `LANGCHAIN_PROJECT`, `LANGCHAIN_TRACING_V2="true"`

### Checkpoint

A checkpoint currently mainly consists of the vectorstore and various other data stores containing cleaned game texts. You can either grab a pre-trained checkpoint from the [release page](https://github.com/isundaylee/istaroth/releases), or follow the sections below to train your own. If you grab a pre-trained checkpoint, be sure to use it with the corresponding Git commit hash. Currently pre-trained checkpoints are only provided for the Chinese language.

#### Checkpoint Training

- Set some env vars:
    - `export AGD_PATH="/path/to/AnimeGameData"`
    - `export AGD_LANGUAGE="CHS"` (or `ENG` for English)
- Process AGD data: `scripts/agd_tools.py generate-all /path/to/text/files` to extract and clean text files

### Running Queries

- Set some env vars:
    - `GOOGLE_API_KEY` to a Google API key with Gemini API enabled
    - `ISTAROTH_TRAINING_DEVICE=cpu` if you don't have CUDA
- Retrieve documents: `scripts/rag_tools.py retrieve "璃月港的历史" -k 3 -c 0`

## MCP Server

Istaroth provides an MCP (Model Context Protocol) server that enables Claude to query the RAG system directly. Three deployment options are available:

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

### Usage

Once configured, you can query the Istaroth knowledge base directly in Claude using natural language. The MCP server provides two tools:

**`retrieve`** - Search for relevant documents
- Query the knowledge base with natural language questions
- Best for finding documents related to characters, lore, regions, and storylines
- Returns matching document excerpts with file IDs for detailed access

**`get_file_content`** - Get complete file contents
- Retrieve full content from specific files using their file ID
- Use after `retrieve` to get complete context from interesting files

## Example Query

See `examples` folder in the repo.
