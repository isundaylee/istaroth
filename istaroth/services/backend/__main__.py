"""Entry point for running the Istaroth backend server."""

import fastapi

from istaroth.services.backend import app as app_module
from istaroth.services.backend import dependencies
from istaroth.services.common import runner, tracing


def _create_app_factory() -> fastapi.FastAPI:
    """Factory that initializes resources and creates the app (for uvicorn reload)."""
    tracing.setup_tracing("istaroth-backend")
    dependencies.init_resources()
    fastapi_app = app_module.create_app()
    tracing.instrument_fastapi_app(fastapi_app)
    return fastapi_app


if __name__ == "__main__":
    runner.run_service(
        service_name="istaroth-backend",
        factory_import_path="istaroth.services.backend.__main__:_create_app_factory",
        default_port=8000,
    )
