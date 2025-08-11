"""Flask application for the Istaroth RAG backend."""

import functools
import logging
import time
import traceback
from typing import Callable, ParamSpec, TypeVar

import attrs
import flask

from istaroth.agd import localization
from istaroth.backend import database, db_models, models
from istaroth.rag import document_store_set, pipeline

logger = logging.getLogger(__name__)

P = ParamSpec("P")


def _handle_unexpected_exception(
    func: Callable[P, tuple[dict, int]],
) -> Callable[P, tuple[dict, int]]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> tuple[dict, int]:
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.error("Error in %s", func.__name__, exc_info=True)
            return (
                attrs.asdict(models.ErrorResponse(error="Internal server error")),
                500,
            )

    return wrapper


class BackendApp:
    """Flask backend application."""

    def __init__(self):
        """Initialize the backend application."""
        self.app = flask.Flask(__name__)

        # Initialize resources
        logger.info("Initializing backend resources...")

        # Initialize database
        logger.info("Initializing database connection")
        self.db_engine = database.create_engine()
        database.init_database(self.db_engine)
        self.db_session_factory = database.get_session_factory(self.db_engine)
        logger.info("Database initialized successfully")

        # Load document store set from environment
        logger.info("Loading document store set from environment")
        self.document_store_set = document_store_set.DocumentStoreSet.from_env()
        logger.info(
            "Document store set loaded %d languages: %s",
            len(self.document_store_set.available_languages),
            ", ".join(l.value for l in self.document_store_set.available_languages),
        )

        # Initialize LLM manager
        logger.info("Initializing LLM manager")
        self.llm_manager = pipeline.LLMManager()

        # RAG pipeline will be created per-query with language-specific document store
        logger.info("Backend initialization completed successfully")

        # Register routes
        self._register_routes()

    def _register_routes(self) -> None:
        """Register API routes."""
        self.app.add_url_rule("/api/query", "query", self._query, methods=["POST"])
        self.app.add_url_rule(
            "/api/conversations/<string:conversation_uuid>",
            "get_conversation",
            self._get_conversation,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/models", "get_models", self._get_models, methods=["GET"]
        )

    @_handle_unexpected_exception
    def _query(self) -> tuple[dict, int]:
        """Answer a question using the RAG pipeline."""
        # Parse request
        data = flask.request.get_json()
        if not data:
            return {"error": "Invalid JSON request"}, 400

        # Validate request
        try:
            request = models.QueryRequest(
                question=data["question"],
                k=data.get("k", 10),
                model=data.get("model"),
                language=data["language"],
            )
        except (TypeError, ValueError, KeyError) as e:
            return attrs.asdict(models.ErrorResponse(error=repr(e))), 400

        # Get document store for requested language
        try:
            selected_store = self.document_store_set.get_store(
                localization.Language(request.language)
            )
            language_name = request.language.upper()
        except (ValueError, KeyError) as e:
            return attrs.asdict(models.ErrorResponse(error=repr(e))), 400

        # Get LLM for the requested model
        try:
            llm = self.llm_manager.get_llm(request.model)
        except ValueError as e:
            return attrs.asdict(models.ErrorResponse(error=repr(e))), 400

        # Get the language enum for the RAG pipeline
        language_enum = localization.Language(request.language)

        # Create RAG pipeline for the selected language
        rag_pipeline = pipeline.RAGPipeline(selected_store, language_enum)

        # Get answer and track timing
        logger.info(
            "Processing query: %s with k=%d using model: %s, language: %s",
            request.question,
            request.k,
            request.model,
            language_name,
        )
        start_time = time.perf_counter()
        answer = rag_pipeline.answer(request.question, k=request.k, llm=llm)
        generation_time = time.perf_counter() - start_time

        logger.info("Query completed in %.2f seconds", generation_time)

        # Save conversation to database
        conversation_uuid = self._save_conversation(request, answer, generation_time)

        # Return response
        return (
            attrs.asdict(
                models.QueryResponse(
                    question=request.question,
                    answer=answer,
                    conversation_id=conversation_uuid,
                    language=language_name,
                )
            ),
            200,
        )

    def _save_conversation(
        self, request: models.QueryRequest, answer: str, generation_time: float
    ) -> str:
        """Save conversation to database and return the conversation ID."""
        try:
            with self.db_session_factory() as session:
                conversation = db_models.Conversation(
                    question=request.question,
                    answer=answer,
                    model=request.model,
                    k=request.k,
                    language=request.language,
                    generation_time_seconds=generation_time,
                )
                session.add(conversation)
                session.commit()
                logger.info(
                    "Conversation saved to database with UUID: %s", conversation.uuid
                )
                return conversation.uuid
        except Exception as e:
            logger.error("Failed to save conversation to database: %s", e)
            return ""  # Return empty string on error

    @_handle_unexpected_exception
    def _get_conversation(self, conversation_uuid: str) -> tuple[dict, int]:
        """Get a specific conversation by ID."""
        with self.db_session_factory() as session:
            conversation = (
                session.query(db_models.Conversation)
                .filter_by(uuid=conversation_uuid)
                .first()
            )

            if not conversation:
                return (
                    attrs.asdict(models.ErrorResponse(error="Conversation not found")),
                    404,
                )

            response = models.ConversationResponse(
                uuid=conversation.uuid,
                question=conversation.question,
                answer=conversation.answer,
                model=conversation.model,
                k=conversation.k,
                created_at=conversation.created_at.timestamp(),
                generation_time_seconds=conversation.generation_time_seconds,
                language=conversation.language,
            )

            return attrs.asdict(response), 200

    @_handle_unexpected_exception
    def _get_models(self) -> tuple[dict, int]:
        """Get list of available models."""
        return (
            attrs.asdict(models.ModelsResponse(models=pipeline.get_available_models())),
            200,
        )


def create_app() -> flask.Flask:
    """Create and configure the Flask application."""
    backend = BackendApp()
    return backend.app
