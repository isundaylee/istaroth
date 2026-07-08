"""Short URL resolution endpoints."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from istaroth.services.backend import db_models, models, slugs
from istaroth.services.backend.dependencies import DBSession
from istaroth.services.backend.utils import handle_unexpected_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/short-urls", response_model=models.ShortURLResponse)
@handle_unexpected_exception
async def create_short_url(
    request: models.ShortURLCreateRequest, db_session: DBSession
) -> models.ShortURLResponse:
    """Create (or reuse) a short URL for an in-app target path."""
    return models.ShortURLResponse(
        slug=await slugs.get_or_create_short_url(
            request.target_path, db_session=db_session
        ),
        target_path=request.target_path,
    )


@router.get("/api/short-urls/{slug}", response_model=models.ShortURLResponse)
@handle_unexpected_exception
async def resolve_short_url(
    slug: str, db_session: DBSession
) -> models.ShortURLResponse:
    """Resolve a short URL slug to its target path."""
    stmt = select(db_models.ShortURL).where(db_models.ShortURL.slug == slug)
    result = await db_session.execute(stmt)
    short_url = result.scalar_one_or_none()

    if not short_url:
        raise HTTPException(status_code=404, detail="Short URL not found")

    return models.ShortURLResponse(
        slug=short_url.slug, target_path=short_url.target_path
    )
