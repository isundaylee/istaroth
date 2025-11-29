"""Citation endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.services.backend import models
from istaroth.services.backend.dependencies import DocumentStoreSet
from istaroth.services.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/citations/batch", response_model=models.CitationBatchResponse)
@handle_unexpected_exception
async def get_citations_batch(
    request: models.CitationBatchRequest,
    document_store_set: DocumentStoreSet,
) -> models.CitationBatchResponse:
    """Get multiple citations in a single request.

    Supports fetching different chunks from different files.
    Returns partial results with successes and errors separated.
    """
    # Validate and get language
    try:
        language_enum = localization.Language(request.language)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {request.language}. Available: CHS, ENG",
        )

    # Get the document store for the specified language
    try:
        store = document_store_set.get_store(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    successes = []
    errors = []

    # Process each citation request
    for file_id, chunk_index in request.citations:
        try:
            # Get the chunk
            chunk = store.get_chunk(file_id, chunk_index)

            if chunk is None:
                # Determine if it's the file or chunk that's missing
                total_chunks = store.get_file_chunk_count(file_id)
                if total_chunks is None:
                    errors.append(
                        models.CitationError(
                            file_id=file_id,
                            chunk_index=chunk_index,
                            error=f"File not found: {file_id}",
                        )
                    )
                else:
                    errors.append(
                        models.CitationError(
                            file_id=file_id,
                            chunk_index=chunk_index,
                            error=f"Chunk index {chunk_index} out of range (0-{total_chunks-1})",
                        )
                    )
                continue

            # Get total chunks for this file
            total_chunks = store.get_file_chunk_count(file_id)
            assert (
                total_chunks is not None
            ), f"Chunk exists but file metadata missing for {file_id}"

            # Extract filename and category from metadata
            filename = chunk.metadata.get("filename")
            category = None
            if filename:
                try:
                    category = text_set.get_category_from_filename(filename)
                except ValueError:
                    # Filename doesn't match any known category prefix
                    category = None

            # Success - add to results
            successes.append(
                models.CitationResponse(
                    file_id=file_id,
                    chunk_index=chunk_index,
                    content=chunk.page_content,
                    metadata=chunk.metadata,
                    total_chunks=total_chunks,
                    category=category,
                    filename=filename,
                )
            )

        except Exception as e:
            # Catch any unexpected errors for this specific citation
            logger.exception(
                "Unexpected error fetching citation %s:%d", file_id, chunk_index
            )
            errors.append(
                models.CitationError(
                    file_id=file_id,
                    chunk_index=chunk_index,
                    error=f"Internal error: {str(e)}",
                )
            )

    return models.CitationBatchResponse(successes=successes, errors=errors)
