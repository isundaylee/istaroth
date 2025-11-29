"""Library endpoints for browsing text files by category."""

import logging

from fastapi import APIRouter, HTTPException, Query

from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.services.backend import models
from istaroth.services.backend.dependencies import DocumentStoreSet
from istaroth.services.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_filename(filename: str, category: str) -> models.LibraryFileInfo:
    """Parse filename into components: category, name, and id.

    Expected format: {prefix}_{name}_{id}.txt or {prefix}_{name}.txt
    The filename MUST start with the expected prefix for the category.
    The ID is only extracted if the last part after the final underscore is an integer.
    """
    if not filename.endswith(".txt"):
        raise ValueError(f"Invalid filename format: {filename}")

    expected_prefix = text_set.get_category_prefix(category)
    name_without_ext = filename[:-4]  # Remove .txt

    # Require category prefix
    if not name_without_ext.startswith(expected_prefix):
        raise ValueError(
            f"Filename must start with category prefix '{expected_prefix}': {filename}"
        )

    name_without_ext = name_without_ext[len(expected_prefix) :]

    # Find the last underscore to check if there's an ID
    last_underscore = name_without_ext.rfind("_")
    if last_underscore == -1:
        # No underscore, entire thing is the name
        return models.LibraryFileInfo(
            category=category, name=name_without_ext, id=None, filename=filename
        )

    # Check if the part after the last underscore is an integer
    potential_id = name_without_ext[last_underscore + 1 :]
    try:
        file_id = int(potential_id)  # Convert to integer
        # It's an integer, so it's the ID
        name = name_without_ext[:last_underscore]
    except ValueError:
        # Not an integer, so the whole thing is the name
        name = name_without_ext
        file_id = None

    return models.LibraryFileInfo(
        category=category, name=name, id=file_id, filename=filename
    )


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
            file_info = _parse_filename(filename, category)
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
