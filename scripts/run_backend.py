#!/usr/bin/env python3
"""Entry point script for running the Istaroth backend server."""

import logging
import pathlib
import sys

import click

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.backend import app, config


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=5000, type=int, help="Port to bind the server to")
@click.option("--debug", is_flag=True, help="Run in debug mode")
def main(
    host: str,
    port: int,
    debug: bool,
) -> None:
    """Run the Istaroth backend server."""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create config from environment
    backend_config = config.BackendConfig.from_env()

    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("Starting Istaroth backend server")
    logger.info("Server will run on %s:%d", host, port)
    logger.info("Debug mode: %s", debug)

    # Create and run the application
    flask_app = app.create_app(backend_config)
    flask_app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
