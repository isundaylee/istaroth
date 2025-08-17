"""Shared utilities for FastAPI backend."""

import functools
import logging
from typing import Awaitable, Callable, ParamSpec, TypeVar

from fastapi import HTTPException

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
