"""Library endpoints for browsing text files by category."""

import logging
import pathlib
from typing import cast

from fastapi import APIRouter, HTTPException, Query

from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.rag import types as rag_types
from istaroth.services.backend import models
from istaroth.services.backend.dependencies import DocumentStoreSet
from istaroth.services.backend.utils import (
    handle_unexpected_exception,
    text_metadata_to_library_file_info,
)
from istaroth.text import types as text_types

logger = logging.getLogger(__name__)

router = APIRouter()

_SNIPPET_CHUNK_CONTEXT = 0


def _format_snippet(content: str) -> str:
    return content.replace("\r\n", " ").replace("\n", " ")


def _build_retrieve_results(
    text_set_obj: text_set.TextSet,
    retrieve_output: rag_types.RetrieveOutput,
) -> list[models.LibraryRetrieveResult]:
    results = []
    for score, docs in retrieve_output.results:
        if not docs:
            continue
        metadata = cast(rag_types.DocumentMetadata, docs[0].metadata)
        relative_path = metadata["path"]
        manifest_item = text_set_obj.get_manifest_item_by_relative_path(relative_path)
        if manifest_item is None:
            raise HTTPException(
                status_code=500,
                detail=f"Missing manifest item for path: {relative_path}",
            )
        file_info = text_metadata_to_library_file_info(manifest_item)
        snippet = _format_snippet(docs[0].page_content)
        results.append(
            models.LibraryRetrieveResult(
                file_info=file_info,
                snippet=snippet,
                score=score,
            )
        )
    return results


@router.get("/api/library/categories", response_model=models.LibraryCategoriesResponse)
@handle_unexpected_exception
async def get_categories(
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.LibraryCategoriesResponse:
    """Get list of all categories for a language."""
    try:
        language_enum = localization.Language(language.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {language}. Available: CHS, ENG",
        )

    try:
        text_set_obj = document_store_set.get_text_set(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Compute categories from manifest at caller site
    manifest = text_set_obj.get_manifest()
    categories = sorted(set(item.category.value for item in manifest))
    return models.LibraryCategoriesResponse(categories=categories)


@router.get("/api/library/files/{category}", response_model=models.LibraryFilesResponse)
@handle_unexpected_exception
async def get_files(
    category: str,
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.LibraryFilesResponse:
    """Get list of files in a category for a language."""
    try:
        language_enum = localization.Language(language.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {language}. Available: CHS, ENG",
        )

    try:
        text_set_obj = document_store_set.get_text_set(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        # Convert directory name to TextCategory enum
        text_category = text_types.TextCategory(category)
        all_metadata = text_set_obj.get_manifest()
        # Filter by TextCategory enum
        metadata_list = [
            metadata for metadata in all_metadata if metadata.category == text_category
        ]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    file_infos = []
    for metadata in metadata_list:
        file_info = text_metadata_to_library_file_info(metadata)
        file_infos.append(file_info)

    # Sort by ID ascending
    file_infos.sort(key=lambda file_info: file_info.id)

    return models.LibraryFilesResponse(files=file_infos)


@router.get(
    "/api/library/file/{category}/{id}", response_model=models.LibraryFileResponse
)
@handle_unexpected_exception
async def get_file(
    category: str,
    id: str,
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.LibraryFileResponse:
    """Get full text content of a file by category and id."""
    try:
        language_enum = localization.Language(language.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {language}. Available: CHS, ENG",
        )

    try:
        text_set_obj = document_store_set.get_text_set(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    manifest_item = text_set_obj.get_manifest_item(
        text_types.TextCategory(category), int(id)
    )
    if manifest_item is None:
        raise HTTPException(
            status_code=404, detail=f"File not found: category={category}, id={id}"
        )

    # Get file content from relative_path
    content = text_set_obj.get_content(manifest_item.relative_path)
    if content is None:
        raise HTTPException(
            status_code=404,
            detail=f"File not found on disk: {manifest_item.relative_path}",
        )

    # Convert manifest item to LibraryFileInfo
    file_info = text_metadata_to_library_file_info(manifest_item)

    return models.LibraryFileResponse(file_info=file_info, content=content)


@router.post("/api/library/retrieve", response_model=models.LibraryRetrieveResponse)
@handle_unexpected_exception
async def retrieve_library(
    request: models.LibraryRetrieveRequest,
    document_store_set: DocumentStoreSet,
) -> models.LibraryRetrieveResponse:
    """Retrieve library documents using BM25 keyword search only."""
    try:
        language_enum = localization.Language(request.language.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {request.language}. Available: CHS, ENG",
        )

    try:
        document_store = document_store_set.get_store(language_enum)
        text_set_obj = document_store_set.get_text_set(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    retrieve_output = document_store.retrieve_bm25(
        request.query, k=request.k, chunk_context=_SNIPPET_CHUNK_CONTEXT
    )

    results = _build_retrieve_results(text_set_obj, retrieve_output)
    return models.LibraryRetrieveResponse(query=request.query, results=results)
