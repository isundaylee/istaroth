#!/bin/bash

# Set your environment variables here
# Comma-separated list of language checkpoints, e.g. CHS:/path/to/chs_checkpoint,ENG:/path/to/eng_checkpoint
export ISTAROTH_DOCUMENT_STORE_SET="CHS:/path/to/chs_checkpoint" # REPLACE
# Language used by the MCP server (must be one of the supported languages, e.g. CHS or ENG)
export ISTAROTH_MCP_LANGUAGE="CHS" # REPLACE
export GOOGLE_API_KEY="your-google-api-key-here"  # REPLACE

# Optional: Set LangSmith tracing environment variables if you want to enable tracing
# export LANGSMITH_API_KEY="your-langsmith-api-key"
# export LANGCHAIN_PROJECT="your-langsmith-project-name"
# export LANGCHAIN_TRACING_V2="true"

# Navigate to the project root directory (parent of this script)
cd "$(dirname "$0")/.."

# Activate the virtual environment
source env/bin/activate

# Run the MCP server
scripts/mcp_server.py
