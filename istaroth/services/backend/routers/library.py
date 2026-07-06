"""Library endpoints for browsing text files by category."""

import logging
import os
from typing import cast

import fastapi
from fastapi import APIRouter, HTTPException, Query

from istaroth.agd import localization
from istaroth.rag import budget as budget_mod
from istaroth.rag import document_store_set as document_store_set_module
from istaroth.rag import text_set
from istaroth.rag import types as rag_types
from istaroth.services.backend import models, proper_noun_highlighting
from istaroth.services.backend.dependencies import DocumentStoreSet, LLMManager
from istaroth.services.backend.utils import (
    handle_unexpected_exception,
    text_metadata_to_library_file_info,
)
from istaroth.text import proper_nouns
from istaroth.text import types as text_types

logger = logging.getLogger(__name__)

router = APIRouter()

# Model for on-the-fly proper-noun extraction. Defaults to the pipeline default
# (not thinking-level-expanded, so always selectable under ISTAROTH_AVAILABLE_MODELS=all).
# Highlighting is supplementary, so a misconfigured/unavailable model surfaces as a
# 500 the frontend treats as "no highlights" rather than breaking the page.
_PROPER_NOUN_MODEL = os.environ.get(
    "ISTAROTH_PROPER_NOUN_MODEL", "gemini-3.1-flash-lite-preview"
)


def _parse_language(language: str) -> localization.Language:
    try:
        return localization.Language(language.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {language}. Available: CHS, ENG",
        )


def _get_text_set(
    document_store_set: document_store_set_module.DocumentStoreSet,
    language_enum: localization.Language,
) -> text_set.TextSet:
    try:
        return document_store_set.get_text_set(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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


@router.get("/api/library/hierarchy", response_model=models.LibraryHierarchyResponse)
@handle_unexpected_exception
async def get_library_hierarchy(
    request: fastapi.Request,
    response: fastapi.Response,
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.LibraryHierarchyResponse | fastapi.Response:
    """Get the full library hierarchy: every category's document tree.

    Categories with a dedicated builder (quests, hangouts) return their pre-baked
    multi-level tree; any other category returns a flat, depth-1 list of file
    leaves synthesized from the manifest. The corpus is immutable per deployment,
    so the response carries an ETag for free conditional reloads.
    """
    text_set_obj = _get_text_set(document_store_set, _parse_language(language))

    # The "v2" prefix versions the response shape: the hash covers only the
    # corpus data, so it must be bumped if the payload structure ever changes.
    etag = f'"v2-{text_set_obj.library_hierarchies_content_hash}"'
    if request.headers.get("if-none-match") == etag:
        return fastapi.Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"

    return models.LibraryHierarchyResponse(
        categories=[
            models.LibraryCategoryHierarchy.model_validate(
                {"category": category, **hierarchy}
            )
            for category, hierarchy in text_set_obj.get_library_hierarchies().items()
        ],
        latest_version=text_set_obj.latest_version,
    )


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
    text_set_obj = _get_text_set(document_store_set, _parse_language(language))

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


@router.get("/api/library/proper-nouns", response_model=models.ProperNounsResponse)
@handle_unexpected_exception
async def get_proper_nouns(
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.ProperNounsResponse:
    """Get the static curated proper-noun list for a language.

    Empty when no list ships for the language (e.g. ENG). The frontend uses this
    as a fast fallback while per-file on-the-fly extraction is in flight.
    """
    text_set_obj = _get_text_set(document_store_set, _parse_language(language))

    return models.ProperNounsResponse(
        nouns=proper_nouns.filter_terms_from_content(
            text_set_obj.get_content(
                proper_nouns.PROPER_NOUNS_RELATIVE_PATH.as_posix()
            ),
            text_set_obj.get_content(
                proper_nouns.PROPER_NOUNS_NEGATIVE_RELATIVE_PATH.as_posix()
            ),
        )
    )


@router.get(
    "/api/library/file/{category}/{id}/proper-nouns",
    response_model=models.ProperNounsResponse,
)
@handle_unexpected_exception
async def get_file_proper_nouns(
    category: str,
    id: str,
    document_store_set: DocumentStoreSet,
    llm_manager: LLMManager,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.ProperNounsResponse:
    """Extract a single file's proper nouns for highlighting.

    Runs an LLM over the exact rendered content on the fly (cached by content
    hash). Only CHS is supported; ENG returns an empty list.
    """
    language_enum = _parse_language(language)
    if language_enum is not localization.Language.CHS:
        return models.ProperNounsResponse(nouns=[])

    text_set_obj = _get_text_set(document_store_set, language_enum)

    manifest_item = text_set_obj.get_manifest_item(
        text_types.TextCategory(category), int(id)
    )
    if manifest_item is None:
        raise HTTPException(
            status_code=404, detail=f"File not found: category={category}, id={id}"
        )

    content = text_set_obj.get_content(manifest_item.relative_path)
    if content is None:
        raise HTTPException(
            status_code=404,
            detail=f"File not found on disk: {manifest_item.relative_path}",
        )

    return models.ProperNounsResponse(
        nouns=await proper_noun_highlighting.extract_highlight_nouns(
            content,
            text_set_obj=text_set_obj,
            llm=llm_manager.get_llm(_PROPER_NOUN_MODEL),
        )
    )


@router.post("/api/library/retrieve", response_model=models.LibraryRetrieveResponse)
@handle_unexpected_exception
async def retrieve_library(
    request: models.LibraryRetrieveRequest,
    document_store_set: DocumentStoreSet,
) -> models.LibraryRetrieveResponse:
    """Retrieve library documents using BM25 or hybrid semantic search."""
    language_enum = _parse_language(request.language)
    try:
        document_store = document_store_set.get_store(language_enum)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    text_set_obj = _get_text_set(document_store_set, language_enum)

    if request.semantic:
        retrieve_output = await document_store.aretrieve(
            request.query, budget=request.k, intent=budget_mod.QueryIntent.LOOKUP
        )
    else:
        retrieve_output = document_store.retrieve_bm25(
            request.query, budget=request.k, intent=budget_mod.QueryIntent.LOOKUP
        )

    results = _build_retrieve_results(text_set_obj, retrieve_output)
    return models.LibraryRetrieveResponse(query=request.query, results=results)
