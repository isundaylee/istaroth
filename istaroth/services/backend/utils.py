"""Shared utilities for FastAPI backend."""

import functools
import logging
from typing import Awaitable, Callable, ParamSpec, TypeVar

from fastapi import HTTPException

from istaroth.rag import text_set
from istaroth.services.backend import models
from istaroth.text import types as text_types

logger = logging.getLogger(__name__)

PS = ParamSpec("PS")
R = TypeVar("R")


def handle_unexpected_exception(
    func: Callable[PS, Awaitable[R]],
) -> Callable[PS, Awaitable[R]]:
    """Decorator to handle unexpected exceptions in endpoint methods."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions (these are expected)
            raise
        except Exception:
            logger.error("Error in %s", func.__name__, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

    return wrapper


def text_metadata_to_library_file_info(
    metadata: text_types.TextMetadata,
) -> models.LibraryFileInfo:
    """Convert TextMetadata to LibraryFileInfo, reconciling type differences.

    Maps:
    - category: TextCategory enum -> directory name string
    - title -> title (direct mapping)
    - id: int -> int (direct mapping)
    - relative_path -> relative_path
    """
    category_dir = metadata.category.value

    return models.LibraryFileInfo(
        category=category_dir,
        title=metadata.title,
        id=metadata.id,
        relative_path=metadata.relative_path,
    )
