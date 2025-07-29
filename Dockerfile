# Multi-stage build for Istaroth MCP server
FROM python:3.12-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt

# Final stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app

# Create data directories for checkpoints and HuggingFace models
RUN mkdir -p /data/checkpoint /data/models/hf && \
    chown -R app:app /data

# Create app directory and set ownership
WORKDIR /app

# Copy only the necessary directories with correct ownership
COPY --chown=app:app istaroth/ ./istaroth/
COPY --chown=app:app scripts/ ./scripts/

# Copy and set up entrypoint script
COPY --chown=app:app scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set environment variables
ENV ISTAROTH_DOCUMENT_STORE=/data/checkpoint
ENV ISTAROTH_TRAINING_DEVICE=cpu
ENV HF_HOME=/data/models/hf

USER app

# Expose port for HTTP transport
EXPOSE 8000

# Set entrypoint to handle checkpoint downloading
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command runs the MCP server with streamable-http transport
CMD ["fastmcp", "run", "scripts/mcp_server.py", "--transport=streamable-http", "--host=0.0.0.0", "--port=8000"]
