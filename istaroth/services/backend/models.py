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
    k: int
    chunk_context: int
    client_id: str | None = None
    # When set, the result is cached under this key (composed with the language
    # by the backend) so repeat lookups replay the stored conversation directly.
    cache_key: str | None = None

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


class LibraryCategoriesResponse(BaseModel):
    """Response model for library categories endpoint."""

    categories: list[str]


class LibraryFileInfo(BaseModel):
    """File information with parsed components."""

    category: str
    title: str
    id: int
    relative_path: str


class LibraryFilesResponse(BaseModel):
    """Response model for library files endpoint."""

    files: list[LibraryFileInfo]


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
    chunk_context: int = 0

    @field_validator("k")
    @classmethod
    def _validate_k(cls, value: int) -> int:
        if not (0 < value <= 15):
            raise ValueError("Invalid k value: must be between 1 and 15")
        return value

    @field_validator("chunk_context")
    @classmethod
    def _validate_chunk_context(cls, value: int) -> int:
        if not (0 <= value <= 10):
            raise ValueError("Invalid chunk_context value: must be between 0 and 10")
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


class QuestHierarchyQuest(BaseModel):
    """A single quest leaf in the quest hierarchy."""

    id: int
    title: str


class QuestHierarchyChapter(BaseModel):
    """One chapter (act) grouping a set of quests."""

    chapter_id: int
    chapter_title: str
    quests: list[QuestHierarchyQuest]


class QuestHierarchySeries(BaseModel):
    """A series (questline) grouping chapters that share a chapter group."""

    series_id: int
    series_title: str
    chapters: list[QuestHierarchyChapter]


class QuestHierarchyType(BaseModel):
    """A top-level quest type and the quests under it.

    ``chapters`` holds chapters with no series; ``standalone_quests`` holds quests
    with no chapter.
    """

    quest_type: str
    series: list[QuestHierarchySeries]
    chapters: list[QuestHierarchyChapter]
    standalone_quests: list[QuestHierarchyQuest]


class QuestHierarchyResponse(BaseModel):
    """Response model for the quest hierarchy endpoint."""

    types: list[QuestHierarchyType]


class QuestSeriesResponse(BaseModel):
    """The series (or lone chapter) enclosing a quest, for the detail-page TOC.

    Only returned for a quest present in the hierarchy, so ``quest_type`` (the
    enclosing top-level type, used to point the back button at the right type
    listing) is always set. ``series`` and ``chapter`` are mutually exclusive and
    both null for a standalone quest.
    """

    quest_type: str
    series: QuestHierarchySeries | None = None
    chapter: QuestHierarchyChapter | None = None


class CoopHierarchyQuest(BaseModel):
    """A single hangout quest leaf in the hangout hierarchy."""

    id: int
    title: str


class CoopHierarchyChapter(BaseModel):
    """One hangout chapter (act) grouping a character's hangout quests."""

    chapter_id: int
    chapter_title: str
    quests: list[CoopHierarchyQuest]


class CoopHierarchyCharacter(BaseModel):
    """One character and the hangout chapters (acts) under them."""

    avatar_id: int
    character_name: str
    chapters: list[CoopHierarchyChapter]


class CoopHierarchyResponse(BaseModel):
    """Response model for the hangout hierarchy endpoint."""

    characters: list[CoopHierarchyCharacter]


class CoopCharacterResponse(BaseModel):
    """The character (and enclosing chapter) of a hangout quest, for its TOC.

    Only returned for a hangout quest present in the hierarchy, so
    ``character_name`` is always set; ``chapter`` is the enclosing act.
    """

    avatar_id: int
    character_name: str
    chapter: CoopHierarchyChapter


class VersionResponse(BaseModel):
    """Response model for version endpoint."""

    checkpoint_versions: dict[str, str | None]
