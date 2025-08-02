"""Document store and embedding utilities for RAG pipeline."""

import json
import logging
import os
import pathlib
import uuid
from typing import cast

import attrs
import jieba
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from istaroth.langsmith_utils import traceable
from istaroth.rag import types

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

    @traceable(name="vector_search")  # type: ignore[misc]
    def search(self, query: str, k: int) -> list[types.ScoredDocument]:
        """Vector similarity search."""
        results = self._vector_store.similarity_search_with_score(query, k=k)
        return [
            types.ScoredDocument(document=doc, score=score) for doc, score in results
        ]

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

    _bm25_retriever: BM25Retriever = attrs.field()

    @classmethod
    def build(cls, documents: dict[str, dict[int, Document]]) -> "_BM25Store":
        """Build BM25 store from documents."""
        all_docs = [doc for docs in documents.values() for doc in docs.values()]
        bm25_retriever = BM25Retriever.from_documents(
            all_docs, preprocess_func=_chinese_tokenizer
        )
        return cls(bm25_retriever)

    @traceable(name="bm25_search")  # type: ignore[misc]
    def search(self, query: str, k: int) -> list[types.ScoredDocument]:
        """BM25 keyword search."""
        docs = self._bm25_retriever.invoke(query, k=k)
        return [types.ScoredDocument(document=doc, score=1.0) for doc in docs]


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


@attrs.define
class DocumentStore:
    """A document store using FAISS for vector similarity search."""

    _vector_store: _VectorStore = attrs.field()
    _bm25_store: _BM25Store = attrs.field()

    _documents: dict[str, dict[int, Document]] = attrs.field()
    _full_texts: dict[str, str] = attrs.field()

    @classmethod
    def build(
        cls, file_paths: list[pathlib.Path], show_progress: bool = False
    ) -> "DocumentStore":
        """Build a document store from file paths."""
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ""],
            chunk_size=300,
            chunk_overlap=100,
            length_function=len,
            is_separator_regex=False,
        )

        all_chunks = []
        all_metadatas = []
        all_documents = {}
        full_texts = {}

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

                    all_chunks.append(chunk)
                    all_metadatas.append(metadata)

                    doc = Document(page_content=chunk, metadata=metadata)
                    file_docs[chunk_index] = doc

                all_documents[file_id] = file_docs
                full_texts[file_id] = content.strip()

            except Exception as e:
                logger.warning("Failed to read %s: %s", file_path, e)
                continue

        logger.info("Added %d chunks from %d files", len(all_chunks), len(file_paths))

        vector_store = _VectorStore.build(all_chunks, all_metadatas)
        bm25_store = _BM25Store.build(all_documents)

        return cls(vector_store, bm25_store, all_documents, full_texts)

    @traceable(name="hybrid_search")
    def retrieve(
        self, query: str, *, k: int, chunk_offset: int = 5
    ) -> list[tuple[float, list[Document]]]:
        """Search using hybrid vector + BM25 retrieval with reciprocal rank fusion."""
        # Get results from both retrievers (these return chunk content)
        vector_results = self._vector_store.search(query, k * 2)
        bm25_results = self._bm25_store.search(query, k * 2)

        # Combine using reciprocal rank fusion with equal weights
        fused_results = _reciprocal_rank_fusion(
            [vector_results, bm25_results], weights=[0.5, 0.5]
        )

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
                max(metadata["chunk_index"] - chunk_offset, 0),
                min(metadata["chunk_index"] + chunk_offset + 1, len(file_docs)),
            ):
                final_chunk_indices[file_id].add(chunk_index)

        return [
            (
                score,
                [
                    self._documents[file_id][chunk_index]
                    for chunk_index in sorted(final_chunk_indices[file_id])
                ],
            )
            for score, file_id in final_file_ids
        ]

    def search_fulltext(self, query: str) -> list[str]:
        """Full-text case-insensitive search for documents containing the query string."""
        results = []
        search_query = query.lower()

        for content in self._full_texts.values():
            if search_query in content.lower():
                results.append(content)

        return results

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

        # Write out full texts
        (path / "full_texts.json").write_text(json.dumps(self._full_texts))

    @classmethod
    def load(cls, path: pathlib.Path) -> "DocumentStore":
        """Load document store from a directory."""
        # Load full texts
        full_texts_file = path / "full_texts.json"
        if full_texts_file.exists():
            with open(full_texts_file, "r") as f:
                full_texts = json.load(f)
        else:
            full_texts = {}

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
        bm25_store = _BM25Store.build(documents)

        instance = cls(vector_store, bm25_store, documents, full_texts)
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
            return cls.load(store_path)
        else:
            # Create empty store
            empty_vector_store = _VectorStore.build([], [])
            empty_bm25_store = _BM25Store.build({})
            return cls(empty_vector_store, empty_bm25_store, {}, {})

    def save_to_env(self) -> None:
        """Save DocumentStore to path specified by ISTAROTH_DOCUMENT_STORE env var."""
        store_path = get_document_store_path()
        store_path.mkdir(parents=True, exist_ok=True)
        self.save(store_path)
