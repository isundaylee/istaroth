"""Request and response models for the backend API.

IMPORTANT: Keep these models in sync with frontend/src/types/api.ts
Any changes to request/response structures should be reflected in both files.
"""

import datetime

import attrs

from istaroth.agd import localization


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


@attrs.define
class ModelsResponse:
    """Response model for available models endpoint."""

    models: list[str]


@attrs.define
class ExampleQuestionRequest:
    """Request model for example question endpoint."""

    language: str = attrs.field()

    @language.validator
    def _validate_language(self, attribute: attrs.Attribute, value: str) -> None:
        if value not in {l.value for l in localization.Language}:
            raise ValueError(f"Invalid language: {value}")


@attrs.define
class ExampleQuestionResponse:
    """Response model for example question endpoint."""

    question: str
    language: str


@attrs.define
class CitationResponse:
    """Response model for citation content endpoint."""

    file_id: str
    chunk_index: int
    content: str
    metadata: dict
    total_chunks: int
