"""Vector store implementations for RAG pipeline."""

import abc
import enum
import logging
import os
import pathlib
import shutil
import tempfile
from typing import ClassVar, Self, cast

import attrs
import chromadb
import langsmith as ls
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from istaroth import utils
from istaroth.rag import types

logger = logging.getLogger(__name__)


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
    def search(self, query: str, k: int) -> list[types.ScoredDocument]:
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
    def build(cls, documents: list[tuple[str, types.DocumentMetadata]]) -> Self:
        """Build vector store from document tuples."""
        ...

    @classmethod
    def _create_embeddings(cls) -> HuggingFaceEmbeddings:
        """Create HuggingFace embeddings instance."""
        return HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")},
            encode_kwargs={"normalize_embeddings": True},
        )


@attrs.define
class ChromaBaseVectorStore(VectorStore):
    """Base class for ChromaDB-based vector stores."""

    COLLECTION_NAME: ClassVar[str] = "istaroth_documents"

    _embeddings: HuggingFaceEmbeddings = attrs.field()
    _client: chromadb.ClientAPI = attrs.field()
    _collection: chromadb.Collection = attrs.field()

    def search(self, query: str, k: int) -> list[types.ScoredDocument]:
        """Vector similarity search using ChromaDB."""
        with ls.trace(
            "vector_search",
            "retriever",
            inputs={"query": query, "k": k},
        ) as rt:
            # Compute query embedding
            query_embedding = self._embeddings.embed_query(query)

            # Search in Chroma
            results = self._collection.query(
                query_embeddings=[query_embedding], n_results=k
            )

            # Convert results to ScoredDocument format
            scored_docs = []
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            for i in range(len(documents)):
                doc = Document(page_content=documents[i], metadata=metadatas[i])
                score = distances[i]
                scored_docs.append(types.ScoredDocument(document=doc, score=score))

            rt.end(
                outputs={"documents": [sd.to_langsmith_output() for sd in scored_docs]}
            )
            return scored_docs


@attrs.define
class ChromaVectorStore(ChromaBaseVectorStore):
    """Vector similarity search using ChromaDB."""

    _chroma_data_dir: str = attrs.field()

    @classmethod
    def build(
        cls, documents: list[tuple[str, types.DocumentMetadata]]
    ) -> "ChromaVectorStore":
        """Build vector store from document tuples."""
        with utils.timer(
            f"building Chroma vector store with {len(documents)} documents"
        ):
            with utils.timer("loading vector embeddings model"):
                embeddings = cls._create_embeddings()

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

                # Compute embeddings
                embeddings_list = embeddings.embed_documents(texts)

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

                    collection.add(
                        ids=batch_ids,
                        documents=batch_texts,
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                    )

            return cls(embeddings, client, collection, chroma_data_dir)

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
                embeddings = cls._create_embeddings()

            with utils.timer("loading Chroma index"):
                chroma_data_dir = str(path / "chroma_index")
                client = chromadb.PersistentClient(path=chroma_data_dir)
                collection = client.get_collection(cls.COLLECTION_NAME)

            return cls(embeddings, client, collection, chroma_data_dir)


@attrs.define
class ChromaExternalVectorStore(ChromaBaseVectorStore):
    """Vector similarity search using external ChromaDB server."""

    @classmethod
    def create(cls, host: str, port: int) -> "ChromaExternalVectorStore":
        """Create external vector store connecting to Chroma server."""
        with utils.timer("connecting to external Chroma server"):
            with utils.timer("loading vector embeddings model"):
                embeddings = cls._create_embeddings()

            # Connect to external Chroma server
            client = chromadb.HttpClient(host=host, port=port)

            # Get existing collection (assume it exists)
            collection = client.get_collection(name=cls.COLLECTION_NAME)

            return cls(embeddings, client, collection)

    @classmethod
    def build(cls, documents: list[tuple[str, types.DocumentMetadata]]) -> Self:
        """Not supported for external vector store."""
        del documents  # Unused parameter
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
