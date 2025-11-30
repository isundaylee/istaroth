"""Document store and embedding utilities for RAG pipeline."""

import hashlib
import json
import logging
import os
import pathlib
import pickle
from typing import cast

import attrs
import jieba
import langsmith as ls
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi
from tqdm import tqdm

from istaroth import langsmith_utils, utils
from istaroth.langsmith_utils import traceable
from istaroth.rag import query_transform, rerank, types, vector_store

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
    text_root: pathlib.Path,
    chunk_size_multiplier: float,
    show_progress: bool = False,
) -> dict[str, dict[int, Document]]:
    """Chunk documents from file paths.

    Args:
        file_paths: List of absolute file paths to chunk
        text_root: Root directory for text files (used to compute relative paths)
        chunk_size_multiplier: Multiplier for chunk size
        show_progress: Whether to show progress bar

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
    seen_paths: dict[str, pathlib.Path] = {}

    for file_path in tqdm(
        file_paths, desc="Reading & chunking files", disable=not show_progress
    ):
        # Compute relative path from text root
        try:
            relative_path = str(file_path.relative_to(text_root))
        except ValueError:
            # If file is not under text_root, use absolute path
            relative_path = str(file_path)

        # Generate file ID from MD5 hash of path (not just basename)
        file_id = hashlib.md5(relative_path.encode("utf-8")).hexdigest()

        # Check for duplicate paths
        if file_id in seen_paths:
            raise ValueError(
                f"Duplicate path detected: '{relative_path}' "
                f"(current: {file_path}, previous: {seen_paths[file_id]})"
            )
        seen_paths[file_id] = file_path

        content = file_path.read_text(encoding="utf-8")
        chunks = text_splitter.split_text(content.strip())
        merged_chunks = _merge_small_chunks(chunks, 100 * chunk_size_multiplier)

        file_docs = dict[int, Document]()
        for chunk_index, chunk in enumerate(merged_chunks):
            metadata: types.DocumentMetadata = {
                "source": str(file_path),
                "type": "document",
                "path": relative_path,
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
    """A document store using ChromaDB for vector similarity search."""

    _vector_store: vector_store.VectorStore
    _bm25_store: _BM25Store

    _query_transformer: query_transform.QueryTransformer
    _reranker: rerank.Reranker

    _documents: dict[str, dict[int, Document]]

    @classmethod
    def build(
        cls,
        file_paths: list[pathlib.Path],
        *,
        text_root: pathlib.Path,
        chunk_size_multiplier: float,
        query_transformer: query_transform.QueryTransformer | None = None,
        reranker: rerank.Reranker | None = None,
        show_progress: bool = False,
    ) -> "DocumentStore":
        """Build a document store from file paths."""
        all_documents = chunk_documents(
            file_paths,
            text_root=text_root,
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

        # Create vector store based on environment variable
        store_type = vector_store.get_vector_store_type_from_env()
        vs: vector_store.VectorStore
        if store_type == vector_store.VectorStoreType.CHROMA:
            vs = vector_store.ChromaVectorStore.build(document_tuples)
        elif store_type == vector_store.VectorStoreType.CHROMA_EXTERNAL:
            raise RuntimeError("Cannot use external Chroma store when building.")
        else:
            raise ValueError(f"Unknown vector store type: {store_type}")

        bm25_store = _BM25Store.build(flattened_documents)

        return cls(
            vs,
            bm25_store,
            query_transformer or query_transform.IdentityTransformer(),
            reranker or rerank.RRFReranker(),
            all_documents,
        )

    @traceable(name="hybrid_search")
    def retrieve(
        self, query: str, *, k: int, chunk_context: int
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
        max_total_chunks = k * (2 * chunk_context + 1)
        total_chunks = 0

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

            # Calculate how many new chunks would be added
            new_chunk_indices = set()
            for chunk_index in range(
                max(metadata["chunk_index"] - chunk_context, 0),
                min(metadata["chunk_index"] + chunk_context + 1, len(file_docs)),
            ):
                if chunk_index not in final_chunk_indices[file_id]:
                    new_chunk_indices.add(chunk_index)

            # Add the new chunks
            final_chunk_indices[file_id].update(new_chunk_indices)
            total_chunks += len(new_chunk_indices)

            # Check if we've exceeded the limit after adding - if so, stop processing more
            if total_chunks >= max_total_chunks:
                break

        logger.info(
            "Selected %d total chunks between %d files",
            total_chunks,
            len(final_file_ids),
        )

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
        # Check if vector store supports saving
        if (
            self._vector_store.get_type()
            == vector_store.VectorStoreType.CHROMA_EXTERNAL
        ):
            raise NotImplementedError(
                "Cannot save DocumentStore with external Chroma vector store. "
                "External stores do not support persistence."
            )

        # Save stores
        self._vector_store.save(path)
        self._bm25_store.save(path)

        # Save configuration
        (path / "config.json").write_text(
            json.dumps({"vector_store_type": self._vector_store.get_type().value})
        )

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
        external_vector_store: vector_store.VectorStore | None = None,
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

            # Use explicit vector store if provided, otherwise load from config
            vs: vector_store.VectorStore
            if external_vector_store is None:
                # Load configuration to determine vector store type
                config = json.loads((path / "config.json").read_text())
                store_type = vector_store.VectorStoreType(config["vector_store_type"])

                # Load the appropriate vector store
                if store_type == vector_store.VectorStoreType.CHROMA:
                    vs = vector_store.ChromaVectorStore.load(path)
                elif store_type == vector_store.VectorStoreType.CHROMA_EXTERNAL:
                    raise ValueError("Cannot load external Chroma store.")
                else:
                    raise ValueError(f"Unknown vector store type: {store_type}")
            else:
                vs = external_vector_store

            bm25_store = _BM25Store.load(path)

            instance = cls(
                vs,
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

                # Create empty store based on environment variable
                vs: vector_store.VectorStore
                match (vst := vector_store.get_vector_store_type_from_env()):
                    case vector_store.VectorStoreType.CHROMA:
                        vs = vector_store.ChromaVectorStore.build([])
                    case vector_store.VectorStoreType.CHROMA_EXTERNAL:
                        raise ValueError(
                            "Cannot create external Chroma store from env."
                        )
                    case _:
                        # TODO figure out why assert_never did not work here
                        assert False, f"Unknown vector store type: {vst}"

                result = cls(
                    vs,
                    _BM25Store.build([]),
                    query_transformer,
                    reranker,
                    {},
                )

            return result

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
