"""Citation endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from istaroth.agd import localization
from istaroth.backend import models
from istaroth.backend.dependencies import DocumentStoreSet
from istaroth.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/citations/{file_id}/{chunk_index}", response_model=models.CitationResponse
)
@handle_unexpected_exception
async def get_citation(
    file_id: str,
    chunk_index: int,
    language: Annotated[str, Query()],
    document_store_set: DocumentStoreSet,
) -> models.CitationResponse:
    """Get citation content by file ID and chunk index."""
    # Validate language parameter
    try:
        language_enum = localization.Language(language.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {language}. Available: CHS, ENG",
        )

    # Get the document store for the specified language
    try:
        store = document_store_set.get_store(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get the chunk
    chunk = store.get_chunk(file_id, chunk_index)

    if chunk is None:
        raise HTTPException(
            status_code=404,
            detail=f"Citation not found: file_id={file_id}, chunk_index={chunk_index}",
        )

    # Get the total number of chunks for this file
    total_chunks = store.get_file_chunk_count(file_id)
    if total_chunks is None:
        raise HTTPException(
            status_code=404, detail=f"File not found: file_id={file_id}"
        )

    # Return the chunk content and metadata
    return models.CitationResponse(
        file_id=file_id,
        chunk_index=chunk_index,
        content=chunk.page_content,
        metadata=chunk.metadata,
        total_chunks=total_chunks,
    )
