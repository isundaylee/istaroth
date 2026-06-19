"""Tests for cached embedding resolution."""

import pathlib
from unittest import mock

from istaroth.rag import embedding_cache, embeddings


def test_embed_documents_with_cache_uses_cached_vectors(
    tmp_path: pathlib.Path,
) -> None:
    cache = embedding_cache.EmbeddingCache(tmp_path, namespace="test")
    cache.put("cached", [1.0, 2.0])
    cache.put("also cached", [3.0, 4.0])

    emb = mock.Mock()
    emb.aembed_documents = mock.AsyncMock(
        side_effect=lambda batch: [[5.0, 6.0] for _ in batch]
    )

    result = embeddings.embed_documents_with_cache(
        emb,
        ["cached", "new text", "also cached"],
        concurrency=1,
        cache=cache,
    )

    assert result == [[1.0, 2.0], [5.0, 6.0], [3.0, 4.0]]
    emb.aembed_documents.assert_awaited_once_with(["new text"])
    assert cache.get("new text") == [5.0, 6.0]
