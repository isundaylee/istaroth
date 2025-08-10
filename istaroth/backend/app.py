"""Flask application for the Istaroth RAG backend."""

import logging
import traceback

import attrs
import flask

from istaroth.backend import database, db_models, models
from istaroth.rag import document_store, pipeline

logger = logging.getLogger(__name__)


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

        # Load document store from environment
        logger.info("Loading document store from environment")
        self.document_store = document_store.DocumentStore.from_env()
        logger.info(
            "Document store loaded with %d documents", self.document_store.num_documents
        )

        # Initialize LLM manager
        logger.info("Initializing LLM manager")
        self.llm_manager = pipeline.LLMManager()

        # Create RAG pipeline (without fixed LLM)
        self.rag_pipeline = pipeline.RAGPipeline(self.document_store)
        logger.info("RAG pipeline initialized successfully")

        # Register routes
        self._register_routes()

    def _register_routes(self) -> None:
        """Register API routes."""
        self.app.add_url_rule("/api/query", "query", self._query, methods=["POST"])

    def _query(self) -> tuple[dict, int]:
        """Answer a question using the RAG pipeline."""
        if not self.rag_pipeline:
            return {"error": "RAG pipeline not initialized"}, 503

        try:
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
                )
            except (TypeError, ValueError, KeyError) as e:
                return attrs.asdict(models.ErrorResponse(error=repr(e))), 400

            # Get LLM for the requested model
            try:
                llm = self.llm_manager.get_llm(request.model)
            except ValueError as e:
                return attrs.asdict(models.ErrorResponse(error=str(e))), 400

            # Get answer
            model_info = getattr(llm, "model", getattr(llm, "model_name", "unknown"))
            logger.info(
                "Processing query: %s with k=%d using model: %s",
                request.question,
                request.k,
                model_info,
            )
            answer = self.rag_pipeline.answer(request.question, k=request.k, llm=llm)

            # Save conversation to database
            self._save_conversation(request, answer)

            # Return response
            return (
                attrs.asdict(
                    models.QueryResponse(question=request.question, answer=answer)
                ),
                200,
            )

        except Exception as e:
            logger.error("Error processing query: %s\n%s", e, traceback.format_exc())
            return {"error": "Internal server error"}, 500

    def _save_conversation(self, request: models.QueryRequest, answer: str) -> None:
        """Save conversation to database."""
        try:
            with self.db_session_factory() as session:
                conversation = db_models.Conversation(
                    question=request.question,
                    answer=answer,
                    model=request.model,
                    k=request.k,
                )
                session.add(conversation)
                session.commit()
                logger.info(
                    "Conversation saved to database with ID: %d", conversation.id
                )
        except Exception as e:
            logger.error("Failed to save conversation to database: %s", e)


def create_app() -> flask.Flask:
    """Create and configure the Flask application."""
    backend = BackendApp()
    return backend.app
