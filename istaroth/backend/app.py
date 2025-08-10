"""Flask application for the Istaroth RAG backend."""

import logging
import traceback

import attrs
import flask
from langchain_google_genai import llms as google_llms

from istaroth.backend import models
from istaroth.rag import document_store, pipeline

logger = logging.getLogger(__name__)


class BackendApp:
    """Flask backend application."""

    def __init__(self):
        """Initialize the backend application."""
        self.app = flask.Flask(__name__)

        # Initialize resources
        logger.info("Initializing backend resources...")

        # Load document store from environment
        logger.info("Loading document store from environment")
        self.document_store = document_store.DocumentStore.from_env()
        logger.info(
            "Document store loaded with %d documents", self.document_store.num_documents
        )

        # Initialize LLM
        logger.info("Initializing Google Gemini LLM")
        self.llm = google_llms.GoogleGenerativeAI(model="gemini-2.0-flash-lite")

        # Create RAG pipeline with default k=10
        self.rag_pipeline = pipeline.RAGPipeline(self.document_store, self.llm)
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
                request = models.QueryRequest(question=data["question"], k=data["k"])
            except (TypeError, ValueError, KeyError) as e:
                return attrs.asdict(models.ErrorResponse(error=repr(e))), 400

            # Get answer
            logger.info("Processing query: %s with k=%d", request.question, request.k)
            answer = self.rag_pipeline.answer(request.question, k=request.k)

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


def create_app() -> flask.Flask:
    """Create and configure the Flask application."""
    backend = BackendApp()
    return backend.app
