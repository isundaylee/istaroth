"""Example question endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from istaroth.agd import localization
from istaroth.backend import example_questions, models
from istaroth.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/example-question", response_model=models.ExampleQuestionResponse)
@handle_unexpected_exception
async def get_example_question(
    language: Annotated[str, Query()] = "eng",
) -> models.ExampleQuestionResponse:
    """Get a random example question for the specified language."""
    # Validate request
    try:
        request = models.ExampleQuestionRequest(language=language)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=repr(e))

    # Get random example question
    try:
        # Convert string to Language enum
        question = example_questions.get_random_example_question(
            localization.Language(request.language)
        )
        return models.ExampleQuestionResponse(
            question=question, language=request.language
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=repr(e))
