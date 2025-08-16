"""Document store and embedding utilities for RAG pipeline."""

import hashlib
import json
import logging
import os
import pathlib
import pickle
import time
from typing import cast

import attrs
import jieba
import langsmith as ls
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi
from tqdm import tqdm

from istaroth import langsmith_utils, utils
from istaroth.langsmith_utils import traceable
from istaroth.rag import query_transform, rerank, types

logger = logging.getLogger(__name__)


def _chinese_tokenizer(text: str) -> list[str]:
    """Tokenize Chinese text using jieba."""
    return list(jieba.cut(text))


def _merge_small_chunks(chunks: list[str], min_size: float) -> list[str]:
    """Merge chunks smaller than min_size with the next chunk."""
    merged_chunks = []
    i = 0
    while i < len(chunks):
        current_chunk = chunks[i]

        # Keep merging with next chunks until we get a chunk of sufficient size
        # or we reach the last chunk
        while len(current_chunk) < min_size and i + 1 < len(chunks):
            i += 1
            current_chunk += "\n\n" + chunks[i]

        merged_chunks.append(current_chunk)
        i += 1

    return merged_chunks


@attrs.define
class _VectorStore:
    """Vector similarity search using FAISS."""

    _embeddings: HuggingFaceEmbeddings = attrs.field()
    _vector_store: FAISS = attrs.field()

    @classmethod
    def build(
        cls, documents: list[tuple[str, types.DocumentMetadata]]
    ) -> "_VectorStore":
        """Build vector store from document tuples."""
        with utils.timer(f"building vector store with {len(documents)} documents"):
            with utils.timer("loading vector embeddings model"):
                embeddings = HuggingFaceEmbeddings(
                    model_name="BAAI/bge-m3",
                    model_kwargs={
                        "device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")
                    },
                    encode_kwargs={"normalize_embeddings": True},
                )

            with utils.timer("document vectorization"):
                vector_store = FAISS.from_texts(
                    texts=[text for text, _ in documents],
                    embedding=embeddings,
                    metadatas=cast(list[dict], [metadata for _, metadata in documents]),
                )

            return cls(embeddings, vector_store)

    def search(self, query: str, k: int) -> list[types.ScoredDocument]:
        """Vector similarity search."""
        with ls.trace(
            "vector_search",
            "retriever",
            inputs={"query": query, "k": k},
        ) as rt:
            results = self._vector_store.similarity_search_with_score(query, k=k)
            scored_docs = [
                types.ScoredDocument(document=doc, score=score)
                for doc, score in results
            ]
            rt.end(
                outputs={"documents": [sd.to_langsmith_output() for sd in scored_docs]}
            )
            return scored_docs

    def save(self, path: pathlib.Path) -> None:
        """Save vector store."""
        self._vector_store.save_local(str(path / "faiss_index"))

    @classmethod
    def load(cls, path: pathlib.Path) -> "_VectorStore":
        """Load vector store."""
        with utils.timer(f"loading vector store from {path}"):
            # Create embeddings instance
            with utils.timer("loading vector embeddings model"):
                embeddings = HuggingFaceEmbeddings(
                    model_name="BAAI/bge-m3",
                    model_kwargs={
                        "device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")
                    },
                    encode_kwargs={"normalize_embeddings": True},
                )

            with utils.timer("loading FAISS index"):
                vector_store = FAISS.load_local(
                    str(path / "faiss_index"),
                    embeddings=embeddings,
                    allow_dangerous_deserialization=True,
                )

            return cls(embeddings, vector_store)


@attrs.define
class _BM25Store:
    """BM25 keyword search store."""

    _bm25: BM25Okapi = attrs.field()
    _documents: list[Document] = attrs.field()

    @classmethod
    def build(cls, documents: list[Document]) -> "_BM25Store":
        """Build BM25 store from flattened list of documents."""
        with utils.timer(f"building BM25 store with {len(documents)} documents"):
            # Tokenize all document contents for BM25
            with utils.timer("document tokenization"):
                tokenized_corpus = [
                    _chinese_tokenizer(doc.page_content) for doc in documents
                ]

            # Create BM25Okapi instance
            with utils.timer("building BM25 index"):
                bm25 = BM25Okapi(tokenized_corpus)

            return cls(bm25, documents)

    def save(self, path: pathlib.Path) -> None:
        """Save BM25 store to disk using pickle."""
        with utils.timer("saving BM25 store"):
            bm25_file = path / "bm25_store.pkl"
            with open(bm25_file, "wb") as f:
                pickle.dump(self, f)

    @classmethod
    def load(cls, path: pathlib.Path) -> "_BM25Store":
        """Load BM25 store from disk using pickle."""
        with utils.timer("loading BM25 store"):
            bm25_file = path / "bm25_store.pkl"
            with open(bm25_file, "rb") as f:
                return pickle.load(f)

    def search(self, query: str, k: int) -> list[types.ScoredDocument]:
        """BM25 keyword search."""
        with ls.trace(
            "bm25_search",
            "retriever",
            inputs={"query": query, "k": k},
        ) as rt:
            # Tokenize the query
            tokenized_query = _chinese_tokenizer(query)

            # Get BM25 scores for all documents
            scores = self._bm25.get_scores(tokenized_query)

            # Create list of (score, document) pairs
            score_doc_pairs = list(zip(scores, self._documents))

            # Sort by score (descending) and take top k
            score_doc_pairs.sort(key=lambda x: x[0], reverse=True)
            top_docs = score_doc_pairs[:k]

            # Return as ScoredDocument objects
            scored_docs = [
                types.ScoredDocument(document=doc, score=float(score))
                for score, doc in top_docs
            ]
            rt.end(
                outputs={"documents": [sd.to_langsmith_output() for sd in scored_docs]}
            )
            return scored_docs


