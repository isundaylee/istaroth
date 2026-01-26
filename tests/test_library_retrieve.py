"""Tests for BM25-only library retrieval mapping."""

import json
import pathlib

import pytest
from fastapi import HTTPException
from langchain_core.documents import Document

from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.rag import types as rag_types
from istaroth.services.backend.routers import library
from istaroth.text import types as text_types


def _create_text_set(tmp_path: pathlib.Path) -> text_set.TextSet:
    text_path = tmp_path / "text"
    text_path.mkdir()
    metadata = text_types.TextMetadata(
        category=text_types.TextCategory.AGD_BOOK,
        title="Test Book",
        id=1,
        relative_path="agd_book/book_1.txt",
    )
    manifest_path = text_path / "manifest.json"
    manifest_path.write_text(json.dumps([metadata.to_dict()]))
    return text_set.TextSet(text_path=text_path, language=localization.Language.ENG)


def test_build_retrieve_results_maps_manifest_item(tmp_path: pathlib.Path) -> None:
    text_set_obj = _create_text_set(tmp_path)
    doc = Document(
        page_content="Hello\nWorld",
        metadata={
            "source": "test",
            "type": "document",
            "path": "agd_book/book_1.txt",
            "file_id": "file-1",
            "chunk_index": 0,
        },
    )
    retrieve_output = rag_types.RetrieveOutput(
        query=rag_types.RetrieveQuery(query="hello", k=1, chunk_context=0),
        results=[(1.23, [doc])],
    )

    results = library._build_retrieve_results(text_set_obj, retrieve_output)

    assert len(results) == 1
    result = results[0]
    assert result.file_info.category == "agd_book"
    assert result.file_info.title == "Test Book"
    assert result.file_info.id == 1
    assert result.file_info.relative_path == "agd_book/book_1.txt"
    assert result.snippet == "Hello World"
    assert result.score == 1.23


def test_build_retrieve_results_missing_manifest(tmp_path: pathlib.Path) -> None:
    text_set_obj = _create_text_set(tmp_path)
    doc = Document(
        page_content="Missing",
        metadata={
            "source": "test",
            "type": "document",
            "path": "agd_book/missing.txt",
            "file_id": "file-2",
            "chunk_index": 0,
        },
    )
    retrieve_output = rag_types.RetrieveOutput(
        query=rag_types.RetrieveQuery(query="missing", k=1, chunk_context=0),
        results=[(0.5, [doc])],
    )

    with pytest.raises(HTTPException):
        library._build_retrieve_results(text_set_obj, retrieve_output)
