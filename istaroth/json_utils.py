"""Stdlib-json dump helpers matching the byte-level output of the old orjson usage."""

import json
from typing import Any, Callable


def dumps(obj: Any, *, default: Callable[[Any], Any] | None = None) -> bytes:
    """Serialize to compact UTF-8 JSON bytes (orjson-compatible separators)."""
    return json.dumps(
        obj, ensure_ascii=False, separators=(",", ":"), default=default
    ).encode()


def dumps_indented(obj: Any, *, default: Callable[[Any], Any] | None = None) -> bytes:
    """Serialize to 2-space-indented UTF-8 JSON bytes."""
    return json.dumps(obj, ensure_ascii=False, indent=2, default=default).encode()
