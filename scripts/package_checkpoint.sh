#!/bin/bash
# Build a checkpoint from a text directory and package it for release.
# The embedding backend is chosen via ISTAROTH_EMBEDDINGS (e.g. "deepinfra").

set -euo pipefail

TEXT_PATH=${1:-}
CHECKPOINT_PATH=${2:-}

if [[ -z "$TEXT_PATH" || -z "$CHECKPOINT_PATH" ]]; then
  echo "Usage: $0 <text_path> <checkpoint_path>"
  exit 1
fi

# Build the document store (vectorstore + BM25 + documents).
# Set ISTAROTH_EMBEDDING_CACHE to reuse embeddings across builds; it is read
# directly by Python (inherited by the subprocess), like the other env vars.
uv run python scripts/rag_tools.py build -f "$TEXT_PATH" "$CHECKPOINT_PATH"

# Bundle the source text and its git provenance into the checkpoint
cp -r "$TEXT_PATH" "$CHECKPOINT_PATH/text"
git -C "$TEXT_PATH" rev-parse HEAD > "$CHECKPOINT_PATH/text.git_commit"
git -C "$TEXT_PATH" diff HEAD > "$CHECKPOINT_PATH/text.git_diff"

# Package for release
tar -C "$CHECKPOINT_PATH" -czf "$CHECKPOINT_PATH.tar.gz" .

echo "Checkpoint built at $CHECKPOINT_PATH & $CHECKPOINT_PATH.tar.gz"
