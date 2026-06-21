"""Vector store implementations for RAG pipeline."""

import abc
import enum
import logging
import os
import pathlib
import shutil
import tempfile
from typing import Any, ClassVar, Self, cast

import attrs
import chromadb
import langsmith as ls
from langchain_core import embeddings as lc_embeddings
from langchain_core.documents import Document
from opentelemetry import trace

from istaroth import utils
from istaroth.rag import embeddings, types

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)


class VectorStoreType(enum.Enum):
    """Supported vector store types."""

    CHROMA = "chroma"
    CHROMA_EXTERNAL = "chroma_external"


def get_vector_store_type_from_env() -> VectorStoreType:
    """Parse ISTAROTH_VECTOR_STORE environment variable into VectorStoreType."""
    store_type = os.getenv("ISTAROTH_VECTOR_STORE", "chroma").lower()
    try:
        return VectorStoreType(store_type)
    except ValueError:
        raise ValueError(
            f"Unknown vector store type: {store_type}. "
            f"Supported: {', '.join(t.value for t in VectorStoreType)}"
        )


class VectorStore(abc.ABC):
    """Abstract base class for vector stores."""

    @abc.abstractmethod
    def search(self, query: str, k: int) -> list[types.ScoredChunk]:
        """Vector similarity search."""
        ...

    @abc.abstractmethod
    def save(self, path: pathlib.Path) -> None:
        """Save vector store."""
        ...

    @abc.abstractmethod
    def get_type(self) -> VectorStoreType:
        """Get the type of this vector store."""
        ...

    @classmethod
    @abc.abstractmethod
    def load(cls, path: pathlib.Path) -> Self:
        """Load vector store."""
        ...

    @classmethod
    @abc.abstractmethod
    def build(
        cls, documents: list[tuple[str, types.DocumentMetadata]], *, concurrency: int
    ) -> Self:
        """Build vector store from document tuples."""
        ...


@attrs.define
class ChromaBaseVectorStore(VectorStore):
    """Base class for ChromaDB-based vector stores."""

    COLLECTION_NAME: ClassVar[str] = "istaroth_documents"

    _embeddings: lc_embeddings.Embeddings = attrs.field()
    _client: chromadb.ClientAPI = attrs.field()
    _collection: chromadb.Collection = attrs.field()

    def search(self, query: str, k: int) -> list[types.ScoredChunk]:
        """Vector similarity search using ChromaDB."""
        with ls.trace(
            "vector_search",
            "retriever",
            inputs={"query": query, "k": k},
        ) as rt:
            # Compute query embedding
            with _tracer.start_as_current_span("embed_query") as span:
                span.set_attribute("query", query)
                query_embedding = self._embeddings.embed_query(query)

            # Search in Chroma
            with _tracer.start_as_current_span("chroma_query") as span:
                span.set_attribute("k", k)
                results = self._collection.query(
                    query_embeddings=cast(Any, [query_embedding]),
                    n_results=k,
                )

            # Build ScoredChunk references from Chroma results. Chroma stores
            # empty strings as documents (see build()), so we discard the
            # documents field entirely and reconstruct from metadata + distance.
            # Invert L2 distance (0 = identical) to a similarity score (1 = most similar)
            # so higher scores consistently mean better matches across all backends.
            scored_chunks = []
            metadatas = cast(list[list[Any]], results["metadatas"])[0]
            distances = cast(list[list[float]], results["distances"])[0]
            for i in range(len(metadatas)):
                score = 1.0 - distances[i]
                scored_chunks.append(
                    types.ScoredChunk(
                        score=score,
                        file_id=metadatas[i]["file_id"],
                        chunk_index=metadatas[i]["chunk_index"],
                    )
                )

            rt.end(
                outputs={
                    "documents": [sc.to_langsmith_output() for sc in scored_chunks]
                }
            )
            return scored_chunks


