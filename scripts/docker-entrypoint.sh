#!/bin/bash
set -euo pipefail

# Default checkpoint URL if not provided
ISTAROTH_CHECKPOINT_URL="${ISTAROTH_CHECKPOINT_URL:-https://github.com/isundaylee/istaroth/releases/download/checkpoint%2F20250727-fd124af6572ba95981862799d7abf12e7508a5b3/chs-5.7.tar.gz}"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Check if /data/checkpoint is empty (allowing for hidden files like .gitkeep)
if [ -z "$(ls -A /data/checkpoint 2>/dev/null | grep -v '^\.')" ]; then
    log "Checkpoint directory is empty, downloading checkpoint from: $ISTAROTH_CHECKPOINT_URL"

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
else
    log "Checkpoint directory is not empty, skipping download"
    log "Existing files in /data/checkpoint:"
    ls -la /data/checkpoint | head -5
fi

# Execute the original command
log "Starting application: $*"
exec "$@"
