"""Query endpoints for the RAG pipeline."""

import asyncio
import logging
import os
import time

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from istaroth.agd import localization
from istaroth.rag import pipeline
from istaroth.services.backend import db_models, models, slugs
from istaroth.services.backend.dependencies import (
    DBSession,
    DocumentStoreSet,
    LLMManager,
)
from istaroth.services.backend.utils import handle_unexpected_exception
from istaroth.services.common import metrics

logger = logging.getLogger(__name__)

router = APIRouter()


async def _save_conversation(
    db_session: DBSession,
    request: models.QueryRequest,
    answer: str,
    generation_time: float,
) -> tuple[str, str]:
    """Save conversation to database and return (uuid, short_slug)."""
    conversation = db_models.Conversation(
        question=request.question,
        answer=answer,
        model=request.model,
        k=request.k,
        language=request.language,
        generation_time_seconds=generation_time,
    )
    db_session.add(conversation)
    await db_session.flush()
    conversation_uuid = conversation.uuid
    logger.info("Conversation flushed with UUID: %s", conversation_uuid)

    for _ in range(5):
        slug = slugs.generate_slug()
        try:
            async with db_session.begin_nested():
                db_session.add(
                    db_models.ShortURL(
                        slug=slug,
                        target_path=f"/conversation/{conversation_uuid}",
                    )
                )
                await db_session.flush()
        except IntegrityError:
            continue
        await db_session.commit()
        return conversation_uuid, slug

    await db_session.rollback()
    raise RuntimeError("Failed to generate a unique short URL slug after 5 attempts")


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
        selected_text_set = document_store_set.get_text_set(language_enum)
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
                os.environ.get("ISTAROTH_PREPROCESSING_MODEL", "gemini-2.5-flash-lite"),
            ),
            text_set=selected_text_set,
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
    answer = await asyncio.to_thread(
        lambda: rag_pipeline.answer(
            request.question, k=request.k, chunk_context=request.chunk_context
        ),
    )
    generation_time = time.perf_counter() - start_time
    metrics.rag_pipeline_duration_seconds.labels(
        model=request.model, language=language_name
    ).observe(generation_time)

    logger.info("Query completed in %.2f seconds", generation_time)

    # Save conversation to database
    conversation_uuid, short_slug = await _save_conversation(
        db_session, request, answer, generation_time
    )

    # Return response
    return models.QueryResponse(
        question=request.question,
        answer=answer,
        conversation_uuid=conversation_uuid,
        language=language_name,
        short_slug=short_slug,
    )
