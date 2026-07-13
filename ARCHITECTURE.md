# Istaroth System Architecture

Istaroth is a **Retrieval-Augmented Generation (RAG) system** for Genshin Impact lore. It retrieves relevant documents from multi-language vector databases and generates natural language answers using LLMs, accessible via web and MCP interfaces.

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                          │
├─────────────────┬──────────────────┬────────────────────┤
│  Web Browser    │  REST Clients    │  MCP Clients       │
│  (React SPA)    │  (HTTP/JSON)     │  (Claude Code)     │
└─────────────────┴──────────────────┴────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  APPLICATION SERVICES                    │
├────────────────────────┬────────────────────────────────┤
│  Web Backend           │  MCP Server                    │
│  (FastAPI)             │  (FastMCP)                     │
│  • /api/query/stream   │  • retrieve() tool             │
│    (retrieve + LLM)    │    (retrieve only)             │
│  Port: 8000            │  stdio                         │
└────────────────────────┴────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    RAG PIPELINE                          │
│  • Retrieval: DocumentStoreSet + ChromaDB               │
│  • Generation: LLM (Gemini/Claude/etc.)                 │
│  • Context expansion & chunking                         │
└─────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   DATA LAYER                             │
├─────────────────┬──────────────────┬───────────────────┤
│  ChromaDB       │  TextSet Files   │  PostgreSQL       │
│  (vectors)      │  (game text)     │  (conversations)  │
└─────────────────┴──────────────────┴───────────────────┘
```

---

## Core Services

### 1. Web Backend (`istaroth.services.backend`)

**Framework**: FastAPI
**Port**: 8000
**Purpose**: Serves the React frontend and provides REST API for web clients.

**Key Endpoints**:
- `POST /api/query/stream` — Submit a question; streams pipeline progress (newline-delimited JSON `step_start`/`step_end` events) and a terminal `done`/`error` event after retrieving documents and generating the answer via LLM
- `GET/POST /api/conversations` — Manage conversation history
- `GET /api/library` — Browse categorized game text
- `GET /api/citations` — Retrieve source documents by ID
- `GET /api/examples` — Fetch example questions

**Features**:
- **RAG question answering**: Retrieval + LLM generation pipeline
- **Multi-language support**: CHS/ENG query processing
- **Conversation persistence**: PostgreSQL storage
- **Citation tracking**: Returns source file IDs and chunks
- **Static file serving**: React SPA

---

### 2. MCP Server (`scripts/mcp_server.py`)

**Framework**: FastMCP
**Transport**: stdio
**Purpose**: Exposes Istaroth's retrieval capabilities to MCP-compatible AI tools (Claude Code, etc.) — provides document retrieval only, not answer generation.

**MCP Tools**:
1. **`retrieve(query, k, context)`**
   - Semantic search over game text
   - Returns top-k relevant chunks with metadata

2. **`get_file_content(file_id, chunks)`**
   - Fetch full or partial document content
   - Supports chunk ID filtering for context expansion

---

### 3. React Frontend (`web/`)

**Framework**: Vite + React + TypeScript
**Build**: `npm run build` → static files served by backend
**Features**:
- **Conversational UI**: Chat interface with conversation history
- **Library browser**: Categorized navigation (quests, characters, readables)
- **Citation display**: Click-to-expand source documents
- **Language toggle**: Switch between CHS/ENG
- **Responsive design**: Desktop and mobile

---

## RAG Pipeline

### Retrieval Layer

**DocumentStoreSet** (`istaroth/rag/document_store_set.py`) — Multi-language document store abstraction.

**Key Features**:
- **Language-specific stores**: Separate ChromaDB collections for CHS/ENG
- **Metadata filtering**: Filter by file type, quest ID, character, etc.
- **Context expansion**: Retrieve neighboring chunks for better context
- **Deduplication**: Merge overlapping chunks in results

**Retrieval Flow**:
1. Select language-specific document store (CHS/ENG)
2. **Query transformation** (optional): Generate multiple semantic variations
3. **Hybrid retrieval**: Vector search (BAAI/bge-m3) + BM25 keyword search
4. **Reranking**: Fuse results using RRF or Cohere Rerank API
5. Expand context by fetching adjacent chunks
6. Return ranked results with metadata

---

### Generation Layer

**RAGPipeline** (`istaroth/rag/pipeline.py`) — Combines retrieval with LLM-based answer generation.

**Process**:
1. Retrieve relevant documents using DocumentStoreSet
2. Format documents with citations and metadata
3. Construct prompt with retrieved context
4. Generate natural language answer via LLM (Gemini/Claude/GPT)
5. Return answer with source citations

**Supported LLMs**: Gemini (default), Claude, OpenAI GPT, configurable via `ISTAROTH_AVAILABLE_MODELS`

---

### Retrieval Enhancements

**Query Transformation** (`ISTAROTH_QUERY_TRANSFORMER`):
- **Identity** (default): No transformation
- **Rewrite**: Generate 3 semantic variations using Gemini 2.5 Flash Lite for comprehensive retrieval

**Hybrid Search**:
- **Vector search**: Semantic similarity via bge-m3 embeddings
- **BM25 search**: Keyword-based retrieval for exact matches
- Both executed in parallel, results fused

**Embeddings** (`ISTAROTH_EMBEDDINGS`):
- **local** (default): Local HuggingFace BAAI/bge-m3
- **deepinfra**: DeepInfra-hosted BAAI/bge-m3 via OpenAI-compatible API (requires `DEEPINFRA_API_KEY`)

**Reranking** (`ISTAROTH_RERANKER`):
- **RRF** (Reciprocal Rank Fusion): Combines results by rank position
- **Cohere Rerank v3.5**: Neural reranker for improved relevance

---

### Vector Storage (ChromaDB)

**Embedding Model**: `BAAI/bge-m3` (multilingual, 1024 dimensions)
**Distance Metric**: Cosine similarity
**Index**: HNSW (Hierarchical Navigable Small World)

**Collections**:
- `istaroth_chs` - Chinese game text
- `istaroth_eng` - English game text

---

## Data Pipeline

The corpus is produced in two stages; see [DEVELOPMENT.md](DEVELOPMENT.md) for the exact commands.

1. **Text generation** — the Rust regen tool (`rust/istaroth-agd-regen`) extracts and cleans game text from AnimeGameData, and `scripts/tps_shishu_tools.py` extracts the TPS Shishu lore manual from PDF. Output: cleaned text files + `manifest.json`.
2. **Vector build** (`scripts/rag_tools.py build`) — chunks the text, generates BAAI/bge-m3 embeddings, and builds the ChromaDB checkpoint.

---

## Deployment

### Docker Compose (Development)

A per-worktree dev stack (backend, retrieval, and frontend services, plus Jaeger for tracing) is defined under `docker-compose/web/` and driven by the `scripts/dev-compose.sh` helper. ChromaDB is embedded as an on-disk store rather than a separate service, and PostgreSQL is external (via `ISTAROTH_DATABASE_URI`). See [DEVELOPMENT.md](DEVELOPMENT.md#docker-compose-dev) for setup and usage.

---

### Kubernetes (Production)

**Namespace**: `istaroth`

**Deployments**:
- `backend` — FastAPI web backend (REST API + static files)
- `frontend` — React UI (nginx)
- `retrieval` — RAG retrieval service
- `mcp-{lang}` — Per-language MCP servers (e.g., mcp-chs, mcp-eng)
- `chroma-{lang}` — Per-language ChromaDB servers (optional)

**External Dependencies**:
- PostgreSQL (conversation storage) via `ISTAROTH_DATABASE_URI` env var

**Helm Chart**: `helm/istaroth/`

---

### MCP Server (Local)

**No container needed** - runs as stdio subprocess invoked by MCP client.

**Configuration**: Add to client's MCP config (e.g., `~/.config/claude-code/mcp_servers.json`).

---

## Technology Stack

| Component         | Technology              | Purpose                      |
|-------------------|-------------------------|------------------------------|
| Frontend          | React + Vite            | Web UI                       |
| Backend API       | FastAPI                 | REST endpoints               |
| MCP Server        | FastMCP                 | AI tool integration          |
| Vector DB         | ChromaDB                | Semantic search              |
| Embeddings        | BAAI/bge-m3             | Multilingual text embeddings |
| LLMs              | Gemini / Claude / GPT   | Answer generation            |
| Conversation DB   | PostgreSQL              | Chat history                 |
| Orchestration     | Docker Compose / K8s    | Deployment                   |
