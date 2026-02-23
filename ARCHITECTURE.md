# Istaroth System Architecture

Istaroth is a **Retrieval-Augmented Generation (RAG) system** for Genshin Impact lore, providing multi-language vector search over game text documents with web and MCP interfaces.

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
│  Port: 8000            │  stdio                         │
└────────────────────────┴────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    RAG CORE                              │
│  • DocumentStoreSet (multi-language)                    │
│  • ChromaDB vector search                               │
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
- `POST /api/query` - Submit a question, retrieve relevant documents
- `GET/POST /api/conversations` - Manage conversation history
- `GET /api/library` - Browse categorized game text
- `GET /api/citations` - Retrieve source documents by ID
- `GET /api/examples` - Fetch example questions

**Features**:
- **Multi-language support**: CHS/ENG query processing
- **Conversation persistence**: PostgreSQL storage
- **Citation tracking**: Returns source file IDs and chunks
- **Static file serving**: React SPA

---

### 2. MCP Server (`scripts/mcp_server.py`)

**Framework**: FastMCP
**Transport**: stdio
**Purpose**: Exposes Istaroth's RAG capabilities to MCP-compatible AI tools (Claude Code, etc.)

**MCP Tools**:
1. **`retrieve(query, k, context)`**
   - Semantic search over game text
   - Returns top-k relevant chunks with metadata
   - Language detection (CHS/ENG)

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

## RAG Core Components

### DocumentStoreSet (`istaroth/rag/document_store_set.py`)

**Purpose**: Multi-language document store abstraction.

**Key Features**:
- **Language-specific stores**: Separate ChromaDB collections for CHS/ENG
- **Metadata filtering**: Filter by file type, quest ID, character, etc.
- **Context expansion**: Retrieve neighboring chunks for better context
- **Deduplication**: Merge overlapping chunks in results

**Query Flow**:
1. Detect language (CHS/ENG)
2. Route to appropriate document store
3. **Query transformation** (optional): Generate multiple semantic variations
4. **Hybrid retrieval**: Vector search (BAAI/bge-m3) + BM25 keyword search
5. **Reranking**: Fuse results using RRF or Cohere Rerank API
6. Expand context by fetching adjacent chunks
7. Return ranked results with metadata

---

### Retrieval Enhancements

**Query Transformation** (`ISTAROTH_QUERY_TRANSFORMER`):
- **Identity** (default): No transformation
- **Rewrite**: Generate 3 semantic variations using Gemini 2.5 Flash Lite for comprehensive retrieval

**Hybrid Search**:
- **Vector search**: Semantic similarity via bge-m3 embeddings
- **BM25 search**: Keyword-based retrieval for exact matches
- Both executed in parallel, results fused

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

### 1. Text Generation

**AGD extraction** — Extract game text from AnimeGameData:
```bash
export AGD_PATH="/path/to/AnimeGameData" AGD_LANGUAGE="CHS"
python scripts/agd_tools.py generate-all text/chs/
```

**TPS Shishu** — Extract lore manual from PDF:
```bash
python scripts/tps_shishu_tools.py extract manual.pdf tmp/manual.md
python scripts/tps_shishu_tools.py generate tmp/manual.md text/chs/
```

**Output**: Cleaned text files + `manifest.json`

---

### 2. Vector Build (`rag_tools.py build`)

Chunk text, generate embeddings (BAAI/bge-m3), build ChromaDB index.

```bash
python scripts/rag_tools.py build text/chs/ checkpoint/chs/
```

**Output**: ChromaDB checkpoint with vector embeddings

---

## Deployment

### Docker Compose (Development)

**File**: `docker-compose.yml`

**Services**:
- `backend` - FastAPI server (port 8000)
- `postgres` - Conversation storage (port 5432)
- `chromadb` - Vector database (port 8001)

**Start**:
```bash
docker-compose up -d
```

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

| Component         | Technology           | Purpose                      |
|-------------------|----------------------|------------------------------|
| Frontend          | React + Vite         | Web UI                       |
| Backend API       | FastAPI              | REST endpoints               |
| MCP Server        | FastMCP              | AI tool integration          |
| Vector DB         | ChromaDB             | Semantic search              |
| Embeddings        | BAAI/bge-m3          | Multilingual text embeddings |
| Conversation DB   | PostgreSQL           | Chat history                 |
| Orchestration     | Docker Compose / K8s | Deployment                   |
