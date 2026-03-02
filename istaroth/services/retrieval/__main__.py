"""Entry point for running the Istaroth retrieval microservice."""

import logging

import fastapi

from istaroth.rag import document_store_set
from istaroth.services.common import runner, tracing
from istaroth.services.retrieval import app as app_module

_logger = logging.getLogger(__name__)


def _create_app_factory() -> fastapi.FastAPI:
    """Factory that initializes resources and creates the retrieval app (for uvicorn reload)."""
    tracing.setup_tracing("istaroth-retrieval")
    _logger.info("Loading document store set from environment...")
    app_module._store_set = document_store_set.DocumentStoreSet.from_env()
    _logger.info("Document store set loaded successfully")
    fastapi_app = app_module.create_app()
    tracing.instrument_fastapi_app(fastapi_app)
    return fastapi_app


if __name__ == "__main__":
    runner.run_service(
        service_name="istaroth-retrieval",
        factory_import_path="istaroth.services.retrieval.__main__:_create_app_factory",
        default_port=8002,
    )