def get_document_store_path() -> pathlib.Path:
    """Get document store path from ISTAROTH_DOCUMENT_STORE environment variable."""
    path_str = os.getenv("ISTAROTH_DOCUMENT_STORE")
    if not path_str:
        raise ValueError(
            "ISTAROTH_DOCUMENT_STORE environment variable is required. "
            "Please set it to the path where the document database is stored."
        )
    return pathlib.Path(path_str)


def chunk_documents(
    file_paths: list[pathlib.Path],
    *,
    chunk_size_multiplier: float,
    show_progress: bool = False,
) -> dict[str, dict[int, Document]]:
    """Chunk documents from file paths.

    Returns:
        Dictionary of all_documents
    """
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ""],
        chunk_size=int(chunk_size_multiplier * 300),
        chunk_overlap=int(chunk_size_multiplier * 100),
        length_function=len,
        is_separator_regex=False,
    )

    all_documents = {}
    seen_basenames: dict[str, pathlib.Path] = {}

    for file_path in tqdm(
        file_paths, desc="Reading & chunking files", disable=not show_progress
    ):
        # Generate file ID from MD5 hash of basename
        basename = file_path.name
        file_id = hashlib.md5(basename.encode("utf-8")).hexdigest()

        # Check for duplicate basenames
        if file_id in seen_basenames:
            raise ValueError(
                f"Duplicate basename detected: '{basename}' "
                f"(current: {file_path}, previous: {seen_basenames[file_id]})"
            )
        seen_basenames[file_id] = file_path

        content = file_path.read_text(encoding="utf-8")
        chunks = text_splitter.split_text(content.strip())
        merged_chunks = _merge_small_chunks(chunks, 100 * chunk_size_multiplier)

        file_docs = dict[int, Document]()
        for chunk_index, chunk in enumerate(merged_chunks):
            metadata: types.DocumentMetadata = {
                "source": str(file_path),
                "type": "document",
                "filename": file_path.name,
                "file_id": file_id,
                "chunk_index": chunk_index,
            }

            doc = Document(page_content=chunk, metadata=metadata)
            file_docs[chunk_index] = doc

        all_documents[file_id] = file_docs

    total_chunks = sum(len(docs) for docs in all_documents.values())
    logger.info("Splitted %d chunks from %d files", total_chunks, len(file_paths))
    return all_documents


