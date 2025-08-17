"""Request and response models for the backend API.

IMPORTANT: Keep these models in sync with frontend/src/types/api.ts
Any changes to request/response structures should be reflected in both files.
"""

from typing import Any

from pydantic import BaseModel, field_validator

from istaroth.agd import localization


class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    language: str
    question: str
    model: str
    k: int
    chunk_context: int

    @field_validator("k")
    @classmethod
    def _validate_k(cls, value: int) -> int:
        if not (0 < value <= 15):
            raise ValueError("Invalid k value: must be between 1 and 15")
        return value

    @field_validator("chunk_context")
    @classmethod
    def _validate_chunk_context(cls, value: int) -> int:
        if not (0 < value <= 10):
            raise ValueError("Invalid chunk_context value: must be between 1 and 10")
        return value


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    language: str
    question: str
    answer: str
    conversation_id: str


class ConversationResponse(BaseModel):
    """Response model for conversation retrieval."""

    uuid: str
    language: str
    question: str
    answer: str
    model: str
    k: int
    created_at: float  # Unix timestamp as float
    generation_time_seconds: float


class ErrorResponse(BaseModel):
    """Error response model for API errors."""

    error: str


class ModelsResponse(BaseModel):
    """Response model for available models endpoint."""

    models: list[str]


class ExampleQuestionRequest(BaseModel):
    """Request model for example question endpoint."""

    language: str

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        if value not in {l.value for l in localization.Language}:
            raise ValueError(f"Invalid language: {value}")
        return value


class ExampleQuestionResponse(BaseModel):
    """Response model for example question endpoint."""

    question: str
    language: str


class CitationResponse(BaseModel):
    """Response model for citation content endpoint."""

    file_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    total_chunks: int
