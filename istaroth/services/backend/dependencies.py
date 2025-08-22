"""FastAPI dependency injection for shared resources."""

import logging
from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from istaroth import llm_manager
from istaroth.rag import document_store_set
from istaroth.services.backend import database

logger = logging.getLogger(__name__)

# Global resources (initialized in init_resources)
_async_db_session_factory = None
_document_store_set = None
_llm_manager = None


def init_resources() -> None:
    """Initialize global resources. Called at application startup."""
    global _async_db_session_factory, _document_store_set, _llm_manager

    logger.info("Initializing backend resources...")

    # Initialize database connection (migrations are now handled by initContainer)
    logger.info("Initializing database connection")
    # Create async engine and session factory for application use
    _async_db_session_factory = database.get_async_session_factory(
        database.create_async_engine()
    )
    logger.info("Database connection initialized successfully")

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


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session."""
    if _async_db_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_resources() first.")

    async with _async_db_session_factory() as session:
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
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
DocumentStoreSet = Annotated[
    document_store_set.DocumentStoreSet, Depends(get_document_store_set)
]
LLMManager = Annotated[llm_manager.LLMManager, Depends(get_llm_manager)]
