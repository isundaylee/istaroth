"""Document store and embedding utilities for RAG pipeline."""

import json
import logging
import os
import pathlib
import uuid

import attrs
import jieba
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable
from tqdm import tqdm

from istaroth import utils

logger = logging.getLogger(__name__)


@attrs.define
class ScoredDocument:
    """Document with similarity score."""

    document: Document
    score: float


def _chinese_tokenizer(text: str) -> list[str]:
    """Tokenize Chinese text using jieba."""
    return list(jieba.cut(text))


def _reciprocal_rank_fusion(
    results: list[list[ScoredDocument]], weights: list[float], k: int = 60
) -> list[ScoredDocument]:
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
        ScoredDocument(document=doc, score=score) for _, (score, doc) in sorted_results
    ]


class DocumentStore:
    """A document store using FAISS for vector similarity search."""

    def __init__(self) -> None:
        """Initialize the document store with empty FAISS index."""
        self._embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")},
            encode_kwargs={"normalize_embeddings": True},  # For cosine similarity
        )
        # Simple newline-based splitting for dialogue structure
        # This works well with the corpus structure where each line is usually a complete dialogue
        self._text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ""],  # Only paragraph and line breaks
            chunk_size=300,
            chunk_overlap=100,
            length_function=len,
            is_separator_regex=False,
        )
        # Initialize vector store
        self._vector_store = self._init_vector_store()
        # Initialize BM25 retriever with placeholder document and Chinese tokenizer
        self._bm25_retriever = BM25Retriever.from_documents(
            [Document(page_content="placeholder")], preprocess_func=_chinese_tokenizer
        )
        self._documents: dict[str, list[Document]] = {}
        self._full_texts: dict[str, str] = {}

    def add_files(
        self, file_paths: list[pathlib.Path], show_progress: bool = False
    ) -> None:
        """Add multiple text files to the document store efficiently."""
        all_chunks = []
        all_metadatas = []
        all_documents = []

        for file_path in tqdm(
            file_paths, desc="Reading & chunking files", disable=not show_progress
        ):
            try:
                # Read file content using pathlib
                content = file_path.read_text(encoding="utf-8")

                # Generate unique file_id
                file_id = str(uuid.uuid4())

                # Split into chunks
                chunks = self._text_splitter.split_text(content.strip())

                # Create documents with structured metadata
                file_documents = []
                for chunk_index, chunk in enumerate(chunks):
                    metadata = {
                        "source": str(file_path),
                        "type": "document",
                        "filename": file_path.name,
                        "file_id": file_id,
                        "chunk_index": chunk_index,
                    }

                    # Collect for batch operations
                    all_chunks.append(chunk)
                    all_metadatas.append(metadata)

                    # Create document for BM25
                    doc = Document(page_content=chunk, metadata=metadata)
                    file_documents.append(doc)
                    all_documents.append(doc)

                # Store documents and full text by file_id
                self._documents[file_id] = file_documents
                self._full_texts[file_id] = content.strip()

            except Exception as e:
                logger.warning("Failed to read %s: %s", file_path, e)
                continue

        # Batch add to FAISS vector store
        assert len(all_chunks) == len(all_metadatas)
        for c, md in tqdm(
            zip(all_chunks, all_metadatas),
            desc="Adding into vector store",
            disable=not show_progress,
            total=len(all_chunks),
        ):
            self._vector_store.add_texts(texts=[c], metadatas=[md])

        # Rebuild BM25 with all documents from all files
        if all_documents:
            self._bm25_retriever = BM25Retriever.from_documents(
                all_documents, preprocess_func=_chinese_tokenizer
            )

        logger.info("Added %d chunks from %d files", len(all_chunks), len(file_paths))

    @traceable(name="hybrid_search")  # type: ignore[misc]
    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Search using hybrid vector + BM25 retrieval with reciprocal rank fusion."""
        # Get results from both retrievers (these return chunk content)
        vector_results = self._vector_search(query, k * 2)
        bm25_results = self._bm25_search(query, k * 2)

        # Combine using reciprocal rank fusion with equal weights
        fused_results = _reciprocal_rank_fusion(
            [vector_results, bm25_results], weights=[0.5, 0.5]
        )

        # Deduplicate by file_id first, keeping highest scored chunk per file
        file_scores: dict[str, float] = {}
        for scored_doc in fused_results:
            file_id = scored_doc.document.metadata["file_id"]  # Must have file_id
            if file_id not in file_scores or scored_doc.score > file_scores[file_id]:
                file_scores[file_id] = scored_doc.score

        # Sort by score, take first k, then compute full content only for selected files
        sorted_file_ids = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)[
            :k
        ]

        final_results = []
        for file_id, score in sorted_file_ids:
            final_results.append((self._full_texts[file_id], score))

        return final_results

    @traceable(name="vector_search")  # type: ignore[misc]
    def _vector_search(self, query: str, k: int) -> list[ScoredDocument]:
        """Vector similarity search."""
        results = self._vector_store.similarity_search_with_score(query, k=k)
        return [ScoredDocument(document=doc, score=score) for doc, score in results]

    @traceable(name="bm25_search")  # type: ignore[misc]
    def _bm25_search(self, query: str, k: int) -> list[ScoredDocument]:
        """BM25 keyword search."""
        docs = self._bm25_retriever.invoke(query, k=k)
        return [ScoredDocument(document=doc, score=1.0) for doc in docs]

    def search_fulltext(self, query: str) -> list[str]:
        """Full-text case-insensitive search for documents containing the query string."""
        results = []
        docstore = self._vector_store.docstore

        # Prepare query for comparison
        search_query = query.lower()

        # Search through all documents
        for doc_id in self._vector_store.index_to_docstore_id.values():
            doc = docstore.search(doc_id)
            if not doc or not hasattr(doc, "page_content"):
                continue

            # Check if query exists in content
            doc = utils.assert_is_instance(doc, Document)
            content = doc.page_content
            if search_query in content.lower():
                results.append(content)

        return results

    def save(self, path: pathlib.Path) -> None:
        """Save the document store to a directory."""
        # Save FAISS vector store
        self._vector_store.save_local(str(path / "faiss_index"))

        # Save documents and full texts (as JSON with file_id structure)
        documents_data = {}
        for file_id, docs in self._documents.items():
            documents_data[file_id] = [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in docs
            ]
        with open(path / "documents.json", "w") as f:
            json.dump(documents_data, f)

        # Save full texts separately
        with open(path / "full_texts.json", "w") as f:
            json.dump(self._full_texts, f)

    def load(self, path: pathlib.Path) -> None:
        """Load document store state from a directory."""
        # Load FAISS vector store
        self._vector_store = FAISS.load_local(
            str(path / "faiss_index"),
            embeddings=self._embeddings,
            allow_dangerous_deserialization=True,
        )

        # Load documents for BM25
        documents_file = path / "documents.json"
        if documents_file.exists():
            with open(documents_file, "r") as f:
                documents_data = json.load(f)

                # Load file_id -> list of documents format
                self._documents = {}
                for file_id, file_docs in documents_data.items():
                    self._documents[file_id] = [
                        Document(
                            page_content=doc["page_content"],
                            metadata=doc["metadata"],
                        )
                        for doc in file_docs
                    ]

            # Rebuild BM25 retriever with Chinese tokenizer
            all_docs = [doc for docs in self._documents.values() for doc in docs]
            if all_docs:
                self._bm25_retriever = BM25Retriever.from_documents(
                    all_docs, preprocess_func=_chinese_tokenizer
                )
        else:
            self._documents = {}

        # Load full texts
        full_texts_file = path / "full_texts.json"
        if full_texts_file.exists():
            with open(full_texts_file, "r") as f:
                self._full_texts = json.load(f)
        else:
            self._full_texts = {}

        logger.info(
            "Loaded document store from %s with %d documents", path, self.num_documents
        )

    def _init_vector_store(self) -> FAISS:
        """Initialize empty FAISS vector store."""
        # Pre-create FAISS store with placeholder text
        vector_store = FAISS.from_texts(
            texts=["placeholder"],
            embedding=self._embeddings,
            metadatas=[{"placeholder": True}],
        )
        # Clear all documents to have an empty store
        vector_store.delete(list(vector_store.index_to_docstore_id.values()))
        return vector_store

    def add_file(self, file_path: pathlib.Path) -> None:
        """Add a single text file to the document store. Use add_files for better performance."""
        self.add_files([file_path])

    @property
    def num_documents(self) -> int:
        """Number of documents in the store."""
        return sum(len(docs) for docs in self._documents.values())

    @classmethod
    def from_env(cls) -> "DocumentStore":
        """Create DocumentStore from ISTAROTH_DOCUMENT_STORE environment variable.

        Loads existing store if path exists, otherwise creates new empty store.
        """
        path_str = os.getenv("ISTAROTH_DOCUMENT_STORE")
        if not path_str:
            raise ValueError(
                "ISTAROTH_DOCUMENT_STORE environment variable is required. "
                "Please set it to the path where the document database is stored."
            )

        store_path = pathlib.Path(path_str)
        store = cls()

        if store_path.exists():
            store.load(store_path)

        return store

    def save_to_env(self) -> None:
        """Save DocumentStore to path specified by ISTAROTH_DOCUMENT_STORE env var."""
        path_str = os.getenv("ISTAROTH_DOCUMENT_STORE")
        if not path_str:
            raise ValueError(
                "ISTAROTH_DOCUMENT_STORE environment variable is required. "
                "Please set it to the path where the document database should be stored."
            )

        store_path = pathlib.Path(path_str)
        store_path.mkdir(parents=True, exist_ok=True)
        self.save(store_path)
