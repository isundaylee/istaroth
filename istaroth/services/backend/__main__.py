"""Entry point for running the Istaroth backend server."""

import logging

import click
import fastapi
import uvicorn

from istaroth.services.backend import app as app_module
from istaroth.services.backend import dependencies
from istaroth.services.common import tracing


def _create_app_factory() -> fastapi.FastAPI:
    """Factory that initializes resources and creates the app (for uvicorn reload)."""
    tracing.setup_tracing("istaroth-backend")
    dependencies.init_resources()
    fastapi_app = app_module.create_app()
    tracing.instrument_fastapi_app(fastapi_app)
    return fastapi_app


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8000, type=int, help="Port to bind the server to")
@click.option("--reload", is_flag=True, help="Enable auto-reload on code changes")
@click.option(
    "--log-level", default="info", help="Log level (debug, info, warning, error)"
)
def main(host: str, port: int, reload: bool, log_level: str) -> None:
    """Run the Istaroth FastAPI backend server."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Istaroth FastAPI backend server on %s:%d", host, port)
    logger.info("Auto-reload: %s", reload)

    if reload:
        uvicorn.run(
            "istaroth.services.backend.__main__:_create_app_factory",
            factory=True,
            host=host,
            port=port,
            reload=True,
            log_level=log_level,
        )
    else:
        tracing.setup_tracing("istaroth-backend")
        dependencies.init_resources()
        fastapi_app = app_module.create_app()
        tracing.instrument_fastapi_app(fastapi_app)
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            log_level=log_level,
        )


if __name__ == "__main__":
    main()
