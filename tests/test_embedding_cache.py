"""Tests for embedding cache."""

import pathlib

from istaroth.rag import embedding_cache


def test_embedding_cache_round_trip(tmp_path: pathlib.Path) -> None:
    cache = embedding_cache.EmbeddingCache(tmp_path, namespace="test")
    vector = [0.1, 0.2, 0.3]

    assert cache.get("unchanged chunk") is None
    cache.put("unchanged chunk", vector)
    assert cache.get("unchanged chunk") == vector
    assert cache.get("different chunk") is None


def test_embedding_cache_is_content_addressed(tmp_path: pathlib.Path) -> None:
    cache = embedding_cache.EmbeddingCache(tmp_path, namespace="test")
    cache.put("same text", [1.0, 2.0])
    cache.put("same text", [9.0, 8.0])

    assert cache.get("same text") == [9.0, 8.0]


def test_embedding_cache_namespaces_are_isolated(tmp_path: pathlib.Path) -> None:
    cache_a = embedding_cache.EmbeddingCache(tmp_path, namespace="backend_a")
    cache_b = embedding_cache.EmbeddingCache(tmp_path, namespace="backend_b")

    cache_a.put("shared text", [1.0])
    assert cache_b.get("shared text") is None


def test_embedding_cache_get_many_records_stats(tmp_path: pathlib.Path) -> None:
    cache = embedding_cache.EmbeddingCache(tmp_path, namespace="test")
    cache.put("hit", [1.0])

    results, stats = cache.get_many(["hit", "miss"])

    assert results == [[1.0], None]
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.total_seconds >= 0.0
    assert stats.lookup_seconds >= 0.0
    assert stats.load_seconds >= 0.0
