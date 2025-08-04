"""Document store and embedding utilities for RAG pipeline."""

import json
import logging
import os
import pathlib
import uuid
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

from istaroth.langsmith_utils import traceable
from istaroth.rag import query_transform, types

logger = logging.getLogger(__name__)


def _chinese_tokenizer(text: str) -> list[str]:
    """Tokenize Chinese text using jieba."""
    return list(jieba.cut(text))


@attrs.define
class _VectorStore:
    """Vector similarity search using FAISS."""

    _embeddings: HuggingFaceEmbeddings = attrs.field()
    _vector_store: FAISS = attrs.field()

    @classmethod
    def build(
        cls, texts: list[str], metadatas: list[types.DocumentMetadata]
    ) -> "_VectorStore":
        """Build vector store from texts and metadatas."""
        embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")},
            encode_kwargs={"normalize_embeddings": True},
        )
        vector_store = FAISS.from_texts(
            texts=texts,
            embedding=embeddings,
            metadatas=cast(list[dict], metadatas),
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
        # Create embeddings instance
        embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")},
            encode_kwargs={"normalize_embeddings": True},
        )

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
        # Tokenize all document contents for BM25
        tokenized_corpus = [_chinese_tokenizer(doc.page_content) for doc in documents]

        # Create BM25Okapi instance
        bm25 = BM25Okapi(tokenized_corpus)

        return cls(bm25, documents)

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
            scored_docs = list(zip(scores, self._documents))

            # Sort by score (descending) and take top k
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            top_docs = scored_docs[:k]

            # Return as ScoredDocument objects
            scored_docs = [
                types.ScoredDocument(document=doc, score=float(score))
                for score, doc in top_docs
            ]
            rt.end(
                outputs={"documents": [sd.to_langsmith_output() for sd in scored_docs]}
            )
            return scored_docs


def _reciprocal_rank_fusion(
    results: list[list[types.ScoredDocument]], weights: list[float], k: int = 60
) -> list[types.ScoredDocument]:
    """Combine multiple retrieval results using reciprocal rank fusion.

    Args:
        results: List of result lists from different retrievers
        weights: Weights for each retriever
        k: Constant added to rank (default 60)

    Returns:
        Fused results sorted by score
    """
    doc_scores: dict[str, tuple[float, Document]] = {}

    for retriever_results, weight in zip(results, weights):
        for rank, scored_doc in enumerate(retriever_results, 1):
            score = weight / (k + rank)
            content = scored_doc.document.page_content
            if content in doc_scores:
                # Update score, keep first document encountered
                doc_scores[content] = (
                    doc_scores[content][0] + score,
                    doc_scores[content][1],
                )
            else:
                doc_scores[content] = (score, scored_doc.document)

    # Sort by combined score (highest first) and return with document
    sorted_results = sorted(doc_scores.items(), key=lambda x: x[1][0], reverse=True)
    return [
        types.ScoredDocument(document=doc, score=score)
        for _, (score, doc) in sorted_results
    ]


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

    for file_path in tqdm(
        file_paths, desc="Reading & chunking files", disable=not show_progress
    ):
        try:
            content = file_path.read_text(encoding="utf-8")
            file_id = str(uuid.uuid4())
            chunks = text_splitter.split_text(content.strip())

            file_docs = dict[int, Document]()
            for chunk_index, chunk in enumerate(chunks):
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

        except Exception as e:
            logger.warning("Failed to read %s: %s", file_path, e)
            continue

    total_chunks = sum(len(docs) for docs in all_documents.values())
    logger.info("Splitted %d chunks from %d files", total_chunks, len(file_paths))
    return all_documents


