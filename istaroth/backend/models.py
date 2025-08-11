"""Request and response models for the backend API."""

import datetime

import attrs


@attrs.define
class QueryRequest:
    """Request model for query endpoint."""

    language: str
    question: str
    model: str
    k: int = attrs.field()

    @k.validator
    def _validate_k(self, attribute: attrs.Attribute, value: int) -> None:
        if value <= 0:
            raise ValueError("k must be positive")
        if value > 100:
            raise ValueError("k must not exceed 100")


@attrs.define
class QueryResponse:
    """Response model for query endpoint."""

    language: str
    question: str
    answer: str
    conversation_id: str


@attrs.define
class ConversationResponse:
    """Response model for conversation retrieval."""

    uuid: str
    language: str
    question: str
    answer: str
    model: str
    k: int
    created_at: float  # Unix timestamp as float
    generation_time_seconds: float


@attrs.define
class ErrorResponse:
    """Error response model for API errors."""

    error: str
