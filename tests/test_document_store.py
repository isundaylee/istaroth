"""Tests for document store module."""

import hashlib
import pathlib
import tempfile

import pytest
from langchain_core.documents import Document

from istaroth.rag.document_store import _BM25Store, chunk_documents


def test_bm25_store_k():
    """Test that _BM25Store.search returns exactly k documents when k <= total documents."""
    # Create test documents with varying content
    documents = [
        Document(
            page_content="This is about apples and fruits",
            metadata={"file_id": "id1", "chunk_index": 0},
        ),
        Document(
            page_content="Bananas are yellow fruits",
            metadata={"file_id": "id2", "chunk_index": 0},
        ),
        Document(
            page_content="Oranges are citrus fruits",
            metadata={"file_id": "id3", "chunk_index": 0},
        ),
        Document(
            page_content="Vegetables are healthy food",
            metadata={"file_id": "id4", "chunk_index": 0},
        ),
        Document(
            page_content="Pizza is a delicious meal",
            metadata={"file_id": "id5", "chunk_index": 0},
        ),
        Document(
            page_content="Coffee is a popular beverage",
            metadata={"file_id": "id6", "chunk_index": 0},
        ),
        Document(
            page_content="Books contain knowledge and stories",
            metadata={"file_id": "id7", "chunk_index": 0},
        ),
        Document(
            page_content="Music brings joy to people",
            metadata={"file_id": "id8", "chunk_index": 0},
        ),
    ]

    # Build BM25 store
    bm25_store = _BM25Store.build(documents, text_path=pathlib.Path("."))

    # Test various k values
    test_cases = [1, 3, 5, 7, 8]  # Different k values including edge cases

    for k in test_cases:
        results = bm25_store.search("fruits", k=k)

        # Assert exactly k documents are returned
        assert len(results) == k, f"Expected {k} documents, got {len(results)}"

        # Ensure all results are ScoredChunk instances
        for result in results:
            assert hasattr(result, "score"), "Result should have score attribute"
            assert hasattr(result, "file_id"), "Result should have file_id attribute"
            assert hasattr(
                result, "chunk_index"
            ), "Result should have chunk_index attribute"
            assert isinstance(result.score, float), "Score should be a float"


def test_bm25_store_k_exceeds_total():
    """Test that _BM25Store.search returns all documents when k > total document count."""
    # Create fewer documents
    documents = [
        Document(
            page_content="Apple fruit", metadata={"file_id": "id1", "chunk_index": 0}
        ),
        Document(
            page_content="Banana fruit", metadata={"file_id": "id2", "chunk_index": 0}
        ),
        Document(
            page_content="Orange fruit", metadata={"file_id": "id3", "chunk_index": 0}
        ),
    ]

    # Build BM25 store
    bm25_store = _BM25Store.build(documents, text_path=pathlib.Path("."))

    # Request more documents than available
    k = 10
    results = bm25_store.search("fruit", k=k)

    # Should return all available documents (3), not k (10)
    assert len(results) == len(
        documents
    ), f"Expected {len(documents)} documents, got {len(results)}"


def test_bm25_store_with_empty_documents():
    """Test _BM25Store with empty document list."""
    documents: list[Document] = []

    # BM25Okapi raises ZeroDivisionError with empty corpus, so we expect this
    with pytest.raises(ZeroDivisionError):
        _BM25Store.build(documents, text_path=pathlib.Path("."))


def test_bm25_store_with_k_zero():
    """Test _BM25Store.search with k=0."""
    documents = [
        Document(
            page_content="Test content", metadata={"file_id": "id1", "chunk_index": 0}
        ),
    ]

    bm25_store = _BM25Store.build(documents, text_path=pathlib.Path("."))
    results = bm25_store.search("test", k=0)

    # Should return empty list
    assert len(results) == 0, "Expected 0 documents when k=0"


def test_chunk_documents_uses_md5_file_id():
    """Test that chunk_documents uses MD5 hash of path as file ID."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)

        # Create test file
        test_file = temp_path / "test_file.txt"
        test_file.write_text("This is a test document content.")

        # Expected MD5 hash of path (relative to text root)
        expected_file_id = hashlib.md5("test_file.txt".encode("utf-8")).hexdigest()

        # Chunk the document
        result = chunk_documents(
            [test_file], text_root=temp_path, chunk_size_multiplier=1.0
        )

        # Assert file ID is MD5 hash
        assert (
            expected_file_id in result
        ), f"Expected file ID {expected_file_id} not found"

        # Check that metadata contains correct file_id and path
        file_docs = result[expected_file_id]
        for doc in file_docs.values():
            assert doc.metadata["file_id"] == expected_file_id
            assert doc.metadata["path"] == "test_file.txt"


def test_chunk_documents_detects_duplicate_paths():
    """Test that chunk_documents raises ValueError for duplicate paths."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)

        # Create a test file
        test_file = temp_path / "test_file.txt"
        test_file.write_text("Content of test file")

        # Should raise ValueError when the same file appears multiple times in input list
        with pytest.raises(ValueError, match="Duplicate path detected"):
            chunk_documents(
                [test_file, test_file], text_root=temp_path, chunk_size_multiplier=1.0
            )
