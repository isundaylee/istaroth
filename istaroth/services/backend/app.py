"""FastAPI application for the Istaroth RAG backend."""

import os
from contextlib import asynccontextmanager

import prometheus_client
from fastapi import FastAPI

from istaroth.services.backend.routers import (
    citations,
    conversations,
    examples,
    library,
    models,
    query,
    short_urls,
    version,
)
from istaroth.services.common import http_metrics_middleware


@asynccontextmanager
async def _lifespan(app: FastAPI):
    prometheus_client.start_http_server(
        int(os.environ.get("ISTAROTH_METRICS_PORT", "9100"))
    )
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Istaroth Web API",
        description="API for the Istaroth Web",
        version="1.0.0",
        lifespan=_lifespan,
    )

    app.add_middleware(http_metrics_middleware.HTTPMetricsMiddleware, service="backend")

    # Include routers (routes define full paths)
    app.include_router(query.router, tags=["query"])
    app.include_router(conversations.router, tags=["conversations"])
    app.include_router(models.router, tags=["models"])
    app.include_router(examples.router, tags=["examples"])
    app.include_router(citations.router, tags=["citations"])
    app.include_router(library.router, tags=["library"])
    app.include_router(short_urls.router, tags=["short-urls"])
    app.include_router(version.router, tags=["version"])

    return app
