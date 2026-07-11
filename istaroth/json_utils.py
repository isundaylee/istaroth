"""JSON helpers: msgspec-backed decode, stdlib dumps matching old orjson output."""

import json
from typing import Any, Callable

import msgspec


def loads(data: bytes | str) -> Any:
    """Deserialize JSON via msgspec (~2x faster than stdlib on AGD-sized files)."""
    return msgspec.json.decode(data)


def dumps(obj: Any, *, default: Callable[[Any], Any] | None = None) -> bytes:
    """Serialize to compact UTF-8 JSON bytes (orjson-compatible separators)."""
    return json.dumps(
        obj, ensure_ascii=False, separators=(",", ":"), default=default
    ).encode()


def dumps_indented(obj: Any, *, default: Callable[[Any], Any] | None = None) -> bytes:
    """Serialize to 2-space-indented UTF-8 JSON bytes."""
    return json.dumps(obj, ensure_ascii=False, indent=2, default=default).encode()
