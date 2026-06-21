"""Tests for output_rendering module."""

from langchain_core.documents import Document

from istaroth.rag.output_rendering import _deduplicate_chunk_overlaps


def _make_doc(
    chunk_index: int, content: str, start_index: int, end_index: int
) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source": "test",
            "type": "document",
            "path": "test/path",
            "file_id": "abc",
            "chunk_index": chunk_index,
            "start_index": start_index,
            "end_index": end_index,
        },
    )


def test_deduplicate_empty() -> None:
    assert _deduplicate_chunk_overlaps([]) == []


def test_deduplicate_single() -> None:
    doc = _make_doc(0, "hello", 0, 5)
    assert _deduplicate_chunk_overlaps([doc]) == [doc]


def test_deduplicate_no_overlap() -> None:
    d0 = _make_doc(0, "abcdef", 0, 6)
    d1 = _make_doc(1, "ghijkl", 6, 12)
    result = _deduplicate_chunk_overlaps([d0, d1])
    assert result == [d0, d1]
    assert result[1].page_content == "ghijkl"


def test_deduplicate_with_overlap() -> None:
    d0 = _make_doc(0, "abcdefghij", 0, 10)
    d1 = _make_doc(1, "fghijklmno", 5, 15)
    result = _deduplicate_chunk_overlaps([d0, d1])
    assert result is not [d0, d1]
    assert result[0] is d0
    assert result[1].page_content == "klmno"


def test_deduplicate_three_chunks_with_overlaps() -> None:
    d0 = _make_doc(0, "abcdefghij", 0, 10)
    d1 = _make_doc(1, "fghijklmno", 5, 15)
    d2 = _make_doc(2, "mnopqrstuv", 12, 22)
    result = _deduplicate_chunk_overlaps([d0, d1, d2])
    assert result[0] is d0
    assert result[1].page_content == "klmno"
    assert result[2].page_content == "pqrstuv"


def test_deduplicate_full_overlap() -> None:
    d0 = _make_doc(0, "abcdefghijklmno", 0, 15)
    d1 = _make_doc(1, "fghij", 5, 10)
    result = _deduplicate_chunk_overlaps([d0, d1])
    assert result[0] is d0
    assert result[1].page_content == ""


def test_deduplicate_nonconsecutive_chunk_indices() -> None:
    d0 = _make_doc(0, "abcdefghij", 0, 10)
    d5 = _make_doc(5, "fghijklmno", 5, 15)
    result = _deduplicate_chunk_overlaps([d0, d5])
    assert result[0] is d0
    assert result[1].page_content == "klmno"
