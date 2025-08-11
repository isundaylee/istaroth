"""Utility functions for type checking and assertions."""

import contextlib
import logging
import re
import time
import typing

T = typing.TypeVar("T")


def assert_is_instance(obj: object, cls: type[T]) -> T:
    """Assert object is instance of class with proper typing."""
    assert isinstance(obj, cls), f"Expected {cls.__name__}, got {type(obj).__name__}"
    return obj


def assert_not_none(obj: T | None) -> T:
    """Assert object is not None and return it with proper typing."""
    assert obj is not None, "Expected non-None value"
    return obj


def make_safe_filename_part(text: str, *, max_length: int = 50) -> str:
    """Convert text to a safe filename part by removing special chars and normalizing spaces."""
    # Remove special characters, keeping only word chars, spaces, and hyphens
    safe_text = re.sub(r"[^\w\s-]", "", text[:max_length])
    # Replace multiple spaces with single underscore
    safe_text = re.sub(r"\s+", "_", safe_text.strip())
    return safe_text


logger = logging.getLogger(__name__)


@contextlib.contextmanager
def timer(operation_name: str) -> typing.Iterator[None]:
    """Context manager for timing operations with automatic logging."""
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time
        logger.log(
            logging.INFO,
            "%s completed in %.2f seconds",
            operation_name.capitalize(),
            elapsed,
        )
