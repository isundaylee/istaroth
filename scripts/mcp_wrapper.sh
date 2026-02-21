#!/bin/bash
cd "$(dirname "$0")/.."
source .env.mcp
source .venv/bin/activate
scripts/mcp_server.py
