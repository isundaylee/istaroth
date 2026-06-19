"""Persistent cache for chunk embeddings keyed by text content."""

import hashlib
import logging
import os
import pathlib
import pickle
import tempfile
import time

import attrs

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI-bge-m3"


def get_default_embedding_cache_dir() -> pathlib.Path:
    """Return the default embedding cache directory."""
    if cache_env := os.environ.get("ISTAROTH_EMBEDDING_CACHE"):
        return pathlib.Path(cache_env)
    return pathlib.Path.home() / ".cache" / "istaroth" / "embeddings"


def get_embedding_cache_namespace() -> str:
    """Return a namespace that distinguishes embedding backend/model."""
    backend = os.environ.get("ISTAROTH_EMBEDDINGS", "local")
    return f"{backend}_{_MODEL_NAME}"


@attrs.define(frozen=True)
class CacheLoadStats:
    """Timing and hit/miss stats for a batch of cache lookups."""

    hits: int
    misses: int
    lookup_seconds: float
    load_seconds: float

    @property
    def total_seconds(self) -> float:
        return self.lookup_seconds + self.load_seconds


@attrs.define
class EmbeddingCache:
    """Disk cache mapping chunk text to precomputed embedding vectors."""

    _root: pathlib.Path = attrs.field()
    _namespace: str = attrs.field(factory=get_embedding_cache_namespace)

    @property
    def _namespace_dir(self) -> pathlib.Path:
        return self._root / self._namespace

    def _path_for(self, text: str) -> pathlib.Path:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return self._namespace_dir / digest[:2] / f"{digest}.pkl"

    def get(self, text: str) -> list[float] | None:
        results, _ = self.get_many([text])
        return results[0]

    def get_many(
        self, texts: list[str]
    ) -> tuple[list[list[float] | None], CacheLoadStats]:
        """Look up embeddings for many texts, recording lookup and load timings."""
        results: list[list[float] | None] = []
        hits = 0
        misses = 0
        lookup_seconds = 0.0
        load_seconds = 0.0

        for text in texts:
            lookup_start = time.perf_counter()
            path = self._path_for(text)
            exists = path.exists()
            lookup_seconds += time.perf_counter() - lookup_start

            if not exists:
                misses += 1
                results.append(None)
                continue

            load_start = time.perf_counter()
            with open(path, "rb") as f:
                results.append(pickle.load(f))
            load_seconds += time.perf_counter() - load_start
            hits += 1

        return results, CacheLoadStats(
            hits=hits,
            misses=misses,
            lookup_seconds=lookup_seconds,
            load_seconds=load_seconds,
        )

    def put(self, text: str, embedding: list[float]) -> None:
        path = self._path_for(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, delete=False, suffix=".tmp"
        ) as f:
            pickle.dump(embedding, f)
            tmp_path = pathlib.Path(f.name)
        tmp_path.replace(path)
