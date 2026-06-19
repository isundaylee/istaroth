"""Embedding backend selection for RAG pipeline."""

import functools
import logging
import os
from typing import TYPE_CHECKING, cast

import anyio
import pydantic
from langchain_core import embeddings as lc_embeddings

if TYPE_CHECKING:
    from istaroth.rag import embedding_cache

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


def embed_documents_parallel(
    emb: lc_embeddings.Embeddings, texts: list[str], *, concurrency: int
) -> list[list[float]]:
    """Embed documents in bounded batches with up to ``concurrency`` requests in flight."""
    return anyio.run(
        functools.partial(
            _aembed_documents_batched, emb, texts, concurrency=concurrency
        )
    )


def embed_documents_with_cache(
    emb: lc_embeddings.Embeddings,
    texts: list[str],
    *,
    concurrency: int,
    cache: "embedding_cache.EmbeddingCache | None",
) -> list[list[float]]:
    """Embed documents, reusing cached vectors for unchanged chunk text."""
    if cache is None or not texts:
        return embed_documents_parallel(emb, texts, concurrency=concurrency)

    results: list[list[float] | None] = [None] * len(texts)
    miss_indices: list[int] = []
    miss_texts: list[str] = []

    cached_results, cache_stats = cache.get_many(texts)
    for i, cached in enumerate(cached_results):
        if cached is not None:
            results[i] = cached
        else:
            miss_indices.append(i)
            miss_texts.append(texts[i])

    total = len(texts)
    hit_rate = 100.0 * cache_stats.hits / total if total else 0.0
    logger.info(
        "Embedding cache loads: %d hits, %d misses (%.1f%% cached) in %.2fs "
        "(lookup %.2fs, read %.2fs)",
        cache_stats.hits,
        cache_stats.misses,
        hit_rate,
        cache_stats.total_seconds,
        cache_stats.lookup_seconds,
        cache_stats.load_seconds,
    )

    if miss_texts:
        new_embeddings = embed_documents_parallel(
            emb, miss_texts, concurrency=concurrency
        )
        for idx, embedding in zip(miss_indices, new_embeddings, strict=True):
            results[idx] = embedding
            cache.put(texts[idx], embedding)

    assert all(result is not None for result in results)
    return cast(list[list[float]], results)
