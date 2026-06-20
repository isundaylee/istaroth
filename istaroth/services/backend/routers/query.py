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

from istaroth import llm_errors
from istaroth.agd import localization
from istaroth.rag import pipeline, progress, text_set, types
from istaroth.services.backend import (
    db_models,
    models,
    proper_noun_highlighting,
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
        k=request.k,
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
) -> tuple[pipeline.RAGPipeline, str, localization.Language, text_set.TextSet]:
    """Validate the request and build a pipeline.

    Returns ``(pipeline, language_name, language_enum, text_set)``.
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
            text_set=selected_text_set,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=repr(e))

    return rag_pipeline, language_name, language_enum, selected_text_set


async def _extract_answer_proper_nouns(
    answer: str,
    *,
    language_enum: localization.Language,
    text_set_obj: text_set.TextSet,
    llm_manager: LLMManager,
    reporter: progress.ProgressReporter,
) -> list[str]:
    """Extract highlightable proper nouns from the answer as a reported step.

    Only CHS is supported (ENG returns ``[]`` without a step). Highlighting is
    supplementary, so any extraction failure degrades to no highlights rather
    than failing the query.
    """
    if language_enum is not localization.Language.CHS:
        return []
    with reporter.step("extracting_proper_nouns"):
        try:
            return await proper_noun_highlighting.extract_highlight_nouns(
                answer,
                text_set_obj=text_set_obj,
                llm=llm_manager.get_llm(_PROPER_NOUN_MODEL),
            )
        except Exception:
            logger.warning("Answer proper-noun extraction failed", exc_info=True)
            return []


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
    rag_pipeline, language_name, language_enum, text_set_obj = _build_pipeline(
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
                reporter = progress.StreamReporter(send_stream)
                start_time = time.perf_counter()
                result = await rag_pipeline.answer(
                    request.question,
                    k=request.k,
                    chunk_context=request.chunk_context,
                    reporter=reporter,
                )
                generation_time = time.perf_counter() - start_time
                metrics.rag_pipeline_duration_seconds.labels(
                    model=request.model, language=language_name
                ).observe(generation_time)
                logger.info(
                    "Streaming query completed in %.2f seconds", generation_time
                )
                proper_nouns = await _extract_answer_proper_nouns(
                    result.answer,
                    language_enum=language_enum,
                    text_set_obj=text_set_obj,
                    llm_manager=llm_manager,
                    reporter=reporter,
                )
                conversation_uuid, short_slug = await _save_conversation(
                    db_session, request, result, generation_time, proper_nouns
                )
                terminal["event"] = models.QueryStreamDone(
                    result=models.QueryResponse(
                        question=request.question,
                        answer=result.answer,
                        conversation_uuid=conversation_uuid,
                        language=language_name,
                        short_slug=short_slug,
                        proper_nouns=proper_nouns,
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
