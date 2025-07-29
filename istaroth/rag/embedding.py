"""Document store and embedding utilities for RAG pipeline."""

import json
import logging
import os
import pathlib

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

logger = logging.getLogger(__name__)


def _reciprocal_rank_fusion(
    results: list[list[tuple[str, float]]], weights: list[float], k: int = 60
) -> list[tuple[str, float]]:
    """Combine multiple retrieval results using reciprocal rank fusion.

    Args:
        results: List of result lists from different retrievers
        weights: Weights for each retriever
        k: Constant added to rank (default 60)

    Returns:
        Fused results sorted by score
    """
    doc_scores: dict[str, float] = {}

    for retriever_results, weight in zip(results, weights):
        for rank, (content, _) in enumerate(retriever_results, 1):
            score = weight / (k + rank)
            doc_scores[content] = doc_scores.get(content, 0) + score

    # Sort by combined score (highest first)
    return sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)


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
        # Initialize BM25 retriever with placeholder document
        self._bm25_retriever = BM25Retriever.from_documents(
            [Document(page_content="placeholder")]
        )
        self._documents: list[Document] = []

    def add_files(
        self, file_paths: list[pathlib.Path], show_progress: bool = False
    ) -> None:
        """Add multiple text files to the document store efficiently."""
        all_chunks = []
        all_metadatas = []
        all_documents = []

        for file_path in tqdm(
            file_paths, desc="Adding files", disable=not show_progress
        ):
            try:
                # Read file content using pathlib
                content = file_path.read_text(encoding="utf-8")

                # Create metadata
                metadata = {
                    "source": str(file_path),
                    "type": "document",
                    "filename": file_path.name,
                }

                # Split into chunks
                chunks = self._text_splitter.split_text(content.strip())
                metadatas = [metadata for _ in chunks]

                # Collect all chunks and metadata
                all_chunks.extend(chunks)
                all_metadatas.extend(metadatas)

                # Create documents for BM25
                for chunk, meta in zip(chunks, metadatas):
                    all_documents.append(Document(page_content=chunk, metadata=meta))

            except Exception as e:
                logger.warning("Failed to read %s: %s", file_path, e)
                continue

        # Batch add to FAISS vector store
        self._vector_store.add_texts(texts=all_chunks, metadatas=all_metadatas)

        # Add to document list and rebuild BM25 once
        self._documents.extend(all_documents)
        if self._documents:
            self._bm25_retriever = BM25Retriever.from_documents(self._documents)

        logger.info("Added %d chunks from %d files", len(all_chunks), len(file_paths))

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Search using hybrid vector + BM25 retrieval with reciprocal rank fusion."""
        if not self._documents:
            # Fallback to vector search only
            results = self._vector_store.similarity_search_with_score(query, k=k)
            return [(doc.page_content, score) for doc, score in results]

        # Get results from both retrievers
        vector_results = self._vector_store.similarity_search_with_score(query, k=k * 2)
        vector_results_formatted = [
            (doc.page_content, score) for doc, score in vector_results
        ]

        bm25_docs = self._bm25_retriever.invoke(query, k=k * 2)
        bm25_results_formatted = [(doc.page_content, 1.0) for doc in bm25_docs]

        # Combine using reciprocal rank fusion with equal weights
        fused_results = _reciprocal_rank_fusion(
            [vector_results_formatted, bm25_results_formatted], weights=[0.5, 0.5]
        )

        return fused_results[:k]

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
            content = doc.page_content
            if search_query in content.lower():
                results.append(content)

        return results

    def save(self, path: pathlib.Path) -> None:
        """Save the document store to a directory."""
        # Save FAISS vector store
        self._vector_store.save_local(str(path / "faiss_index"))

        # Save documents for BM25 (as JSON)
        documents_data = [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in self._documents
        ]
        with open(path / "documents.json", "w") as f:
            json.dump(documents_data, f)

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
                self._documents = [
                    Document(page_content=doc["page_content"], metadata=doc["metadata"])
                    for doc in documents_data
                ]

            # Rebuild BM25 retriever
            if self._documents:
                self._bm25_retriever = BM25Retriever.from_documents(self._documents)
        else:
            self._documents = []

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
        return int(self._vector_store.index.ntotal)

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
