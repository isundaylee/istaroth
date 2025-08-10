"""Request and response models for the backend API."""

import datetime

import attrs


@attrs.define
class QueryRequest:
    """Request model for query endpoint."""

    question: str = attrs.field()
    k: int = attrs.field(default=10)
    model: str | None = attrs.field(default=None)

    @k.validator
    def _validate_k(self, attribute: attrs.Attribute, value: int) -> None:
        if value <= 0:
            raise ValueError("k must be positive")
        if value > 100:
            raise ValueError("k must not exceed 100")


@attrs.define
class QueryResponse:
    """Response model for query endpoint."""

    question: str = attrs.field()
    answer: str = attrs.field()
    conversation_id: int = attrs.field()


@attrs.define
class ConversationResponse:
    """Response model for conversation retrieval."""

    id: int = attrs.field()
    question: str = attrs.field()
    answer: str = attrs.field()
    model: str | None = attrs.field()
    k: int = attrs.field()
    created_at: float = attrs.field()  # Unix timestamp as float


@attrs.define
class ErrorResponse:
    """Error response model for API errors."""

    error: str = attrs.field()
