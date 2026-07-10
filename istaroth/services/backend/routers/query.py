"""Query endpoints for the RAG pipeline."""

import logging
import math
import os
import time
from typing import Any, AsyncIterator

import anyio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from istaroth import json_utils, llm_errors
from istaroth.agd import localization
from istaroth.rag import pipeline, progress, types
from istaroth.services.backend import (
    db_models,
    models,
    slugs,
)
from istaroth.services.backend.dependencies import (
    DBSession,
    DocumentStoreSet,
    LLMManager,
)
from istaroth.services.backend.utils import handle_unexpected_exception
from istaroth.services.common import metrics

logger = logging.getLogger(__name__)

router = APIRouter()

# Model for inline answer proper-noun extraction (highlighting); mirrors the
# library router default and degrades to "no highlights" if unavailable.
_PROPER_NOUN_MODEL = os.environ.get(
    "ISTAROTH_PROPER_NOUN_MODEL", "gemini-3.1-flash-lite-preview"
)


async def _save_conversation(
    db_session: DBSession,
    request: models.QueryRequest,
    result: types.AnswerResult,
    generation_time: float,
    proper_nouns: list[str],
) -> tuple[str, str]:
    """Save conversation to database and return (uuid, short_slug)."""
    conversation = db_models.Conversation(
        question=request.question,
        answer=result.answer,
        model=request.model,
        k=0,
        budget=request.budget,
        language=request.language,
        client_id=request.client_id,
        generation_time_seconds=generation_time,
        final_generation_input_text_length=(
            result.stats.final_generation_input_text_length
        ),
        retrieval_unique_chunk_count=result.stats.retrieval_unique_chunk_count,
        retrieval_unique_file_count=result.stats.retrieval_unique_file_count,
        proper_nouns=proper_nouns,
    )
    db_session.add(conversation)
    await db_session.flush()
    conversation_uuid = conversation.uuid
    logger.info("Conversation flushed with UUID: %s", conversation_uuid)

    slug = await slugs.get_or_create_short_url(
        f"/conversation/{conversation_uuid}", db_session=db_session
    )
    return conversation_uuid, slug


def _build_pipeline(
    request: models.QueryRequest,
    document_store_set: DocumentStoreSet,
    llm_manager: LLMManager,
) -> tuple[pipeline.RAGPipeline, str]:
    """Validate the request and build a pipeline.

    Returns ``(pipeline, language_name)``.
    """
    try:
        language_enum = localization.Language(request.language)
        selected_store = document_store_set.get_store(language_enum)
        selected_text_set = document_store_set.get_text_set(language_enum)
        language_name = request.language.upper()
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=repr(e))

    try:
        rag_pipeline = pipeline.RAGPipeline(
            selected_store,
            language_enum,
            llm=llm_manager.get_llm(request.model),
            preprocessing_llm=llm_manager.get_llm(
                os.environ.get(
                    "ISTAROTH_PREPROCESSING_MODEL", "gemini-3.1-flash-lite-preview"
                ),
            ),
            proper_noun_llm=llm_manager.get_llm(_PROPER_NOUN_MODEL),
            text_set=selected_text_set,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=repr(e))

    return rag_pipeline, language_name


def _compose_cache_key(request: models.QueryRequest) -> str:
    """Build the stored cache key: ``{language}:{normalized client key}``.

    The backend namespaces by language (an ENG answer is not valid for a CHS
    query) and normalizes for case-insensitive matching. Returns an empty string
    when the client supplied no key (caching disabled for the request).
    """
    client_key = (request.cache_key or "").strip().lower()
    if not client_key:
        return ""
    return f"{request.language.strip().lower()}:{client_key}"


