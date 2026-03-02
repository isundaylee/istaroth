"""Shared service runner for Istaroth microservices."""

import importlib
import logging

import click
import uvicorn


def run_service(
    *, service_name: str, factory_import_path: str, default_port: int
) -> None:
    """Run a FastAPI service with Click CLI, logging setup, and uvicorn startup."""

    @click.command()
    @click.option("--host", default="0.0.0.0", help="Host to bind the server to")
    @click.option(
        "--port", default=default_port, type=int, help="Port to bind the server to"
    )
    @click.option("--reload", is_flag=True, help="Enable auto-reload on code changes")
    @click.option(
        "--log-level", default="info", help="Log level (debug, info, warning, error)"
    )
    def _main(host: str, port: int, reload: bool, log_level: str) -> None:
        """Run the FastAPI service."""
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logging.getLogger(service_name).info(
            "Starting %s on %s:%d (reload=%s)", service_name, host, port, reload
        )
        if reload:
            uvicorn.run(
                factory_import_path,
                factory=True,
                host=host,
                port=port,
                reload=True,
                log_level=log_level,
            )
        else:
            module_path, func_name = factory_import_path.split(":")
            factory = getattr(importlib.import_module(module_path), func_name)
            uvicorn.run(factory(), host=host, port=port, log_level=log_level)

    _main()
