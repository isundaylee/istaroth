"""FastAPI application for the Istaroth RAG backend."""

from fastapi import FastAPI

from istaroth.services.backend.routers import (
    citations,
    conversations,
    examples,
    models,
    query,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Istaroth Web API",
        description="API for the Istaroth Web",
        version="1.0.0",
    )

    # Include routers (routes define full paths)
    app.include_router(query.router, tags=["query"])
    app.include_router(conversations.router, tags=["conversations"])
    app.include_router(models.router, tags=["models"])
    app.include_router(examples.router, tags=["examples"])
    app.include_router(citations.router, tags=["citations"])

    return app