async def _lookup_query_cache(
    db_session: DBSession, cache_key: str
) -> models.QueryResponse | None:
    """Return the cached answer for ``cache_key``, or ``None`` on miss."""
    cache_row = (
        await db_session.execute(
            select(db_models.QueryCache).where(
                db_models.QueryCache.cache_key == cache_key
            )
        )
    ).scalar_one_or_none()
    if cache_row is None:
        return None
    conversation = (
        await db_session.execute(
            select(db_models.Conversation).where(
                db_models.Conversation.uuid == cache_row.conversation_uuid
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        # A cache row pointing at a missing conversation is a data-integrity
        # bug (the FK should forbid it); surface it rather than mask as a miss.
        raise AssertionError(
            f"query_cache entry {cache_key!r} references missing conversation "
            f"{cache_row.conversation_uuid!r}"
        )
    short_url = (
        await db_session.execute(
            select(db_models.ShortURL).where(
                db_models.ShortURL.target_path == f"/conversation/{conversation.uuid}"
            )
        )
    ).scalar_one_or_none()
    if short_url is None:
        raise AssertionError(
            f"No short URL found for conversation {conversation.uuid!r}"
        )
    return models.QueryResponse(
        question=conversation.question,
        answer=conversation.answer,
        conversation_uuid=conversation.uuid,
        language=conversation.language,
        short_slug=short_url.slug,
        proper_nouns=conversation.proper_nouns or [],
        final_generation_input_text_length=(
            conversation.final_generation_input_text_length or 0
        ),
        retrieval_unique_chunk_count=conversation.retrieval_unique_chunk_count or 0,
        retrieval_unique_file_count=conversation.retrieval_unique_file_count or 0,
    )


async def _populate_query_cache(
    db_session: DBSession, cache_key: str, conversation_uuid: str
) -> None:
    """Record the cache_key → conversation mapping (first write wins)."""
    try:
        async with db_session.begin_nested():
            db_session.add(
                db_models.QueryCache(
                    cache_key=cache_key,
                    conversation_uuid=conversation_uuid,
                )
            )
        await db_session.commit()
    except IntegrityError:
        await db_session.rollback()


@router.post(
    "/api/query/stream",
    responses={
        200: {
            "model": models.QueryStreamEvent,
            "description": (
                "Newline-delimited JSON (application/x-ndjson) stream of progress "
                "events, ending with a `done` or `error` event."
            ),
        }
    },
)
@handle_unexpected_exception
async def query_stream(
    request: models.QueryRequest,
    document_store_set: DocumentStoreSet,
    llm_manager: LLMManager,
    db_session: DBSession,
) -> StreamingResponse:
    """Answer a question, streaming pipeline progress as newline-delimited JSON.

    Emits ``step_start``/``step_end`` events as pipeline steps begin and finish,
    followed by a terminal ``done`` event carrying the ``QueryResponse`` (or an
    ``error`` event). The client shows every step that has started but not ended.
    """
    language_name = request.language.upper()
    cache_key = _compose_cache_key(request)

    if cache_key:
        cached = await _lookup_query_cache(db_session, cache_key)
        if cached is not None:
            metrics.query_cache_total.labels(language=language_name, result="hit").inc()
            logger.info("Query cache hit for %r", cache_key)

            async def _generate_cached() -> AsyncIterator[bytes]:
                event = models.QueryStreamDone(result=cached)
                yield json_utils.dumps(event.model_dump()) + b"\n"

            return StreamingResponse(
                _generate_cached(),
                media_type="application/x-ndjson",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        metrics.query_cache_total.labels(language=language_name, result="miss").inc()
        logger.info("Query cache miss for %r", cache_key)

    rag_pipeline, language_name = _build_pipeline(
        request, document_store_set, llm_manager
    )

    logger.info(
        "Processing streaming query: %s with budget=%d using model: %s, language: %s",
        request.question,
        request.budget,
        request.model,
        language_name,
    )

    async def _generate() -> AsyncIterator[bytes]:
        send_stream, receive_stream = anyio.create_memory_object_stream[
            progress.ProgressEvent
        ](math.inf)
        terminal: dict[str, Any] = {}

        async def _run() -> None:
            try:
                reporter = progress.StreamReporter(send_stream)
                start_time = time.perf_counter()
                result = await rag_pipeline.answer(
                    request.question,
                    budget=request.budget,
                    reporter=reporter,
                )
                generation_time = time.perf_counter() - start_time
                metrics.rag_pipeline_duration_seconds.labels(
                    model=request.model, language=language_name
                ).observe(generation_time)
                logger.info(
                    "Streaming query completed in %.2f seconds", generation_time
                )
                conversation_uuid, short_slug = await _save_conversation(
                    db_session, request, result, generation_time, result.proper_nouns
                )
                if cache_key:
                    await _populate_query_cache(
                        db_session, cache_key, conversation_uuid
                    )
                terminal["event"] = models.QueryStreamDone(
                    result=models.QueryResponse(
                        question=request.question,
                        answer=result.answer,
                        conversation_uuid=conversation_uuid,
                        language=language_name,
                        short_slug=short_slug,
                        proper_nouns=result.proper_nouns,
                        final_generation_input_text_length=(
                            result.stats.final_generation_input_text_length
                        ),
                        retrieval_unique_chunk_count=(
                            result.stats.retrieval_unique_chunk_count
                        ),
                        retrieval_unique_file_count=(
                            result.stats.retrieval_unique_file_count
                        ),
                    )
                )
            except Exception as exc:
                logger.error("Error in streaming query", exc_info=True)
                llm_error = llm_errors.classify_llm_error(exc)
                terminal["event"] = models.QueryStreamError(
                    error=(
                        llm_error.message
                        if llm_error is not None
                        else "Internal server error"
                    )
                )
            finally:
                send_stream.close()

        async with anyio.create_task_group() as tg:
            tg.start_soon(_run)
            async for event in receive_stream:
                yield json_utils.dumps(event.to_dict()) + b"\n"

        terminal_event = terminal.get(
            "event", models.QueryStreamError(error="Internal server error")
        )
        yield json_utils.dumps(terminal_event.model_dump()) + b"\n"

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
