"""Tests for RAG types module."""

from langchain_core.documents import Document

from istaroth.rag import types


def test_retrieve_output_serialization():
    """Test RetrieveOutput to_dict and from_dict methods."""
    # Create test documents
    doc1 = Document(
        page_content="Test content 1",
        metadata={
            "source": "test1.txt",
            "type": "document",
            "filename": "test1.txt",
            "file_id": "id1",
            "chunk_index": 0,
        },
    )
    doc2 = Document(
        page_content="Test content 2",
        metadata={
            "source": "test2.txt",
            "type": "document",
            "filename": "test2.txt",
            "file_id": "id2",
            "chunk_index": 1,
        },
    )

    # Create RetrieveOutput with test data
    query = types.RetrieveQuery(query="test query", k=2, chunk_context=5)
    original = types.RetrieveOutput(
        query=query, results=[(0.95, [doc1, doc2]), (0.80, [doc1])]
    )

    # Test serialization
    assert types.RetrieveOutput.from_dict(original.to_dict()) == original


def test_retrieve_output_total_documents():
    """Test RetrieveOutput total_documents property."""
    doc1 = Document(page_content="Test 1", metadata={})
    doc2 = Document(page_content="Test 2", metadata={})
    doc3 = Document(page_content="Test 3", metadata={})

    query = types.RetrieveQuery(query="total documents test", k=3, chunk_context=5)
    output = types.RetrieveOutput(
        query=query, results=[(0.9, [doc1, doc2]), (0.8, [doc3])]
    )

    assert output.total_documents == 3
