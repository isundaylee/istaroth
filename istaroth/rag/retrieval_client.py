"""HTTP client for the retrieval microservice, implementing the Retriever protocol."""

import logging
import os

import httpx
from langchain_core.documents import Document

from istaroth.rag import types

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120.0


class RetrievalClient:
    """Thin HTTP client that talks to the retrieval microservice."""

    def __init__(self, base_url: str, language: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._language = language.upper()
        self._client = httpx.Client(base_url=self._base_url, timeout=_DEFAULT_TIMEOUT)

    @classmethod
    def from_env(cls, language: str) -> "RetrievalClient":
        url = os.environ.get("ISTAROTH_RETRIEVAL_SERVICE_URL")
        if not url:
            raise ValueError("ISTAROTH_RETRIEVAL_SERVICE_URL is required")
        return cls(url, language)

    def retrieve(
        self, query: str, *, k: int, chunk_context: int
    ) -> types.RetrieveOutput:
        resp = self._client.post(
            "/retrieve",
            json={
                "language": self._language,
                "query": query,
                "k": k,
                "chunk_context": chunk_context,
            },
        )
        resp.raise_for_status()
        return types.RetrieveOutput.from_dict(resp.json())

    def retrieve_bm25(
        self, query: str, *, k: int, chunk_context: int
    ) -> types.RetrieveOutput:
        resp = self._client.post(
            "/retrieve_bm25",
            json={
                "language": self._language,
                "query": query,
                "k": k,
                "chunk_context": chunk_context,
            },
        )
        resp.raise_for_status()
        return types.RetrieveOutput.from_dict(resp.json())

    def get_file_chunks(self, file_id: str) -> list[Document] | None:
        resp = self._client.post(
            "/get_file_chunks",
            json={"language": self._language, "file_id": file_id},
        )
        resp.raise_for_status()
        data = resp.json()
        if data["chunks"] is None:
            return None
        return [
            Document(page_content=doc["page_content"], metadata=doc["metadata"])
            for doc in data["chunks"]
        ]

    def get_chunk(self, file_id: str, chunk_index: int) -> Document | None:
        resp = self._client.post(
            "/get_chunk",
            json={
                "language": self._language,
                "file_id": file_id,
                "chunk_index": chunk_index,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data["chunk"] is None:
            return None
        return Document(
            page_content=data["chunk"]["page_content"],
            metadata=data["chunk"]["metadata"],
        )

    def get_file_chunk_count(self, file_id: str) -> int | None:
        resp = self._client.post(
            "/get_file_chunk_count",
            json={"language": self._language, "file_id": file_id},
        )
        resp.raise_for_status()
        return resp.json()["count"]

    @property
    def num_documents(self) -> int:
        resp = self._client.post(
            "/num_documents",
            json={"language": self._language},
        )
        resp.raise_for_status()
        return resp.json()["num_documents"]