@attrs.define
class ChromaVectorStore(ChromaBaseVectorStore):
    """Vector similarity search using ChromaDB."""

    _chroma_data_dir: str = attrs.field()

    @classmethod
    def build(
        cls,
        documents: list[tuple[str, types.DocumentMetadata]],
        *,
        concurrency: int,
    ) -> "ChromaVectorStore":
        """Build vector store from document tuples."""
        with utils.timer(
            f"building Chroma vector store with {len(documents)} documents"
        ):
            with utils.timer("loading vector embeddings model"):
                emb = embeddings.create_embeddings()

            # Create persistent client in temporary directory
            chroma_data_dir = tempfile.mkdtemp(prefix="chroma_", dir="/tmp")
            client = chromadb.PersistentClient(path=chroma_data_dir)

            # Create or get collection
            collection = client.create_collection(
                name=cls.COLLECTION_NAME, metadata={"hnsw:space": "l2"}
            )

            with utils.timer("document vectorization"):
                texts = [text for text, _ in documents]
                metadatas = [metadata for _, metadata in documents]

                # Compute embeddings in parallel, bounded-size batches,
                # reusing cached vectors for unchanged chunk text when
                # ISTAROTH_EMBEDDING_CACHE is set.
                with embeddings.EmbeddingCache.from_env() as cache:
                    embeddings_list = cache.embed(emb, texts, concurrency=concurrency)

                # Add documents in batches to avoid ChromaDB batch size limits
                batch_size = 5000
                total_docs = len(documents)

                for i in range(0, total_docs, batch_size):
                    end_idx = min(i + batch_size, total_docs)
                    batch_texts = texts[i:end_idx]
                    batch_embeddings = embeddings_list[i:end_idx]
                    batch_metadatas = metadatas[i:end_idx]
                    batch_ids = [f"doc_{j}" for j in range(i, end_idx)]

                    logger.info(
                        "Adding batch %s/%s (%s documents)",
                        i // batch_size + 1,
                        (total_docs + batch_size - 1) // batch_size,
                        len(batch_texts),
                    )

                    # Store empty strings — Chroma's stored page_content is never
                    # consumed downstream; search returns ScoredChunk references
                    # that resolve to full Documents from DocumentStore._documents.
                    collection.add(
                        ids=batch_ids,
                        documents=[""] * len(batch_texts),
                        embeddings=cast(Any, batch_embeddings),
                        metadatas=cast(Any, batch_metadatas),
                    )

            return cls(emb, client, collection, chroma_data_dir)

    def save(self, path: pathlib.Path) -> None:
        """Save vector store."""
        shutil.copytree(
            self._chroma_data_dir, path / "chroma_index", dirs_exist_ok=True
        )

    def get_type(self) -> VectorStoreType:
        """Get the type of this vector store."""
        return VectorStoreType.CHROMA

    @classmethod
    def load(cls, path: pathlib.Path) -> "ChromaVectorStore":
        """Load vector store."""
        with utils.timer(f"loading Chroma vector store from {path}"):
            # Create embeddings instance
            with utils.timer("loading vector embeddings model"):
                emb = embeddings.create_embeddings()

            with utils.timer("loading Chroma index"):
                chroma_data_dir = str(path / "chroma_index")
                client = chromadb.PersistentClient(path=chroma_data_dir)
                collection = client.get_collection(cls.COLLECTION_NAME)

            return cls(emb, client, collection, chroma_data_dir)


@attrs.define
class ChromaExternalVectorStore(ChromaBaseVectorStore):
    """Vector similarity search using external ChromaDB server."""

    @classmethod
    def create(cls, host: str, port: int) -> "ChromaExternalVectorStore":
        """Create external vector store connecting to Chroma server."""
        with utils.timer("connecting to external Chroma server"):
            with utils.timer("loading vector embeddings model"):
                emb = embeddings.create_embeddings()

            # Connect to external Chroma server
            client = chromadb.HttpClient(host=host, port=port)

            # Get existing collection (assume it exists)
            collection = client.get_collection(name=cls.COLLECTION_NAME)

            return cls(emb, client, collection)

    @classmethod
    def build(
        cls, documents: list[tuple[str, types.DocumentMetadata]], *, concurrency: int
    ) -> Self:
        """Not supported for external vector store."""
        del documents, concurrency  # Unused parameters
        raise NotImplementedError(
            "build() is not supported for external Chroma store. "
            "Use create() with an API address instead."
        )

    def save(self, path: pathlib.Path) -> None:
        """Not supported for external vector store."""
        del path  # Unused parameter
        raise NotImplementedError(
            "save() is not supported for external Chroma store. "
            "Data is stored on the external server."
        )

    def get_type(self) -> VectorStoreType:
        """Get the type of this vector store."""
        return VectorStoreType.CHROMA_EXTERNAL

    @classmethod
    def load(cls, path: pathlib.Path) -> "ChromaExternalVectorStore":
        """Not supported for external vector store."""
        del path  # Unused parameter
        raise NotImplementedError(
            "load() is not supported for external Chroma store. "
            "Use create() with an API address instead."
        )
