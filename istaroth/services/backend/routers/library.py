"""Library endpoints for browsing text files by category."""

import logging

from fastapi import APIRouter, HTTPException, Query

from istaroth.agd import localization
from istaroth.services.backend import models
from istaroth.services.backend.dependencies import DocumentStoreSet
from istaroth.services.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


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

    categories = text_set_obj.get_categories()
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
        files = text_set_obj.get_files(category)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return models.LibraryFilesResponse(files=files)


@router.get(
    "/api/library/file/{category}/{filename}", response_model=models.LibraryFileResponse
)
@handle_unexpected_exception
async def get_file(
    category: str,
    filename: str,
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.LibraryFileResponse:
    """Get full text content of a file."""
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
        content = text_set_obj.get_file_content(category, filename)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

    return models.LibraryFileResponse(
        category=category, filename=filename, content=content
    )
