"""Tests for RemoteEmbeddings client."""

import httpx
import pytest

from istaroth.rag import remote_embeddings

_FAKE_REQUEST = httpx.Request("POST", "http://fake:8001/embed/query")


def test_embed_query(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [0.1, 0.2, 0.3]

    def _mock_post(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        assert url == "/embed/query"
        assert kwargs["json"] == {"text": "hello"}
        return httpx.Response(200, json={"embedding": expected}, request=_FAKE_REQUEST)

    monkeypatch.setattr(httpx.Client, "post", _mock_post)
    client = remote_embeddings.RemoteEmbeddings("http://fake:8001")
    assert client.embed_query("hello") == expected


def test_embed_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [[0.1, 0.2], [0.3, 0.4]]

    def _mock_post(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        assert url == "/embed/documents"
        assert kwargs["json"] == {"texts": ["a", "b"]}
        return httpx.Response(200, json={"embeddings": expected}, request=_FAKE_REQUEST)

    monkeypatch.setattr(httpx.Client, "post", _mock_post)
    client = remote_embeddings.RemoteEmbeddings("http://fake:8001")
    assert client.embed_documents(["a", "b"]) == expected


def test_embed_query_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _mock_post(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(500, json={"detail": "error"}, request=_FAKE_REQUEST)

    monkeypatch.setattr(httpx.Client, "post", _mock_post)
    client = remote_embeddings.RemoteEmbeddings("http://fake:8001")
    with pytest.raises(httpx.HTTPStatusError):
        client.embed_query("hello")
