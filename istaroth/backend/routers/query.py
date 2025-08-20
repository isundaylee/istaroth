"""Query endpoints for the RAG pipeline."""

import asyncio
import logging
import os
import time

from fastapi import APIRouter, HTTPException

from istaroth.agd import localization
from istaroth.backend import db_models, models
from istaroth.backend.dependencies import DBSession, DocumentStoreSet, LLMManager
from istaroth.backend.utils import handle_unexpected_exception
from istaroth.rag import pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


async def _save_conversation(
    db_session: DBSession,
    request: models.QueryRequest,
    answer: str,
    generation_time: float,
) -> str:
    """Save conversation to database and return the conversation ID."""
    conversation = db_models.Conversation(
        question=request.question,
        answer=answer,
        model=request.model,
        k=request.k,
        language=request.language,
        generation_time_seconds=generation_time,
    )
    db_session.add(conversation)
    await db_session.commit()

    # Refresh to get the generated UUID after commit
    await db_session.refresh(conversation)
    logger.info("Conversation saved to database with UUID: %s", conversation.uuid)
    return conversation.uuid


@router.post("/api/query", response_model=models.QueryResponse)
@handle_unexpected_exception
async def query(
    request: models.QueryRequest,
    document_store_set: DocumentStoreSet,
    llm_manager: LLMManager,
    db_session: DBSession,
) -> models.QueryResponse:
    """Answer a question using the RAG pipeline."""
    # Get document store for requested language
    try:
        language_enum = localization.Language(request.language)
        selected_store = document_store_set.get_store(language_enum)
        language_name = request.language.upper()
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=repr(e))

    # Get LLM for the requested model
    try:
        rag_pipeline = pipeline.RAGPipeline(
            selected_store,
            language_enum,
            llm=llm_manager.get_llm(request.model),
            preprocessing_llm=llm_manager.get_llm(
                os.environ.get("ISTAROTH_PREPROCESSING_MODEL", "gemini-2.5-flash-lite")
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=repr(e))

    # Get answer and track timing - run in worker thread to avoid blocking
    logger.info(
        "Processing query: %s with k=%d using model: %s, language: %s",
        request.question,
        request.k,
        request.model,
        language_name,
    )
    start_time = time.perf_counter()
    answer = rag_pipeline.answer(
        request.question, k=request.k, chunk_context=request.chunk_context
    )
    generation_time = time.perf_counter() - start_time

    logger.info("Query completed in %.2f seconds", generation_time)

    # Save conversation to database
    conversation_uuid = await _save_conversation(
        db_session, request, answer, generation_time
    )

    # Return response
    return models.QueryResponse(
        question=request.question,
        answer=answer,
        conversation_uuid=conversation_uuid,
        language=language_name,
    )
