"""Library endpoints for browsing text files by category."""

import logging

from fastapi import APIRouter, HTTPException, Query

from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.services.backend import models
from istaroth.services.backend.dependencies import DocumentStoreSet
from istaroth.services.backend.utils import handle_unexpected_exception, parse_filename

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
        filenames = text_set_obj.get_files(category)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    file_infos = []
    for filename in filenames:
        try:
            file_info = parse_filename(filename)
            # Verify that the parsed category matches the requested category
            if file_info.category != category:
                raise ValueError(
                    f"Parsed category '{file_info.category}' doesn't match requested category '{category}'"
                )
            file_infos.append(file_info)
        except ValueError as e:
            logger.warning(f"Failed to parse filename {filename}: {e}")
            # Fallback: create file info with filename as name and no id
            file_infos.append(
                models.LibraryFileInfo(
                    category=category,
                    name=filename[:-4] if filename.endswith(".txt") else filename,
                    id=None,
                    filename=filename,
                )
            )

    # Sort by ID ascending
    # Files without IDs come after files with numeric IDs
    def sort_key(file_info: models.LibraryFileInfo) -> tuple[int, int]:
        if file_info.id is None:
            return (1, 0)  # Files without IDs come last
        return (0, file_info.id)  # Numeric IDs sorted numerically

    file_infos.sort(key=sort_key)

    return models.LibraryFilesResponse(files=file_infos)


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
