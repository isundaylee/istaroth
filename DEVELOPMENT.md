# Development Guide

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python dependency management (`uv sync`).
- [rustup](https://rustup.rs) for the Rust regen tool (`rust/istaroth-agd-regen`).
  The toolchain version is pinned in the repo-root `rust-toolchain.toml`; rustup
  installs it automatically on the first `cargo` invocation.

## Rust Regen Tool

`rust/istaroth-agd-regen` generates the AGD corpus and first-seen index
(see its [README](rust/istaroth-agd-regen/README.md)). Build it with the `fast`
profile for everything — output is byte-identical to `--release` and runtime is
equal within noise (~2.8–2.9s), but incremental rebuilds take ~1s instead of
~15s for release thin-LTO:

```bash
cargo build --profile fast --manifest-path rust/Cargo.toml
# binary: rust/target/fast/istaroth-agd-regen
```

`scripts/dev-compose.sh setup` runs this build automatically, so a fresh
worktree can regen immediately.

## Regenerating Text Data

When you need to regenerate text files from source data (e.g., after updating AGD or TPS data):

### AGD (AnimeGameData)

```bash
./rust/target/fast/istaroth-agd-regen generate-all --language CHS -f text/chs
./rust/target/fast/istaroth-agd-regen generate-all --language ENG -f text/eng
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
```

### Build Process

1. **Process AGD data** to extract and clean text files:

```bash
./rust/target/fast/istaroth-agd-regen generate-all --language CHS /path/to/text/files/output
```

2. **Build a checkpoint** from the processed text files:

```bash
scripts/rag_tools.py build /path/to/text/files/output /path/to/checkpoint/output
```

### Building & releasing for distribution

Released checkpoints are built by the **Build and Release Checkpoint** GitHub
Actions workflow (`.github/workflows/build-checkpoint.yml`), triggered manually
via *workflow_dispatch*. It builds the committed `text/` corpus with the
DeepInfra embedding backend on a standard runner (no GPU) and publishes a
`checkpoint/YYYYMMDD-HHMMSS-<commit>` release with `chs.tar.gz` / `eng.tar.gz`
assets.
Requires the `DEEPINFRA_API_KEY` repository secret.

## Docker Compose (Dev)

Runs all services in Docker with source code mounted from the host for live-reload. No pre-built images needed — dependencies are installed into Docker volumes via `uv sync` (backend) and `npm ci` (frontend). API keys and config are read from the repo-root `.env.common` and `.env.web` files; container-specific paths (checkpoint, DB) are overridden in the compose file.

```bash
# One-time setup: create shared cache volumes
docker volume create uv-cache
docker volume create hf-cache
docker volume create npm-cache

# Make sure .env.common and .env.web are set up (copy from .env.*.example)
cd docker-compose/web
docker compose up     # first run installs deps automatically
```

Checkpoints are bind-mounted from `docker-compose/web/checkpoints`, a per-stack
copy of `tmp/checkpoints`. `scripts/dev-compose.sh setup` populates it when it
doesn't already exist (copy-on-write clone where the filesystem supports it, e.g.
APFS/btrfs/XFS; otherwise a full copy), so each worktree's stack gets its own
writable copy — Chroma opens its SQLite read-write even for queries, so stacks
must not share one on-disk database. Delete the directory and re-run `setup` to
refresh after updating `tmp/checkpoints`.

`scripts/dev-compose.sh setup` also initializes the shallow `text` submodule,
syncs the host `.venv`, and runs `npm ci` for host-side frontend tooling used by
pre-commit. Those setup steps run in parallel with the checkpoint clone.

After changing `pyproject.toml` or `frontend/package.json`:

```bash
docker compose run --rm backend-deps   # re-sync Python deps
docker compose run --rm frontend-deps  # re-sync Node deps
```
