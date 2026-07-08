"""Slug generation and persistence utilities for short URLs."""

import secrets
import string

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from istaroth.services.backend import db_models

_ALPHABET = string.ascii_letters + string.digits


def generate_slug(*, length: int = 8) -> str:
    """Generate a random alphanumeric slug."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


async def get_or_create_short_url(target_path: str, *, db_session: AsyncSession) -> str:
    """Return the slug mapping to ``target_path``, creating one if absent.

    Commits the session (including any pending changes) on successful creation.
    """
    existing = (
        (
            await db_session.execute(
                select(db_models.ShortURL).where(
                    db_models.ShortURL.target_path == target_path
                )
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing.slug

    for _ in range(5):
        slug = generate_slug()
        try:
            async with db_session.begin_nested():
                db_session.add(db_models.ShortURL(slug=slug, target_path=target_path))
                await db_session.flush()
        except IntegrityError:
            continue
        await db_session.commit()
        return slug

    await db_session.rollback()
    raise RuntimeError("Failed to generate a unique short URL slug after 5 attempts")
