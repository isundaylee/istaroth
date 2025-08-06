#!/bin/bash
set -euo pipefail

# Default checkpoint URL if not provided
ISTAROTH_CHECKPOINT_URL="${ISTAROTH_CHECKPOINT_URL:-https://github.com/isundaylee/istaroth/releases/download/checkpoint%2F20250806-c7c76f4db72d57d9f4a06a8399694ad27eb7394d/chs.tar.gz}"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Function to download and extract checkpoint
download_checkpoint() {
    log "Downloading checkpoint from: $ISTAROTH_CHECKPOINT_URL"

    # Create temporary directory for download
    TEMP_DIR=$(mktemp -d)
    TEMP_FILE="$TEMP_DIR/checkpoint.tar.gz"

    # Set up cleanup trap
    cleanup() {
        log "Cleaning up temporary files..."
        rm -rf "$TEMP_DIR"
    }
    trap cleanup EXIT INT TERM

    # Download the checkpoint file
    log "Downloading checkpoint archive..."
    curl -L -o "$TEMP_FILE" "$ISTAROTH_CHECKPOINT_URL"

    log "Extracting checkpoint archive to /data/checkpoint..."

    # Extract the archive
    if tar -xzf "$TEMP_FILE" -C /data/checkpoint --strip-components=0; then
        # Extract and handle potential subdirectories
        log "Checkpoint extracted successfully"
    else
        log "ERROR: Invalid or corrupted tar.gz file"
        exit 1
    fi
}

# Check if checkpoint update is requested
if [ "${ISTAROTH_CHECKPOINT_UPDATE:-0}" = "1" ]; then
    log "ISTAROTH_CHECKPOINT_UPDATE=1, forcing checkpoint update"

    # Remove existing checkpoint directory and recreate it
    log "Removing existing checkpoint directory..."
    rm -rf /data/checkpoint
    mkdir -p /data/checkpoint

    download_checkpoint
elif [ -z "$(ls -A /data/checkpoint 2>/dev/null | grep -v '^\.')" ]; then
    log "Checkpoint directory is empty, downloading checkpoint"
    download_checkpoint
else
    log "Checkpoint directory is not empty, skipping download"
    log "Existing files in /data/checkpoint:"
    ls -la /data/checkpoint | head -5
fi

# Execute the original command
log "Starting application: $*"
exec "$@"
