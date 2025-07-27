"""Document store and embedding utilities for RAG pipeline."""

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
            model_kwargs={"device": "mps"},
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
        # Track added texts by key to prevent duplicates
        self._added_texts: set[str] = set()

    def add_text(self, content: str, key: str, metadata: Optional[dict] = None) -> bool:
        """Add text content to the document store. Returns False if key already exists."""
        if key in self._added_texts:
            return False

        chunks = self._text_splitter.split_text(content)
        metadatas = [metadata or {} for _ in chunks]
        self._vector_store.add_texts(texts=chunks, metadatas=metadatas)
        self._added_texts.add(key)
        return True

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Search for similar documents."""
        results = self._vector_store.similarity_search_with_score(query, k=k)
        return [(doc.page_content, score) for doc, score in results]

    @property
    def num_documents(self) -> int:
        """Number of documents in the store."""
        return int(self._vector_store.index.ntotal)
