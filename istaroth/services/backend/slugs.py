"""Slug generation utilities for short URLs."""

import secrets
import string

_ALPHABET = string.ascii_letters + string.digits


def generate_slug(*, length: int = 8) -> str:
    """Generate a random alphanumeric slug."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
