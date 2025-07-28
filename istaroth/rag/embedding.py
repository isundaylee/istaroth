"""Document store and embedding utilities for RAG pipeline."""

import json
import os
import pathlib
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentStore:
    """A document store using FAISS for vector similarity search."""

    def __init__(self) -> None:
        """Initialize the document store with empty FAISS index."""
        self._embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")},
            encode_kwargs={"normalize_embeddings": True},  # For cosine similarity
        )
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False,
        )
        # Pre-create FAISS store with placeholder text
        self._vector_store = FAISS.from_texts(
            texts=["placeholder"],
            embedding=self._embeddings,
            metadatas=[{"placeholder": True}],
        )
        # Clear all documents to have an empty store
        self._vector_store.delete(
            list(self._vector_store.index_to_docstore_id.values())
        )
        # Track added keys to prevent duplicates
        self._added_keys: set[str] = set()

    def add_text(self, content: str, key: str, metadata: Optional[dict] = None) -> bool:
        """Add text content to the document store. Returns False if key already exists."""
        if key in self._added_keys:
            return False

        chunks = self._text_splitter.split_text(content)
        metadatas = [metadata or {} for _ in chunks]
        self._vector_store.add_texts(texts=chunks, metadatas=metadatas)
        self._added_keys.add(key)
        return True

    def add_file(self, file_path: pathlib.Path) -> bool:
        """Add a text file to the document store.

        Returns True if added, False if already exists.
        Raises exception if file cannot be read.
        """
        # Read file content using pathlib
        content = file_path.read_text(encoding="utf-8")

        # Create metadata
        metadata = {
            "source": str(file_path),
            "type": "document",
            "filename": file_path.name,
        }

        # Use file path as unique key
        return self.add_text(content.strip(), key=str(file_path), metadata=metadata)

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Search for similar documents."""
        results = self._vector_store.similarity_search_with_score(query, k=k)
        return [(doc.page_content, score) for doc, score in results]

    def search_fulltext(self, query: str) -> list[str]:
        """Full-text case-insensitive search for documents containing the query string."""
        results = []
        docstore = self._vector_store.docstore

        # Prepare query for comparison
        search_query = query.lower()

        # Search through all documents
        for doc_id in self._vector_store.index_to_docstore_id.values():
            if not (doc := docstore.search(doc_id)):
                continue

            # Check if query exists in content
            content = doc.page_content
            if search_query in doc.page_content.lower():
                results.append(content)

        return results

    def save(self, path: pathlib.Path) -> None:
        """Save the document store to a directory."""
        # Save FAISS vector store
        self._vector_store.save_local(str(path / "faiss_index"))

        # Save added keys set as JSON
        with open(path / "added_keys.json", "w") as f:
            json.dump(list(self._added_keys), f)

    def load(self, path: pathlib.Path) -> None:
        """Load document store state from a directory."""
        # Load FAISS vector store
        self._vector_store = FAISS.load_local(
            str(path / "faiss_index"),
            embeddings=self._embeddings,
            allow_dangerous_deserialization=True,
        )

        # Load added keys set
        with open(path / "added_keys.json", "r") as f:
            added_keys_list = json.load(f)
            self._added_keys = set(added_keys_list)

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
