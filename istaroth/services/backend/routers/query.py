"""Query endpoints for the RAG pipeline."""

import json
import logging
import math
import os
import time
from typing import Any, AsyncIterator

import anyio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError

from istaroth.agd import localization
from istaroth.rag import pipeline, progress
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


def _build_pipeline(
    request: models.QueryRequest,
    document_store_set: DocumentStoreSet,
    llm_manager: LLMManager,
) -> tuple[pipeline.RAGPipeline, str]:
    """Validate the request and build a pipeline; returns (pipeline, language_name)."""
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
            text_set=selected_text_set,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=repr(e))

    return rag_pipeline, language_name


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
    rag_pipeline, language_name = _build_pipeline(
        request, document_store_set, llm_manager
    )

    logger.info(
        "Processing streaming query: %s with k=%d using model: %s, language: %s",
        request.question,
        request.k,
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
                start_time = time.perf_counter()
                answer = await rag_pipeline.answer(
                    request.question,
                    k=request.k,
                    chunk_context=request.chunk_context,
                    reporter=progress.StreamReporter(send_stream),
                )
                generation_time = time.perf_counter() - start_time
                metrics.rag_pipeline_duration_seconds.labels(
                    model=request.model, language=language_name
                ).observe(generation_time)
                logger.info(
                    "Streaming query completed in %.2f seconds", generation_time
                )
                conversation_uuid, short_slug = await _save_conversation(
                    db_session, request, answer, generation_time
                )
                terminal["event"] = models.QueryStreamDone(
                    result=models.QueryResponse(
                        question=request.question,
                        answer=answer,
                        conversation_uuid=conversation_uuid,
                        language=language_name,
                        short_slug=short_slug,
                    )
                )
            except Exception:
                logger.error("Error in streaming query", exc_info=True)
                terminal["event"] = models.QueryStreamError(
                    error="Internal server error"
                )
            finally:
                send_stream.close()

        async with anyio.create_task_group() as tg:
            tg.start_soon(_run)
            async for event in receive_stream:
                yield (json.dumps(event.to_dict()) + "\n").encode()

        terminal_event = terminal.get(
            "event", models.QueryStreamError(error="Internal server error")
        )
        yield (json.dumps(terminal_event.model_dump()) + "\n").encode()

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
