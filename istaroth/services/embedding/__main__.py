"""Entry point for running the Istaroth embedding microservice."""

import logging

import click
import uvicorn

from istaroth.services.embedding.app import create_app


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8001, type=int, help="Port to bind the server to")
@click.option(
    "--log-level", default="info", help="Log level (debug, info, warning, error)"
)
def main(host: str, port: int, log_level: str) -> None:
    """Run the Istaroth embedding microservice."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Istaroth embedding service on %s:%d", host, port)

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
