"""SQLAlchemy database models for the backend."""

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Conversation(Base):
    """SQLAlchemy model for storing conversation history."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    model: Mapped[str] = mapped_column(String(100), nullable=False)
    k: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(
            tzinfo=None
        ),
    )
    generation_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )


class ShortURL(Base):
    """SQLAlchemy model for generic short URL mappings."""

    __tablename__ = "short_urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    target_path: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(
            tzinfo=None
        ),
    )

    __table_args__ = (Index("ix_short_urls_slug", "slug"),)
