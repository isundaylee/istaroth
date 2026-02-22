# Development Guide

## Regenerating Text Data

When you need to regenerate text files from source data (e.g., after updating AGD or TPS data):

### AGD (AnimeGameData)

```bash
AGD_LANGUAGE=CHS scripts/agd_tools.py generate-all -f text/chs
AGD_LANGUAGE=ENG scripts/agd_tools.py generate-all -f text/eng
```

The `-f` flag forces regeneration by deleting existing output directories.

### TPS - Shishu (Shishu lore manual)

```bash
# Step 1: Extract PDF to markdown (can run on a separate machine with GPU)
python scripts/tps_shishu_tools.py extract manual.pdf tmp/manual.md

# Step 2: Split chapters and write manifest
python scripts/tps_shishu_tools.py generate tmp/manual.md text/chs/
```

The `-f` flag on `generate` forces regeneration by deleting the existing `tps_shishu/` directory.

## Checkpoint Training

A checkpoint consists of the vectorstore and various data stores containing cleaned game texts.

### Prerequisites

Set up your environment variables:

```bash
export AGD_PATH="/path/to/AnimeGameData"
export AGD_LANGUAGE="CHS"  # or "ENG" for English
```

### Build Process

1. **Process AGD data** to extract and clean text files:

```bash
scripts/agd_tools.py generate-all /path/to/text/files/output
```

2. **Build a checkpoint** from the processed text files:

```bash
scripts/rag_tools.py build /path/to/text/files/output /path/to/checkpoint/output
```

## Docker Compose (Dev)

Runs all services in Docker with source code mounted from the host for live-reload. No pre-built images needed — dependencies are installed into Docker volumes via `uv sync` (backend) and `npm ci` (frontend). API keys and config are read from the repo-root `.env.common` and `.env.web` files; container-specific paths (checkpoint, DB) are overridden in the compose file.

```bash
# One-time setup: create shared cache volumes
docker volume create uv-cache
docker volume create hf-cache

# Make sure .env.common and .env.web are set up (copy from .env.*.example)
cd docker-compose/web
docker compose up     # first run installs deps automatically
```

After changing `pyproject.toml` or `frontend/package.json`:

```bash
docker compose run --rm backend-deps   # re-sync Python deps
docker compose run --rm frontend-deps  # re-sync Node deps
```
