"""LangSmith tracing configuration for RAG pipeline."""

import logging
import os
import typing

logger = logging.getLogger(__name__)


REQUIRED_TRACING_ENV_VARS = [
    "LANGSMITH_API_KEY",
    "LANGCHAIN_PROJECT",
    "LANGCHAIN_TRACING_V2",
]

OPTIONAL_TRACING_ENV_VARS = [
    "LANGSMITH_ENDPOINT",
]


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled."""
    return os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"


def get_trace_url() -> typing.Optional[str]:
    """Get trace URL if available."""
    if not is_tracing_enabled():
        return None

    project = os.getenv("LANGCHAIN_PROJECT")
    endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

    if not project:
        return None

    # Remove trailing slash and api path if present
    base_url = endpoint.rstrip("/").replace("/api", "")
    return f"{base_url}/o/default/projects/p/{project}"
