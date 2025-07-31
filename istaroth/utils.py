"""Utility functions for type checking and assertions."""

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
