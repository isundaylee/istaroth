"""SQLAlchemy database models for the backend."""

import datetime
import uuid
from typing import Any

import sqlalchemy
import sqlalchemy.orm

# SQLAlchemy ORM models
Base: Any = sqlalchemy.orm.declarative_base()


class Conversation(Base):
    """SQLAlchemy model for storing conversation history."""

    __tablename__ = "conversations"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    question = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    answer = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    model = sqlalchemy.Column(sqlalchemy.String(100), nullable=True)
    k = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    language = sqlalchemy.Column(sqlalchemy.String(10), nullable=False)
    created_at = sqlalchemy.Column(
        sqlalchemy.DateTime, default=datetime.datetime.utcnow
    )
    generation_time_seconds = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
