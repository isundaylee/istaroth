"""Embedding backend selection for RAG pipeline."""

import abc
import functools
import hashlib
import logging
import os
import pathlib

import anyio
import attrs
import numpy as np
import pydantic
from langchain_core import embeddings as lc_embeddings

from istaroth import utils

logger = logging.getLogger(__name__)

_EMBED_BATCH_SIZE = 256
"""Texts per embedding request when building, to bound each API request."""


@functools.cache
def create_embeddings() -> lc_embeddings.Embeddings:
    """Create embeddings instance based on ISTAROTH_EMBEDDINGS env var.

    - "local" (default): HuggingFace BAAI/bge-m3
    - "deepinfra": DeepInfra-hosted BAAI/bge-m3 via OpenAI-compatible API
    """
    match (backend := os.environ.get("ISTAROTH_EMBEDDINGS", "local")):
        case "local":
            from langchain_huggingface import HuggingFaceEmbeddings

            logger.info("Using local HuggingFace embeddings")
            return HuggingFaceEmbeddings(
                model_name="BAAI/bge-m3",
                model_kwargs={"device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")},
                encode_kwargs={"normalize_embeddings": True},
            )
        case "deepinfra":
            from langchain_openai import OpenAIEmbeddings

            logger.info("Using DeepInfra embeddings")
            return OpenAIEmbeddings(
                base_url="https://api.deepinfra.com/v1/openai",
                model="BAAI/bge-m3",
                api_key=pydantic.SecretStr(os.environ["DEEPINFRA_API_KEY"]),
                check_embedding_ctx_length=False,
            )
        case _:
            raise ValueError(f"Unknown ISTAROTH_EMBEDDINGS: {backend}")


async def _aembed_documents_batched(
    emb: lc_embeddings.Embeddings, texts: list[str], *, concurrency: int
) -> list[list[float]]:
    batches = [
        texts[i : i + _EMBED_BATCH_SIZE]
        for i in range(0, len(texts), _EMBED_BATCH_SIZE)
    ]
    results: list[list[list[float]] | None] = [None] * len(batches)
    limiter = anyio.CapacityLimiter(concurrency)
    log_every = max(1, len(batches) // 20)
    done_batches = 0
    done_docs = 0

    async def _embed(idx: int, batch: list[str]) -> None:
        nonlocal done_batches, done_docs
        async with limiter:
            results[idx] = await emb.aembed_documents(batch)
        done_batches += 1
        done_docs += len(batch)
        if done_batches % log_every == 0 or done_batches == len(batches):
            logger.info(
                "Embedded %d/%d documents (%d/%d batches)",
                done_docs,
                len(texts),
                done_batches,
                len(batches),
            )

    async with anyio.create_task_group() as tg:
        for idx, batch in enumerate(batches):
            tg.start_soon(_embed, idx, batch)

    flattened: list[list[float]] = []
    for batch_result in results:
        assert batch_result is not None
        flattened.extend(batch_result)
    return flattened


def _embed_parallel(
    emb: lc_embeddings.Embeddings, texts: list[str], *, concurrency: int
) -> list[list[float]]:
    """Embed texts in bounded batches with up to ``concurrency`` requests in flight."""
    return anyio.run(
        functools.partial(
            _aembed_documents_batched, emb, texts, concurrency=concurrency
        )
    )


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingCache(abc.ABC):
    """Embedding helper, optionally backed by a content-addressed disk cache.

    Use as a context manager; persistent variants save on clean exit:

        with EmbeddingCache.from_env() as cache:
            vectors = cache.embed(emb, texts, concurrency=8)
    """

    @abc.abstractmethod
    def embed(
        self, emb: lc_embeddings.Embeddings, texts: list[str], *, concurrency: int
    ) -> list[list[float]]:
        """Embed ``texts``, reusing cached vectors when available."""

    def __enter__(self) -> "EmbeddingCache":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self._save()

    def _save(self) -> None:
        """Persist the cache; no-op unless overridden."""

    @classmethod
    def from_env(cls) -> "EmbeddingCache":
        """Build a file-backed cache from ``ISTAROTH_EMBEDDING_CACHE``, else a no-op."""
        if path := os.environ.get("ISTAROTH_EMBEDDING_CACHE"):
            return _FileEmbeddingCache(pathlib.Path(path))
        return _NoopEmbeddingCache()


class _NoopEmbeddingCache(EmbeddingCache):
    """Embeds without caching."""

    def embed(
        self, emb: lc_embeddings.Embeddings, texts: list[str], *, concurrency: int
    ) -> list[list[float]]:
        return _embed_parallel(emb, texts, concurrency=concurrency)


@attrs.define
class _FileEmbeddingCache(EmbeddingCache):
    """Content-addressed embedding cache persisted to a .npz file.

    Vectors are keyed by text hash, so unchanged chunks (and duplicate chunks
    within a build) are embedded at most once. On exit the cache is rewritten
    restricted to the texts seen this session, keeping it bounded to the live
    corpus.
    """

    _path: pathlib.Path = attrs.field()
    _cache: dict[str, list[float]] = attrs.field(init=False)
    _seen: set[str] = attrs.field(init=False, factory=set)

    @_cache.default
    def _load_cache(self) -> dict[str, list[float]]:
        if not self._path.exists():
            logger.info("Embedding cache: no existing cache at %s", self._path)
            return {}
        with utils.timer("loading embedding cache"):
            with np.load(self._path, allow_pickle=False) as data:
                cache = {
                    str(key): vector.tolist()
                    for key, vector in zip(data["keys"], data["vectors"])
                }
        logger.info(
            "Embedding cache: loaded %d cached vectors from %s", len(cache), self._path
        )
        return cache

    def embed(
        self, emb: lc_embeddings.Embeddings, texts: list[str], *, concurrency: int
    ) -> list[list[float]]:
        hashes = [_text_hash(t) for t in texts]
        self._seen.update(hashes)

        # Unique texts missing from the cache (dedups repeated chunks too).
        missing: dict[str, str] = {}
        for h, text in zip(hashes, texts):
            if h not in self._cache:
                missing.setdefault(h, text)

        reused = sum(1 for h in hashes if h not in missing)
        logger.info(
            "Embedding cache: reused %d/%d chunks (%.1f%% hit rate), "
            "%d unique texts to compute",
            reused,
            len(texts),
            100.0 * reused / len(texts) if texts else 0.0,
            len(missing),
        )

        if missing:
            missing_hashes = list(missing)
            self._cache.update(
                zip(
                    missing_hashes,
                    _embed_parallel(
                        emb,
                        [missing[h] for h in missing_hashes],
                        concurrency=concurrency,
                    ),
                )
            )

        return [self._cache[h] for h in hashes]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        keys = list(self._seen)
        with utils.timer("saving embedding cache"):
            with self._path.open("wb") as f:
                np.savez(
                    f,
                    keys=np.array(keys),
                    vectors=np.array([self._cache[k] for k in keys], dtype=np.float32),
                )
        logger.info("Embedding cache: saved %d vectors to %s", len(keys), self._path)
