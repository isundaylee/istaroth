"""Classify common LLM/provider API failures into user-facing messages."""

from __future__ import annotations

import dataclasses
import typing

import openai
from google.genai import errors as google_genai_errors

LLM_ERROR_RATE_LIMIT = "rate_limit"
LLM_ERROR_OVERLOADED = "overloaded"
LLM_ERROR_TIMEOUT = "timeout"

_USER_MESSAGES: dict[str, str] = {
    LLM_ERROR_RATE_LIMIT: (
        "The AI model is temporarily rate-limited. Please try again in a moment."
    ),
    LLM_ERROR_OVERLOADED: (
        "The AI model is experiencing high demand. Please try again shortly."
    ),
    LLM_ERROR_TIMEOUT: (
        "The request timed out while waiting for the AI model. Please try again."
    ),
}

_HTTP_STATUS_BY_CODE: dict[str, int] = {
    LLM_ERROR_RATE_LIMIT: 429,
    LLM_ERROR_OVERLOADED: 503,
    LLM_ERROR_TIMEOUT: 504,
}


@dataclasses.dataclass(frozen=True)
class LLMUserError:
    """A classified LLM failure suitable for API responses."""

    code: str
    message: str
    http_status: int


def iter_exception_chain(exc: BaseException) -> typing.Iterator[BaseException]:
    """Yield *exc* and linked causes/contexts without cycles."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def classify_llm_error(exc: BaseException) -> LLMUserError | None:
    """Return a user-facing error when *exc* looks like a known LLM API failure."""
    for error in iter_exception_chain(exc):
        classified = _classify_single(error)
        if classified is not None:
            return classified
    return None


def _classify_single(exc: BaseException) -> LLMUserError | None:
    if isinstance(exc, openai.RateLimitError):
        return _make(LLM_ERROR_RATE_LIMIT)

    if isinstance(exc, openai.APITimeoutError):
        return _make(LLM_ERROR_TIMEOUT)

    if isinstance(exc, openai.APIStatusError):
        return _classify_http_status(exc.status_code)

    if isinstance(exc, google_genai_errors.APIError):
        return _classify_http_status(exc.code)

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return _classify_http_status(status_code)

    return None


def _classify_http_status(status_code: int) -> LLMUserError | None:
    if status_code == 429:
        return _make(LLM_ERROR_RATE_LIMIT)
    if status_code == 503:
        return _make(LLM_ERROR_OVERLOADED)
    if status_code == 504:
        return _make(LLM_ERROR_TIMEOUT)
    return None


def _make(code: str) -> LLMUserError:
    return LLMUserError(
        code=code,
        message=_USER_MESSAGES[code],
        http_status=_HTTP_STATUS_BY_CODE[code],
    )
