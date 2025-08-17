"""Database configuration and session management."""

import logging
import os
from pathlib import Path

import alembic.command
import alembic.config
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
    logger.info("Creating database engine")
    return sqlalchemy.create_engine(uri, echo=False)


def get_session_factory(engine: sqlalchemy.Engine) -> sqlalchemy.orm.sessionmaker:
    """Create session factory."""
    return sqlalchemy.orm.sessionmaker(bind=engine)


def run_migrations() -> None:
    """Run database migrations using Alembic."""
    logger.info("Running database migrations...")

    # Get the project root directory
    project_root = Path(__file__).parent.parent.parent
    alembic_cfg_path = project_root / "alembic.ini"

    if not alembic_cfg_path.exists():
        raise FileNotFoundError(f"Alembic config file not found at {alembic_cfg_path}")

    # Create Alembic configuration
    alembic_cfg = alembic.config.Config(str(alembic_cfg_path))
    alembic_cfg.attributes["configure_logger"] = False

    # Run migrations to head
    alembic.command.upgrade(alembic_cfg, "head")

    logger.info("Database migrations completed successfully")


def init_database(engine: sqlalchemy.Engine) -> None:
    """Initialize database using migrations."""
    logger.info("Initializing database...")

    # Run migrations instead of create_all
    run_migrations()

    logger.info("Database initialization completed")
