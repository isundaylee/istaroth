"""FastAPI dependency injection for shared resources."""

import logging
from typing import Annotated, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from istaroth import llm_manager
from istaroth.backend import database
from istaroth.rag import document_store_set

logger = logging.getLogger(__name__)

# Global resources (initialized in init_resources)
_db_session_factory = None
_document_store_set = None
_llm_manager = None


def init_resources() -> None:
    """Initialize global resources. Called at application startup."""
    global _db_session_factory, _document_store_set, _llm_manager

    logger.info("Initializing backend resources...")

    # Initialize database
    logger.info("Initializing database connection")
    db_engine = database.create_engine()
    database.init_database(db_engine)
    _db_session_factory = database.get_session_factory(db_engine)
    logger.info("Database initialized successfully")

    # Load document store set from environment
    logger.info("Loading document store set from environment")
    _document_store_set = document_store_set.DocumentStoreSet.from_env()
    logger.info(
        "Document store set loaded %d languages: %s",
        len(_document_store_set.available_languages),
        ", ".join(l.value for l in _document_store_set.available_languages),
    )

    # Initialize LLM manager
    logger.info("Initializing LLM manager")
    _llm_manager = llm_manager.LLMManager()

    logger.info("Backend initialization completed successfully")


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    if _db_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_resources() first.")

    with _db_session_factory() as session:
        yield session


def get_document_store_set() -> document_store_set.DocumentStoreSet:
    """Dependency to get document store set."""
    if _document_store_set is None:
        raise RuntimeError(
            "Document store set not initialized. Call init_resources() first."
        )
    return _document_store_set


def get_llm_manager() -> llm_manager.LLMManager:
    """Dependency to get LLM manager."""
    if _llm_manager is None:
        raise RuntimeError("LLM manager not initialized. Call init_resources() first.")
    return _llm_manager


# Type aliases for dependency injection
DBSession = Annotated[Session, Depends(get_db_session)]
DocumentStoreSet = Annotated[
    document_store_set.DocumentStoreSet, Depends(get_document_store_set)
]
LLMManager = Annotated[llm_manager.LLMManager, Depends(get_llm_manager)]
