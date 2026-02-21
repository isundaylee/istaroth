"""Remote embeddings client that delegates to an embedding microservice."""

import httpx
from langchain_core import embeddings


class RemoteEmbeddings(embeddings.Embeddings):
    """LangChain Embeddings implementation backed by a remote HTTP service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=300.0)

    def embed_query(self, text: str) -> list[float]:
        response = self._client.post("/embed/query", json={"text": text})
        response.raise_for_status()
        return response.json()["embedding"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post("/embed/documents", json={"texts": texts})
        response.raise_for_status()
        return response.json()["embeddings"]
