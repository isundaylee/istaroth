"""Database configuration and session management."""

import logging
import os

import sqlalchemy
import sqlalchemy.orm

from istaroth.backend import db_models

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


def create_engine() -> sqlalchemy.Engine:
    """Create SQLAlchemy engine."""
    uri = get_database_uri()
    logger.info("Creating database engine with URI: %s", uri)
    return sqlalchemy.create_engine(uri, echo=False)


def get_session_factory(engine: sqlalchemy.Engine) -> sqlalchemy.orm.sessionmaker:
    """Create session factory."""
    return sqlalchemy.orm.sessionmaker(bind=engine)


def init_database(engine: sqlalchemy.Engine) -> None:
    """Initialize database tables."""
    logger.info("Initializing database tables...")
    db_models.Base.metadata.create_all(engine)
    logger.info("Database tables initialized successfully")
