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
    original = types.RetrieveOutput(results=[(0.95, [doc1, doc2]), (0.80, [doc1])])

    # Test serialization
    data = original.to_dict()

    # Verify structure
    assert "results" in data
    assert len(data["results"]) == 2

    # Check first result
    result1 = data["results"][0]
    assert result1["score"] == 0.95
    assert len(result1["documents"]) == 2
    assert result1["documents"][0]["page_content"] == "Test content 1"
    assert result1["documents"][0]["metadata"]["source"] == "test1.txt"

    # Check second result
    result2 = data["results"][1]
    assert result2["score"] == 0.80
    assert len(result2["documents"]) == 1
    assert result2["documents"][0]["page_content"] == "Test content 1"

    # Test deserialization
    restored = types.RetrieveOutput.from_dict(data)

    # Verify restored object matches original
    assert len(restored.results) == 2

    # Check first result
    score1, docs1 = restored.results[0]
    assert score1 == 0.95
    assert len(docs1) == 2
    assert docs1[0].page_content == "Test content 1"
    assert docs1[0].metadata["source"] == "test1.txt"
    assert docs1[1].page_content == "Test content 2"

    # Check second result
    score2, docs2 = restored.results[1]
    assert score2 == 0.80
    assert len(docs2) == 1
    assert docs2[0].page_content == "Test content 1"
    assert docs2[0].metadata["source"] == "test1.txt"


def test_retrieve_output_empty():
    """Test RetrieveOutput serialization with empty results."""
    original = types.RetrieveOutput(results=[])

    data = original.to_dict()
    assert data == {"results": []}

    restored = types.RetrieveOutput.from_dict(data)
    assert restored.results == []


def test_retrieve_output_total_documents():
    """Test RetrieveOutput total_documents property."""
    doc1 = Document(page_content="Test 1", metadata={})
    doc2 = Document(page_content="Test 2", metadata={})
    doc3 = Document(page_content="Test 3", metadata={})

    output = types.RetrieveOutput(results=[(0.9, [doc1, doc2]), (0.8, [doc3])])

    assert output.total_documents == 3
