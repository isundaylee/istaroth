"""Conversation endpoints."""

import datetime
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from istaroth.services.backend import db_models, models
from istaroth.services.backend.dependencies import DBSession
from istaroth.services.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/conversations", response_model=models.ConversationListResponse)
@handle_unexpected_exception
async def list_conversations(
    client_id: str,
    db_session: DBSession,
    limit: int = 50,
    before_id: int | None = None,
) -> models.ConversationListResponse:
    """List a client's conversations, newest first, with cursor pagination."""
    limit = max(1, min(limit, 100))
    stmt = select(db_models.Conversation).where(
        db_models.Conversation.client_id == client_id
    )
    if before_id is not None:
        stmt = stmt.where(db_models.Conversation.id < before_id)
    stmt = stmt.order_by(db_models.Conversation.id.desc()).limit(limit)

    result = await db_session.execute(stmt)
    return models.ConversationListResponse(
        conversations=[
            models.ConversationSummary(
                id=conversation.id,
                uuid=conversation.uuid,
                question=conversation.question,
                language=conversation.language,
                model=conversation.model or "",
                created_at=conversation.created_at.replace(
                    tzinfo=datetime.timezone.utc
                ).timestamp(),
            )
            for conversation in result.scalars().all()
        ]
    )


@router.get(
    "/api/conversations/{conversation_uuid}", response_model=models.ConversationResponse
)
@handle_unexpected_exception
async def get_conversation(
    conversation_uuid: str, db_session: DBSession
) -> models.ConversationResponse:
    """Get a specific conversation by ID."""
    stmt = select(db_models.Conversation).where(
        db_models.Conversation.uuid == conversation_uuid
    )
    result = await db_session.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    short_url_stmt = select(db_models.ShortURL).where(
        db_models.ShortURL.target_path == f"/conversation/{conversation_uuid}"
    )
    short_url_result = await db_session.execute(short_url_stmt)
    short_url = short_url_result.scalar_one_or_none()
    if not short_url:
        raise AssertionError(f"No short URL found for conversation {conversation_uuid}")

    return models.ConversationResponse(
        uuid=conversation.uuid,
        question=conversation.question,
        answer=conversation.answer,
        model=conversation.model or "",  # Handle Optional[str]
        k=conversation.k,
        created_at=conversation.created_at.replace(
            tzinfo=datetime.timezone.utc
        ).timestamp(),
        generation_time_seconds=conversation.generation_time_seconds
        or 0.0,  # Handle Optional[float]
        final_generation_input_text_length=(
            conversation.final_generation_input_text_length or 0
        ),
        retrieval_unique_chunk_count=conversation.retrieval_unique_chunk_count or 0,
        retrieval_unique_file_count=conversation.retrieval_unique_file_count or 0,
        language=conversation.language,
        short_slug=short_url.slug,
        proper_nouns=conversation.proper_nouns or [],
    )
