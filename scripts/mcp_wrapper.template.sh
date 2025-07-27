#!/bin/bash

# Set your environment variables here
export ISTORATH_DOCUMENT_STORE="/path/to/checkpoint" # REPLACE
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