@attrs.define
class DocumentStore:
    """A document store using FAISS for vector similarity search."""

    _vector_store: _VectorStore
    _bm25_store: _BM25Store

    _query_transformer: query_transform.QueryTransformer
    _reranker: rerank.Reranker

    _documents: dict[str, dict[int, Document]]

    @classmethod
    def build(
        cls,
        file_paths: list[pathlib.Path],
        *,
        chunk_size_multiplier: float,
        query_transformer: query_transform.QueryTransformer | None = None,
        reranker: rerank.Reranker | None = None,
        show_progress: bool = False,
    ) -> "DocumentStore":
        """Build a document store from file paths."""
        all_documents = chunk_documents(
            file_paths,
            chunk_size_multiplier=chunk_size_multiplier,
            show_progress=show_progress,
        )

        # Extract chunks and metadatas from all_documents
        flattened_documents = [
            doc for file_docs in all_documents.values() for doc in file_docs.values()
        ]
        document_tuples = [
            (doc.page_content, cast(types.DocumentMetadata, doc.metadata))
            for doc in flattened_documents
        ]

        vector_store = _VectorStore.build(document_tuples)
        bm25_store = _BM25Store.build(flattened_documents)

        return cls(
            vector_store,
            bm25_store,
            query_transformer or query_transform.IdentityTransformer(),
            reranker or rerank.RRFReranker(),
            all_documents,
        )

    @traceable(name="hybrid_search")
    def retrieve(
        self, query: str, *, k: int, chunk_context: int = 5
    ) -> types.RetrieveOutput:
        """Search using hybrid vector + BM25 retrieval with reciprocal rank fusion."""
        # Transform the query into multiple queries
        queries = self._query_transformer.transform(query)

        logger.info("Transformed query '%s' into: %r", query, queries)

        # Collect all results from all queries
        weights = []
        all_results = []

        # Get vector store results for all queries.
        for transformed_query in queries:
            weights.append(1.0)
            all_results.append(self._vector_store.search(transformed_query, k * 2))

        # Only get BM25 results for the original query (with scaled up weight).
        weights.append(float(len(queries)))
        all_results.append(self._bm25_store.search(queries[0], k * 2))

        # Combine all results using reciprocal rank fusion with equal weights
        fused_results = self._reranker.rerank(query, all_results, weights)
        langsmith_utils.log_scored_docs("reranked_docs", fused_results)

        final_file_ids = list[tuple[float, str]]()
        final_chunk_indices = dict[str, set[int]]()
        for scored_doc in sorted(fused_results, key=lambda x: x.score, reverse=True):
            doc = scored_doc.document
            metadata = cast(types.DocumentMetadata, doc.metadata)
            file_id = metadata["file_id"]
            file_docs = self._documents[file_id]

            # For multiple retrieved docs from the same file, we use the highest
            # score for now.
            if file_id not in final_chunk_indices:
                if len(final_file_ids) == k:
                    break

                final_file_ids.append((scored_doc.score, file_id))
                final_chunk_indices[file_id] = set()

            for chunk_index in range(
                max(metadata["chunk_index"] - chunk_context, 0),
                min(metadata["chunk_index"] + chunk_context + 1, len(file_docs)),
            ):
                final_chunk_indices[file_id].add(chunk_index)

        return types.RetrieveOutput(
            query=types.RetrieveQuery(
                query=query,
                k=k,
                chunk_context=chunk_context,
            ),
            results=[
                (
                    score,
                    [
                        self._documents[file_id][chunk_index]
                        for chunk_index in sorted(final_chunk_indices[file_id])
                    ],
                )
                for score, file_id in final_file_ids
            ],
        )

    def save(self, path: pathlib.Path) -> None:
        """Save the document store to a directory."""
        # Save stores
        self._vector_store.save(path)
        self._bm25_store.save(path)

        # Write out documents
        (path / "documents.json").write_text(
            json.dumps(
                {
                    file_id: [
                        {
                            "page_content": doc.page_content,
                            "metadata": doc.metadata,
                        }
                        for doc in docs.values()
                    ]
                    for file_id, docs in self._documents.items()
                }
            )
        )

    @classmethod
    def load(
        cls,
        path: pathlib.Path,
        *,
        query_transformer: query_transform.QueryTransformer | None,
        reranker: rerank.Reranker | None,
    ) -> "DocumentStore":
        """Load document store from a directory."""
        with utils.timer(f"loading document store from {path}"):
            # Load documents
            with utils.timer("loading documents"):
                documents_file = path / "documents.json"
                documents = {
                    cast(str, file_id): {
                        cast(int, doc["metadata"]["chunk_index"]): Document(
                            page_content=doc["page_content"],
                            metadata=doc["metadata"],
                        )
                        for doc in file_docs
                    }
                    for file_id, file_docs in json.loads(
                        documents_file.read_text()
                    ).items()
                }

            # Load stores
            vector_store = _VectorStore.load(path)
            bm25_store = _BM25Store.load(path)

            instance = cls(
                vector_store,
                bm25_store,
                query_transformer or query_transform.IdentityTransformer(),
                reranker or rerank.RRFReranker(),
                documents,
            )

            logger.info(
                "Document store loaded with %d documents", instance.num_documents
            )
            return instance

    @property
    def num_documents(self) -> int:
        """Number of documents in the store."""
        return sum(len(docs) for docs in self._documents.values())

    @classmethod
    def from_env(cls) -> "DocumentStore":
        """Create DocumentStore from ISTAROTH_DOCUMENT_STORE environment variable.

        Loads existing store if path exists, otherwise creates new empty store.
        """
        with utils.timer("document store initialization from environment"):
            store_path = get_document_store_path()

            query_transformer = query_transform.QueryTransformer.from_env()
            reranker = rerank.Reranker.from_env()

            if store_path.exists():
                logger.info("Found existing document store at %s", store_path)
                result = cls.load(
                    store_path, query_transformer=query_transformer, reranker=reranker
                )
            else:
                logger.info("Creating empty document store (no existing store found)")
                # Create empty store
                result = cls(
                    _VectorStore.build([]),
                    _BM25Store.build([]),
                    query_transformer,
                    reranker,
                    {},
                )

            return result

    def save_to_env(self) -> None:
        """Save DocumentStore to path specified by ISTAROTH_DOCUMENT_STORE env var."""
        store_path = get_document_store_path()
        store_path.mkdir(parents=True, exist_ok=True)
        self.save(store_path)

    def get_chunk(self, file_id: str, chunk_index: int) -> Document | None:
        """Get a specific chunk from a file."""
        if file_id not in self._documents:
            return None

        file_docs = self._documents[file_id]
        return file_docs.get(chunk_index)

    def get_file_chunks(self, file_id: str) -> list[Document] | None:
        """Get all chunks from a specific file.

        Args:
            file_id: The file ID (MD5 hash)

        Returns:
            List of all Document objects or None if file not found
        """
        if file_id not in self._documents:
            return None

        file_docs = self._documents[file_id]
        return [file_docs[i] for i in sorted(file_docs.keys())]

    def get_file_chunk_count(self, file_id: str) -> int | None:
        """Get the total number of chunks for a specific file."""
        if file_id not in self._documents:
            return None

        return len(self._documents[file_id])
