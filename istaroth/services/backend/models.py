"""Request and response models for the backend API.

IMPORTANT: Keep these models in sync with frontend/src/types/api.ts
Any changes to request/response structures should be reflected in both files.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, field_validator

from istaroth.agd import localization


class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    language: str
    question: str
    model: str
    budget: int
    client_id: str | None = None
    # When set, the result is cached under this key (composed with the language
    # by the backend) so repeat lookups replay the stored conversation directly.
    cache_key: str | None = None

    @field_validator("budget")
    @classmethod
    def _validate_budget(cls, value: int) -> int:
        if not (3 <= value <= 400):
            raise ValueError("Invalid budget value: must be between 3 and 400")
        return value


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    language: str
    question: str
    answer: str
    conversation_uuid: str
    short_slug: str
    proper_nouns: list[str]
    final_generation_input_text_length: int
    retrieval_unique_chunk_count: int
    retrieval_unique_file_count: int


# Events streamed (newline-delimited JSON) by POST /api/query/stream. The
# step events mirror the wire format of ``istaroth.rag.progress``; the terminal
# ``done``/``error`` events are emitted by the router.
class QueryStreamStepStart(BaseModel):
    """A pipeline step has started (shown until its matching step_end)."""

    type: Literal["step_start"] = "step_start"
    id: str
    kind: str
    detail: str | None


class QueryStreamStepEnd(BaseModel):
    """A previously started pipeline step has ended."""

    type: Literal["step_end"] = "step_end"
    id: str


class QueryStreamDone(BaseModel):
    """Terminal event carrying the completed answer."""

    type: Literal["done"] = "done"
    result: QueryResponse


class QueryStreamError(BaseModel):
    """Terminal event signalling the query failed."""

    type: Literal["error"] = "error"
    error: str


QueryStreamEvent = (
    QueryStreamStepStart | QueryStreamStepEnd | QueryStreamDone | QueryStreamError
)


class ConversationResponse(BaseModel):
    """Response model for conversation retrieval."""

    uuid: str
    language: str
    question: str
    answer: str
    model: str
    k: int
    budget: int | None = None
    created_at: float  # Unix timestamp as float
    generation_time_seconds: float
    final_generation_input_text_length: int
    retrieval_unique_chunk_count: int
    retrieval_unique_file_count: int
    short_slug: str
    proper_nouns: list[str]


class ConversationSummary(BaseModel):
    """Lightweight conversation metadata for the history list."""

    id: int
    uuid: str
    question: str
    language: str
    model: str
    created_at: float  # Unix timestamp as float


class ConversationListResponse(BaseModel):
    """Response model for listing a client's conversations, newest first."""

    conversations: list[ConversationSummary]


class ShortURLResponse(BaseModel):
    """Response model for short URL resolution."""

    slug: str
    target_path: str


class ErrorResponse(BaseModel):
    """Error response model for API errors."""

    error: str


class ModelsResponse(BaseModel):
    """Response model for available models endpoint."""

    models: list[str]
    default: str


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
    file_info: LibraryFileInfo
    start_index: int
    end_index: int


class CitationBatchRequest(BaseModel):
    """Request model for batch citation endpoint."""

    language: str
    citations: list[tuple[str, int]]  # List of (file_id, chunk_index) pairs

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        if value.upper() not in {l.value for l in localization.Language}:
            raise ValueError(f"Invalid language: {value}")
        return value.upper()


class CitationError(BaseModel):
    """Error details for a failed citation fetch."""

    file_id: str
    chunk_index: int
    error: str


class CitationBatchResponse(BaseModel):
    """Response model for batch citation endpoint."""

    successes: list[CitationResponse]
    errors: list[CitationError]


class LibraryFileInfo(BaseModel):
    """File information with parsed components.

    ``min_version``/``max_version`` bound the game versions in which the file's
    source content first appeared; ``None`` for non-AGD content.
    """

    category: str
    title: str
    id: int
    relative_path: str
    min_version: str | None
    max_version: str | None


class LibraryFileResponse(BaseModel):
    """Response model for library file content endpoint."""

    file_info: LibraryFileInfo
    content: str


class LibraryRetrieveRequest(BaseModel):
    """Request model for library retrieval endpoint."""

    language: str
    query: str
    k: int
    semantic: bool = False

    @field_validator("k")
    @classmethod
    def _validate_k(cls, value: int) -> int:
        if not (0 < value <= 15):
            raise ValueError("Invalid k value: must be between 1 and 15")
        return value


class LibraryRetrieveResult(BaseModel):
    """Single retrieved library document with snippet."""

    file_info: LibraryFileInfo
    snippet: str
    score: float


class LibraryRetrieveResponse(BaseModel):
    """Response model for library retrieval endpoint."""

    query: str
    results: list[LibraryRetrieveResult]


class ProperNounsResponse(BaseModel):
    """Response model for the proper-nouns endpoints.

    ``nouns`` are proper nouns the frontend highlights: either the static curated
    list for a language or those extracted on the fly from a single file's
    content (empty for languages without support, e.g. ENG).
    """

    nouns: list[str]


class HierarchyNode(BaseModel):
    """One node in a browsable document hierarchy.

    A node is either a group (``children`` set) or a leaf (``file_id`` set, a
    viewable file). ``title`` is the resolved display label. ``max_version`` is
    the newest first-seen game version in the node's subtree (the file's own for
    a leaf); ``None`` for versionless (non-AGD) content.
    """

    key: str
    title: str | None
    children: list["HierarchyNode"] | None
    file_id: int | None
    toc_eligible: bool
    max_version: str | None


class LibraryCategoryHierarchy(BaseModel):
    """One category's document tree within the full library hierarchy.

    ``title`` is the category's localized display label, mirroring
    ``HierarchyNode``'s ``key``/``title`` pairing (with ``category`` as the key).
    """

    category: str
    title: str
    nodes: list[HierarchyNode]


class LibraryHierarchyResponse(BaseModel):
    """Full library hierarchy: every category's document tree, in display order.

    ``latest_version`` is the newest first-seen game version anywhere in the
    corpus, letting clients badge content added in the latest version.
    """

    categories: list[LibraryCategoryHierarchy]
    latest_version: str | None


class VersionResponse(BaseModel):
    """Response model for version endpoint."""

    checkpoint_versions: dict[str, str | None]
