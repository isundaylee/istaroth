"""Conversation endpoints."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from istaroth.backend import db_models, models
from istaroth.backend.dependencies import DBSession
from istaroth.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


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

    return models.ConversationResponse(
        uuid=conversation.uuid,
        question=conversation.question,
        answer=conversation.answer,
        model=conversation.model or "",  # Handle Optional[str]
        k=conversation.k,
        created_at=conversation.created_at.timestamp(),
        generation_time_seconds=conversation.generation_time_seconds
        or 0.0,  # Handle Optional[float]
        language=conversation.language,
    )
