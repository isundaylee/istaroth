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

A checkpoint currently mainly consists of the vectorstore containing cleaned game texts and their vector embeddings. You can either grab a pre-trained checkpoint from the [release page](https://github.com/isundaylee/istaroth/releases), or follow the sections below to train your own. If you grab a pre-trained checkpoint, be sure to use it with the corresponding Git commit hash. Currently pre-trained checkpoints are only provided for the Chinese language.

#### Checkpoint Training

- Set some env vars:
    - `export AGD_PATH="/path/to/AnimeGameData"`
    - `export AGD_LANGUAGE="CHS"` (or `ENG` for English)
- Process AGD data: `scripts/agd_tools.py generate-all /path/to/text/files` to extract and clean text files
- Add documents: `scripts/rag_tools.py add-documents /path/to/text/files`

### Running Queries

- Set some env vars:
    - `GOOGLE_API_KEY` to a Google API key with Gemini API enabled
    - `ISTAROTH_TRAINING_DEVICE=cpu` if you don't have CUDA
- Basic query: `scripts/rag_tools.py query "玛丽安与西摩尔的关系是怎么样的？"`
    - Query with sources: `scripts/rag_tools.py query "玛丽安与西摩尔的关系是怎么样的？" --show-sources`
- Retrieve documents only: `scripts/rag_tools.py retrieve "璃月港的历史" --k 3`
    - Parameters: `--k` (documents to retrieve, default 5), `--show-sources` (display similarity scores)

## MCP Server

Istaroth includes an MCP (Model Context Protocol) server that allows Claude to query the RAG system directly. The server supports both local (stdio) and remote (HTTP/WebSocket) connections.

### Docker image

You can launch an MCP server with a prebuilt Docker image:

```
docker run -p 8000:8000 isundaylee/istaroth:latest
```

Then follow the remaining instructions in the Remote MCP server section below to add it into Claude.

The Docker image defaults to loading a recent Chinese checkpoint upon first startup. You can customize it by setting the `ISTAROTH_CHECKPOINT_URL` env var.

### Local MCP Server (stdio)

For local Claude Code integration:

- Copy the MCP wrapper template: `cp scripts/mcp_wrapper.template.sh scripts/mcp_wrapper.sh`
- Edit `scripts/mcp_wrapper.sh` and set your environment variables.
- Add the MCP server to Claude Code: `claude mcp add istaroth /path/to/istaroth/scripts/mcp_wrapper.sh`
- Restart Claude Code to enable the MCP server

### Remote MCP Server (HTTP/WebSocket)

For remote access or web-based integrations:

- Start the HTTP/WebSocket server: `fastmcp run scripts/mcp_server.py --transport=streamable-http`
- Add the MCP server to Claude Code: `claude mcp add istaroth --transport=http http://127.0.0.1:8000/mcp`
- Restart Claude Code to enable the MCP server

### Usage

Once configured, you can query the Istaroth knowledge base directly in Claude using natural language. The MCP server provides a `retrieve` function that searches the document store for relevant content.

## Example Query

See `examples` folder in the repo.
