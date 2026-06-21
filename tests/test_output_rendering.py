"""Tests for output_rendering module."""

from langchain_core.documents import Document

from istaroth.rag.output_rendering import _deduplicate_chunk_overlaps

_RAW = "abcdefghijklmnopqrstuv"


def _make_doc(chunk_index: int, start_index: int, end_index: int) -> Document:
    return Document(
        page_content=_RAW[start_index:end_index],
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


def test_deduplicate_with_overlap() -> None:
    d0 = _make_doc(0, 0, 10)
    d1 = _make_doc(1, 5, 15)
    result = _deduplicate_chunk_overlaps([d0, d1])
    assert result[0] is d0
    assert result[1].page_content == _RAW[10:15]


def test_deduplicate_three_chunks_with_overlaps() -> None:
    d0 = _make_doc(0, 0, 10)
    d1 = _make_doc(1, 5, 15)
    d2 = _make_doc(2, 12, 22)
    result = _deduplicate_chunk_overlaps([d0, d1, d2])
    assert result[0] is d0
    assert result[1].page_content == _RAW[10:15]
    assert result[2].page_content == _RAW[15:22]