@attrs.define
class DocumentStore:
    """A document store using FAISS for vector similarity search."""

    _vector_store: _VectorStore = attrs.field()
    _bm25_store: _BM25Store = attrs.field()
    _query_transformer: query_transform.QueryTransformer = attrs.field()

    _documents: dict[str, dict[int, Document]] = attrs.field()

    @classmethod
    def build(
        cls,
        file_paths: list[pathlib.Path],
        *,
        chunk_size_multiplier: float,
        query_transformer: query_transform.QueryTransformer | None = None,
        show_progress: bool = False,
    ) -> "DocumentStore":
        """Build a document store from file paths."""
        all_documents = chunk_documents(
            file_paths,
            chunk_size_multiplier=chunk_size_multiplier,
            show_progress=show_progress,
        )

        # Extract chunks and metadatas from all_documents
        all_chunks = [
            doc.page_content
            for file_docs in all_documents.values()
            for doc in file_docs.values()
        ]
        all_metadatas = [
            cast(types.DocumentMetadata, doc.metadata)
            for file_docs in all_documents.values()
            for doc in file_docs.values()
        ]
        flattened_documents = [
            doc for file_docs in all_documents.values() for doc in file_docs.values()
        ]

        vector_store = _VectorStore.build(all_chunks, all_metadatas)
        bm25_store = _BM25Store.build(flattened_documents)

        # Use provided query transformer or default to identity transformer
        if query_transformer is None:
            query_transformer = query_transform.IdentityTransformer()

        return cls(vector_store, bm25_store, query_transformer, all_documents)

    @traceable(name="hybrid_search")
    def retrieve(
        self, query: str, *, k: int, chunk_context: int = 5
    ) -> types.RetrieveOutput:
        """Search using hybrid vector + BM25 retrieval with reciprocal rank fusion."""
        # Transform the query into multiple queries
        queries = self._query_transformer.transform(query)

        logger.info("Transformed query '%s' into: %r", query, queries)

        # Collect all results from all queries
        all_results = []

        for transformed_query in queries:
            # Get results from both retrievers for this query
            vector_results = self._vector_store.search(transformed_query, k * 2)
            bm25_results = self._bm25_store.search(transformed_query, k * 2)

            # Add both vector and BM25 results to the collection
            all_results.extend([vector_results, bm25_results])

        # Combine all results using reciprocal rank fusion with equal weights
        # Each query contributes equally, with vector and BM25 weighted equally within each query
        weights = [0.5 / len(queries)] * len(all_results)
        fused_results = _reciprocal_rank_fusion(all_results, weights)

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
            results=[
                (
                    score,
                    [
                        self._documents[file_id][chunk_index]
                        for chunk_index in sorted(final_chunk_indices[file_id])
                    ],
                )
                for score, file_id in final_file_ids
            ]
        )

    def save(self, path: pathlib.Path) -> None:
        """Save the document store to a directory."""
        # Save stores
        self._vector_store.save(path)

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
        query_transformer: query_transform.QueryTransformer | None = None,
    ) -> "DocumentStore":
        """Load document store from a directory."""

        # Load documents to build BM25 store
        documents_file = path / "documents.json"
        if documents_file.exists():
            documents = {
                cast(str, file_id): {
                    cast(int, doc["metadata"]["chunk_index"]): Document(
                        page_content=doc["page_content"], metadata=doc["metadata"]
                    )
                    for doc in file_docs
                }
                for file_id, file_docs in json.loads(documents_file.read_text()).items()
            }
        else:
            documents = {}

        # Load stores
        vector_store = _VectorStore.load(path)
        flattened_documents = [
            doc for file_docs in documents.values() for doc in file_docs.values()
        ]
        bm25_store = _BM25Store.build(flattened_documents)

        instance = cls(
            vector_store,
            bm25_store,
            query_transformer or query_transform.IdentityTransformer(),
            documents,
        )
        logger.info(
            "Loaded document store from %s with %d documents",
            path,
            instance.num_documents,
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
        store_path = get_document_store_path()

        if store_path.exists():
            match (qtv := os.environ.get("ISTAROTH_QUERY_TRANSFORMER", "identity")):
                case "identity":
                    query_transformer = query_transform.IdentityTransformer()
                case "rewrite":
                    query_transformer = query_transform.RewriteQueryTransformer.create()
                case _:
                    raise ValueError(f"Unknown ISTAROTH_QUERY_TRANSFORMER: {qtv}")

            return cls.load(store_path, query_transformer=query_transformer)
        else:
            # Create empty store
            empty_vector_store = _VectorStore.build([], [])
            empty_bm25_store = _BM25Store.build([])
            empty_query_transformer = query_transform.IdentityTransformer()
            return cls(
                empty_vector_store, empty_bm25_store, empty_query_transformer, {}
            )

    def save_to_env(self) -> None:
        """Save DocumentStore to path specified by ISTAROTH_DOCUMENT_STORE env var."""
        store_path = get_document_store_path()
        store_path.mkdir(parents=True, exist_ok=True)
        self.save(store_path)
