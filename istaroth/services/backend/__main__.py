"""Entry point for running the Istaroth backend server."""

import fastapi

from istaroth.services.common import runner, tracing


def _create_app_factory() -> fastapi.FastAPI:
    """Factory that initializes resources and creates the app (for uvicorn reload).

    The heavy RAG stack is imported here rather than at module top level so the
    uvicorn ``--reload`` parent process (which only spawns the worker and never
    calls this factory) avoids loading it; only the worker pays the import cost.
    """
    # Deferred: see docstring — keeps the reload parent's import light.
    from istaroth.services.backend import app as app_module
    from istaroth.services.backend import dependencies

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
