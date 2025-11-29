"""Shared utilities for FastAPI backend."""

import functools
import logging
from typing import Awaitable, Callable, ParamSpec, TypeVar

from fastapi import HTTPException

from istaroth.rag import text_set
from istaroth.services.backend import models

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


def parse_filename(filename: str) -> models.LibraryFileInfo:
    """Parse filename into components: category, name, and id.

    The category is automatically determined from the filename prefix.
    Expected format: {prefix}_{name}_{id}.txt or {prefix}_{name}.txt
    The filename MUST start with a known category prefix.
    The ID is only extracted if the last part after the final underscore is an integer.

    Raises:
        ValueError: If the filename format is invalid or doesn't match any known category prefix.
    """
    if not filename.endswith(".txt"):
        raise ValueError(f"Invalid filename format: {filename}")

    # Get category from filename prefix
    category = text_set.get_category_from_filename(filename)
    expected_prefix = text_set.get_category_prefix(category)
    name_without_ext = filename[:-4]  # Remove .txt

    # Require category prefix (should always match since we got category from it)
    if not name_without_ext.startswith(expected_prefix):
        raise ValueError(
            f"Filename must start with category prefix '{expected_prefix}': {filename}"
        )

    name_without_ext = name_without_ext[len(expected_prefix) :]

    # Find the last underscore to check if there's an ID
    last_underscore = name_without_ext.rfind("_")
    if last_underscore == -1:
        # No underscore, entire thing is the name
        return models.LibraryFileInfo(
            category=category, name=name_without_ext, id=None, filename=filename
        )

    # Check if the part after the last underscore is an integer
    potential_id = name_without_ext[last_underscore + 1 :]
    try:
        file_id = int(potential_id)  # Convert to integer
        # It's an integer, so it's the ID
        name = name_without_ext[:last_underscore]
    except ValueError:
        # Not an integer, so the whole thing is the name
        name = name_without_ext
        file_id = None

    return models.LibraryFileInfo(
        category=category, name=name, id=file_id, filename=filename
    )
