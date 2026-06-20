"""Library endpoints for browsing text files by category."""

import logging
import os
from typing import cast

from fastapi import APIRouter, HTTPException, Query

from istaroth.agd import localization
from istaroth.rag import text_set
from istaroth.rag import types as rag_types
from istaroth.services.backend import models
from istaroth.services.backend.dependencies import DocumentStoreSet, LLMManager
from istaroth.services.backend.utils import (
    handle_unexpected_exception,
    text_metadata_to_library_file_info,
)
from istaroth.text import proper_noun_extraction, proper_nouns
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
    try:
        language_enum = localization.Language(language.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {language}. Available: CHS, ENG",
        )

    if language_enum is not localization.Language.CHS:
        return models.ProperNounsResponse(nouns=[])

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

    content = text_set_obj.get_content(manifest_item.relative_path)
    if content is None:
        raise HTTPException(
            status_code=404,
            detail=f"File not found on disk: {manifest_item.relative_path}",
        )

    negative_terms = proper_nouns.parse_terms(
        text_set_obj.get_content(
            proper_nouns.PROPER_NOUNS_NEGATIVE_RELATIVE_PATH.as_posix()
        )
    )
    try:
        extracted = await proper_noun_extraction.extract_proper_nouns_cached(
            content, llm=llm_manager.get_llm(_PROPER_NOUN_MODEL)
        )
    except proper_noun_extraction.CharBudgetExceededError:
        # Over the daily budget: degrade to the static, curated proper-noun list.
        logger.warning("Proper-noun extraction budget exceeded; serving static list")
        return models.ProperNounsResponse(
            nouns=proper_nouns.filter_terms(
                proper_nouns.parse_terms(
                    text_set_obj.get_content(
                        proper_nouns.PROPER_NOUNS_RELATIVE_PATH.as_posix()
                    )
                ),
                negative_terms,
            )
        )
    # Keep only terms that actually appear in the content so the frontend trie can
    # highlight them (guards against LLM paraphrase/hallucination).
    nouns = sorted(
        {
            term
            for term in proper_nouns.filter_terms(extracted, negative_terms)
            if term in content
        }
    )
    return models.ProperNounsResponse(nouns=nouns)


@router.get(
    "/api/library/quest-hierarchy",
    response_model=models.QuestHierarchyResponse,
)
@handle_unexpected_exception
async def get_quest_hierarchy(
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.QuestHierarchyResponse:
    """Get the browsable quest hierarchy (type -> series -> chapter -> quest)."""
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

    hierarchy = text_set_obj.get_quest_hierarchy()
    if hierarchy is None:
        raise HTTPException(status_code=404, detail="Quest hierarchy not available")

    return models.QuestHierarchyResponse.model_validate(hierarchy)


@router.get(
    "/api/library/quest-series/{id}",
    response_model=models.QuestSeriesResponse,
)
@handle_unexpected_exception
async def get_quest_series(
    id: str,
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.QuestSeriesResponse:
    """Get the series (or lone chapter) enclosing a quest, for its detail-page TOC."""
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

    # 404 when there is no hierarchy or the quest is absent from it; the detail
    # page treats the TOC as supplementary and simply omits it on failure.
    hierarchy = text_set_obj.get_quest_hierarchy()
    if hierarchy is None:
        raise HTTPException(status_code=404, detail="Quest hierarchy not available")

    quest_id = int(id)
    for type_node in hierarchy["types"]:
        quest_type = type_node["quest_type"]
        for series in type_node["series"]:
            if any(
                quest["id"] == quest_id
                for chapter in series["chapters"]
                for quest in chapter["quests"]
            ):
                return models.QuestSeriesResponse(
                    quest_type=quest_type,
                    series=models.QuestHierarchySeries.model_validate(series),
                )
        for chapter in type_node["chapters"]:
            if any(quest["id"] == quest_id for quest in chapter["quests"]):
                return models.QuestSeriesResponse(
                    quest_type=quest_type,
                    chapter=models.QuestHierarchyChapter.model_validate(chapter),
                )
        if any(quest["id"] == quest_id for quest in type_node["standalone_quests"]):
            return models.QuestSeriesResponse(quest_type=quest_type)

    raise HTTPException(
        status_code=404, detail=f"Quest {quest_id} not found in hierarchy"
    )


@router.get(
    "/api/library/coop-hierarchy",
    response_model=models.CoopHierarchyResponse,
)
@handle_unexpected_exception
async def get_coop_hierarchy(
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.CoopHierarchyResponse:
    """Get the browsable hangout hierarchy (character -> chapter -> quest)."""
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

    hierarchy = text_set_obj.get_coop_hierarchy()
    if hierarchy is None:
        raise HTTPException(status_code=404, detail="Hangout hierarchy not available")

    return models.CoopHierarchyResponse.model_validate(hierarchy)


@router.get(
    "/api/library/coop-character/{id}",
    response_model=models.CoopCharacterResponse,
)
@handle_unexpected_exception
async def get_coop_character(
    id: str,
    document_store_set: DocumentStoreSet,
    language: str = Query(..., description="Language code (CHS, ENG)"),
) -> models.CoopCharacterResponse:
    """Get the character (and enclosing chapter) of a hangout quest, for its TOC."""
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

    # 404 when there is no hierarchy or the quest is absent from it; the detail
    # page treats the TOC as supplementary and simply omits it on failure.
    hierarchy = text_set_obj.get_coop_hierarchy()
    if hierarchy is None:
        raise HTTPException(status_code=404, detail="Hangout hierarchy not available")

    quest_id = int(id)
    for character in hierarchy["characters"]:
        for chapter in character["chapters"]:
            if any(quest["id"] == quest_id for quest in chapter["quests"]):
                return models.CoopCharacterResponse(
                    avatar_id=character["avatar_id"],
                    character_name=character["character_name"],
                    chapter=models.CoopHierarchyChapter.model_validate(chapter),
                )

    raise HTTPException(
        status_code=404, detail=f"Hangout quest {quest_id} not found in hierarchy"
    )


@router.post("/api/library/retrieve", response_model=models.LibraryRetrieveResponse)
@handle_unexpected_exception
async def retrieve_library(
    request: models.LibraryRetrieveRequest,
    document_store_set: DocumentStoreSet,
) -> models.LibraryRetrieveResponse:
    """Retrieve library documents using BM25 or hybrid semantic search."""
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

    if request.semantic:
        retrieve_output = await document_store.aretrieve(
            request.query, k=request.k, chunk_context=request.chunk_context
        )
    else:
        retrieve_output = document_store.retrieve_bm25(
            request.query, k=request.k, chunk_context=request.chunk_context
        )

    results = _build_retrieve_results(text_set_obj, retrieve_output)
    return models.LibraryRetrieveResponse(query=request.query, results=results)
