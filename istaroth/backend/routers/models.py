"""Model endpoints."""

import logging

from fastapi import APIRouter

from istaroth import llm_manager
from istaroth.backend import models
from istaroth.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/models", response_model=models.ModelsResponse)
@handle_unexpected_exception
async def get_models() -> models.ModelsResponse:
    """Get list of available models."""
    return models.ModelsResponse(models=llm_manager.get_available_models())
