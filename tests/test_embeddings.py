"""Tests for embedding cache."""

import pathlib
from typing import cast

import pytest
from langchain_core import embeddings as lc_embeddings

from istaroth.rag import embeddings


class _FakeEmbeddings:
    """Records every text it embeds; vector encodes the text length."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.extend(texts)
        return [[float(len(t)), 1.0] for t in texts]


def _fake() -> tuple["_FakeEmbeddings", lc_embeddings.Embeddings]:
    fake = _FakeEmbeddings()
    return fake, cast(lc_embeddings.Embeddings, fake)


def test_file_embedding_cache_reuses_and_prunes(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """File-backed cache embeds each text once, reuses across sessions, and prunes."""
    monkeypatch.setenv("ISTAROTH_EMBEDDING_CACHE", str(tmp_path / "cache.npz"))

    # First build: duplicate "alpha" embedded once; "gamma" present too.
    emb1, emb1_typed = _fake()
    with embeddings.EmbeddingCache.from_env() as cache:
        result1 = cache.embed(
            emb1_typed, ["alpha", "beta", "alpha", "gamma"], concurrency=2
        )
    assert sorted(emb1.calls) == ["alpha", "beta", "gamma"]
    assert result1[0] == result1[2]

    # Second build: "alpha"/"beta" reused from disk, only "delta" computed;
    # "gamma" drops out of the corpus and must be pruned from the cache.
    emb2, emb2_typed = _fake()
    with embeddings.EmbeddingCache.from_env() as cache:
        result2 = cache.embed(emb2_typed, ["alpha", "beta", "delta"], concurrency=2)
    assert emb2.calls == ["delta"]
    assert result2[0] == result1[0]

    emb3, emb3_typed = _fake()
    with embeddings.EmbeddingCache.from_env() as cache:
        cache.embed(emb3_typed, ["gamma"], concurrency=1)
    assert emb3.calls == ["gamma"]  # gamma was pruned, so it must be recomputed
