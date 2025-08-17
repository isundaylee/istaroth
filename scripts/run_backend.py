#!/usr/bin/env python3
"""Entry point script for running the Istaroth backend server."""

import logging
import pathlib
import sys

import click
import uvicorn

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.backend.app import create_app
from istaroth.backend.dependencies import init_resources


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8000, type=int, help="Port to bind the server to")
@click.option("--reload", is_flag=True, help="Enable auto-reload on code changes")
@click.option(
    "--log-level", default="info", help="Log level (debug, info, warning, error)"
)
def main(host: str, port: int, reload: bool, log_level: str) -> None:
    """Run the Istaroth FastAPI backend server."""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)

    # Log startup information
    logger.info("Starting Istaroth FastAPI backend server")
    logger.info("Server will run on %s:%d", host, port)
    logger.info("Auto-reload: %s", reload)
    logger.info("Log level: %s", log_level)

    # Initialize backend resources (database, document stores, LLM manager)
    init_resources()

    # Create and run the FastAPI application with uvicorn
    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
