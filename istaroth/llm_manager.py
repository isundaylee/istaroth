"""Shared LLM management utilities for different model providers."""

import os
import typing

from langchain_core import language_models, messages
from langchain_google_genai import chat_models as google_chat_models
from langchain_openai import chat_models as openai_llms

# Default model when ISTAROTH_PIPELINE_MODEL is unset
_DEFAULT_PIPELINE_MODEL = "gemini-3.1-flash-lite-preview"

# All technically supported models in order of decreasing speed
_ALL_SUPPORTED_MODELS: list[str] = [
    "gemini-3.1-flash-lite-preview",  # Fastest
    "gemini-3-flash-preview",
    "gpt-5-nano",
    "gpt-5-mini",
    "gemini-3.1-pro-preview",  # Slowest
]

# Base models exposed as one selectable variant per thinking level, mapped to
# their offered levels in order of increasing reasoning depth (and latency).
# Models absent here still think, but use the provider default and aren't expanded.
_GEMINI_THINKING_LEVEL_EXPANDED_MODELS: dict[str, list[str]] = {
    "gemini-3-flash-preview": ["minimal", "high"],
}

# Cache for the expanded, speed-ordered available models from environment
_available_models_cache: list[str] | None = None


def _expand_models(base_models: list[str]) -> list[str]:
    """Expand level-expanded base models into one variant per thinking level."""
    expanded: list[str] = []
    for model in base_models:
        if levels := _GEMINI_THINKING_LEVEL_EXPANDED_MODELS.get(model):
            expanded.extend(f"{model}:{level}" for level in levels)
        else:
            expanded.append(model)
    return expanded


def get_available_models() -> list[str]:
    """Get sorted list of available model IDs from environment variable.

    Reads from ISTAROTH_AVAILABLE_MODELS environment variable.

    Special values:
    - "all": Enable all supported models

    Otherwise expects a comma-separated list of model IDs.
    """
    global _available_models_cache

    if _available_models_cache is not None:
        return _available_models_cache

    models_env = os.environ.get("ISTAROTH_AVAILABLE_MODELS")
    if not models_env:
        raise ValueError(
            "ISTAROTH_AVAILABLE_MODELS environment variable is required. "
            "Set it to 'all' or a comma-separated list of model IDs, e.g., "
            "'gemini-3.1-flash-lite-preview,gemini-3-flash-preview,gpt-5-mini'"
        )

    # Check for special value
    if models_env.strip().lower() == "all":
        _available_models_cache = _expand_models(_ALL_SUPPORTED_MODELS)
        return _available_models_cache

    # Parse comma-separated list
    requested_models = {m.strip() for m in models_env.split(",") if m.strip()}

    if not requested_models:
        raise ValueError("ISTAROTH_AVAILABLE_MODELS cannot be empty")

    # Validate that all requested models are supported
    unsupported = requested_models - set(_ALL_SUPPORTED_MODELS)
    if unsupported:
        raise ValueError(
            f"Unsupported models in ISTAROTH_AVAILABLE_MODELS: {', '.join(sorted(unsupported))}. "
            f"Supported models are: {', '.join(_ALL_SUPPORTED_MODELS)}"
        )

    # Cache in speed order (preserve order from _ALL_SUPPORTED_MODELS), expanded
    _available_models_cache = _expand_models(
        [model for model in _ALL_SUPPORTED_MODELS if model in requested_models]
    )
    return _available_models_cache


def get_default_model() -> str:
    """Get the model ID to pre-select in the UI, from ISTAROTH_PIPELINE_MODEL.

    Falls back to the fastest available model when the configured default is not
    among the available models.
    """
    available_models = get_available_models()
    default = os.environ.get("ISTAROTH_PIPELINE_MODEL", _DEFAULT_PIPELINE_MODEL)
    return default if default in available_models else available_models[0]


def create_llm(model_name: str, **kwargs) -> language_models.BaseLanguageModel:
    """Create LLM instance for the specified model name."""
    available_models = get_available_models()

    if model_name not in available_models:
        raise ValueError(
            f"Model '{model_name}' is not available. Available models: {', '.join(available_models)}"
        )

    implied_kwargs: dict[str, typing.Any] = {"max_retries": 1}

    # Split off an optional ":<thinking-level>" suffix (e.g. gemini-3-flash-preview:low)
    base_model, _, thinking_level = model_name.partition(":")

    # Google models
    if base_model.startswith("gemini-"):
        if thinking_level and base_model in _GEMINI_THINKING_LEVEL_EXPANDED_MODELS:
            implied_kwargs["thinking_level"] = thinking_level
        return google_chat_models.ChatGoogleGenerativeAI(
            model=base_model, **implied_kwargs, **kwargs
        )
    # OpenAI models
    elif base_model.startswith("gpt-"):
        return openai_llms.ChatOpenAI(model=base_model, **implied_kwargs, **kwargs)
    else:
        raise ValueError(f"Unknown model provider for '{model_name}'.")


class LLMManager:
    """Manager for multiple LLM instances with lazy loading and caching."""

    def __init__(self):
        """Initialize LLM manager with empty cache."""
        self._llm_cache: dict[str, language_models.BaseLanguageModel] = {}

    def get_default_llm(self, **kwargs) -> language_models.BaseLanguageModel:
        """Get default LLM instance based on environment variable."""
        return self.get_llm(get_default_model(), **kwargs)

    def get_llm(self, model_name: str, **kwargs) -> language_models.BaseLanguageModel:
        """Get LLM instance for the specified model, with caching."""
        # Create cache key that includes kwargs for proper caching
        cache_key = f"{model_name}:{hash(tuple(sorted(kwargs.items())))}"

        if cache_key not in self._llm_cache:
            self._llm_cache[cache_key] = create_llm(model_name, **kwargs)

        return self._llm_cache[cache_key]


def extract_text_from_response(response: typing.Any) -> str:
    """Extract text content from various LLM response types."""
    if isinstance(response, messages.AIMessage):
        content = response.content
        # Handle Gemini 3 format: list of dicts with 'text' keys
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
                else:
                    text_parts.append(str(item))
            return "\n\n".join(text_parts)
        return str(content)
    elif isinstance(response, str):
        return response
    else:
        return str(response)


def get_model_name(llm: language_models.BaseLanguageModel) -> str:
    """Extract model name from LLM instance."""
    return getattr(llm, "model_name", str(type(llm).__name__))
