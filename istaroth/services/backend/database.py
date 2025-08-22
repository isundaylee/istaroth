"""Database configuration and session management."""

import logging
import os
from pathlib import Path

import alembic.command
import alembic.config
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

from istaroth.services.backend import db_models

logger = logging.getLogger(__name__)


def get_database_uri() -> str:
    """Get database URI from environment variable."""
    uri = os.environ.get("ISTAROTH_DATABASE_URI")
    if not uri:
        raise ValueError(
            "ISTAROTH_DATABASE_URI environment variable is required but not set. "
            "Please set it to a valid database URI (e.g., sqlite:///tmp/istaroth.db)"
        )
    return uri


def get_sync_database_uri() -> str:
    """Get synchronous database URI, converting async URIs if necessary."""
    uri = get_database_uri()
    # Convert async URI to sync for migrations and sync operations
    if uri.startswith("postgresql+asyncpg://"):
        uri = uri.replace("postgresql+asyncpg://", "postgresql://")
    elif uri.startswith("sqlite+aiosqlite://"):
        uri = uri.replace("sqlite+aiosqlite://", "sqlite://")
    return uri


def create_async_engine() -> sqlalchemy.ext.asyncio.AsyncEngine:
    """Create async SQLAlchemy engine."""
    uri = get_database_uri()
    logger.info("Creating async database engine")
    return sqlalchemy.ext.asyncio.create_async_engine(uri, echo=False)


def get_async_session_factory(
    async_engine: sqlalchemy.ext.asyncio.AsyncEngine,
) -> sqlalchemy.ext.asyncio.async_sessionmaker:
    """Create async session factory."""
    return sqlalchemy.ext.asyncio.async_sessionmaker(bind=async_engine)


def get_session_factory(engine: sqlalchemy.Engine) -> sqlalchemy.orm.sessionmaker:
    """Create sync session factory for migrations."""
    return sqlalchemy.orm.sessionmaker(bind=engine)
