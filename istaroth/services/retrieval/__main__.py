"""Entry point for running the Istaroth retrieval microservice."""

import logging

import click
import uvicorn

from istaroth.rag import document_store_set
from istaroth.services.retrieval import app


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8002, type=int, help="Port to bind the server to")
@click.option(
    "--log-level", default="info", help="Log level (debug, info, warning, error)"
)
def main(host: str, port: int, log_level: str) -> None:
    """Run the Istaroth retrieval microservice."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Istaroth retrieval service on %s:%d", host, port)

    logger.info("Loading document store set from environment...")
    app._store_set = document_store_set.DocumentStoreSet.from_env()
    logger.info("Document store set loaded successfully")

    fastapi_app = app.create_app()
    uvicorn.run(fastapi_app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
