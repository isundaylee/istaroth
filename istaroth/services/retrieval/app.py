"""FastAPI retrieval microservice that serves hybrid (vector + BM25) search."""

import logging
from typing import Any

import pydantic
from fastapi import FastAPI, HTTPException

from istaroth.agd import localization
from istaroth.rag import document_store_set, types

logger = logging.getLogger(__name__)

_store_set: document_store_set.DocumentStoreSet | None = None


class _RetrieveRequest(pydantic.BaseModel):
    language: str
    query: str
    k: int
    chunk_context: int


class _GetFileChunksRequest(pydantic.BaseModel):
    language: str
    file_id: str


class _GetChunkRequest(pydantic.BaseModel):
    language: str
    file_id: str
    chunk_index: int


class _GetFileChunkCountRequest(pydantic.BaseModel):
    language: str
    file_id: str


class _NumDocumentsRequest(pydantic.BaseModel):
    language: str


def _get_store(language_str: str) -> types.Retriever:
    if _store_set is None:
        raise RuntimeError("Store set not initialized")
    try:
        lang = localization.Language(language_str.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid language: {language_str}")
    try:
        return _store_set.get_store(lang)
    except KeyError:
        raise HTTPException(
            status_code=400, detail=f"Language not available: {language_str}"
        )


def create_app() -> FastAPI:
    """Create the retrieval service FastAPI application."""
    app = FastAPI(
        title="Istaroth Retrieval Service",
        description="Microservice for hybrid (vector + BM25) document retrieval",
        version="1.0.0",
    )

    @app.post("/retrieve")
    def retrieve(request: _RetrieveRequest) -> dict[str, Any]:
        store = _get_store(request.language)
        output = store.retrieve(
            request.query, k=request.k, chunk_context=request.chunk_context
        )
        return output.to_dict()

    @app.post("/retrieve_bm25")
    def retrieve_bm25(request: _RetrieveRequest) -> dict[str, Any]:
        store = _get_store(request.language)
        output = store.retrieve_bm25(
            request.query, k=request.k, chunk_context=request.chunk_context
        )
        return output.to_dict()

    @app.post("/get_file_chunks")
    def get_file_chunks(request: _GetFileChunksRequest) -> dict[str, Any]:
        store = _get_store(request.language)
        chunks = store.get_file_chunks(request.file_id)
        return {
            "chunks": [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in chunks
            ]
            if chunks is not None
            else None
        }

    @app.post("/get_chunk")
    def get_chunk(request: _GetChunkRequest) -> dict[str, Any]:
        store = _get_store(request.language)
        chunk = store.get_chunk(request.file_id, request.chunk_index)
        return {
            "chunk": {"page_content": chunk.page_content, "metadata": chunk.metadata}
            if chunk is not None
            else None
        }

    @app.post("/get_file_chunk_count")
    def get_file_chunk_count(request: _GetFileChunkCountRequest) -> dict[str, Any]:
        store = _get_store(request.language)
        return {"count": store.get_file_chunk_count(request.file_id)}

    @app.post("/num_documents")
    def num_documents(request: _NumDocumentsRequest) -> dict[str, Any]:
        store = _get_store(request.language)
        return {"num_documents": store.num_documents}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
