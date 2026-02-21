"""FastAPI embedding microservice that serves vector embeddings."""

import pydantic
from fastapi import FastAPI

from istaroth.rag import vector_store


class _EmbedQueryRequest(pydantic.BaseModel):
    text: str


class _EmbedQueryResponse(pydantic.BaseModel):
    embedding: list[float]


class _EmbedDocumentsRequest(pydantic.BaseModel):
    texts: list[str]


class _EmbedDocumentsResponse(pydantic.BaseModel):
    embeddings: list[list[float]]


def create_app() -> FastAPI:
    """Create the embedding service FastAPI application."""
    app = FastAPI(
        title="Istaroth Embedding Service",
        description="Microservice for computing text embeddings",
        version="1.0.0",
    )

    embeddings = vector_store._create_local_embeddings()

    @app.post("/embed/query")
    def embed_query(request: _EmbedQueryRequest) -> _EmbedQueryResponse:
        return _EmbedQueryResponse(
            embedding=embeddings.embed_query(request.text),
        )

    @app.post("/embed/documents")
    def embed_documents(
        request: _EmbedDocumentsRequest,
    ) -> _EmbedDocumentsResponse:
        return _EmbedDocumentsResponse(
            embeddings=embeddings.embed_documents(request.texts),
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
