"""Shared LLM management utilities for different model providers."""

import os
import typing

from langchain_core import language_models, messages
from langchain_google_genai import chat_models as google_chat_models
from langchain_openai import chat_models as openai_llms

# All technically supported models in order of decreasing speed
_ALL_SUPPORTED_MODELS: list[str] = [
    "gemini-2.5-flash-lite",  # Fastest
    "gemini-2.5-flash",
    "gpt-5-nano",
    "gpt-5-mini",
    "gemini-2.5-pro",
    "gemini-3-pro-preview",  # Slowest
]

# Cache for available models from environment
_available_models_cache: set[str] | None = None


def get_available_models() -> list[str]:
    """Get sorted list of available model IDs from environment variable.

    Reads from ISTAROTH_AVAILABLE_MODELS environment variable.

    Special values:
    - "all": Enable all supported models

    Otherwise expects a comma-separated list of model IDs.
    """
    global _available_models_cache

    if _available_models_cache is not None:
        return sorted(_available_models_cache)

    models_env = os.environ.get("ISTAROTH_AVAILABLE_MODELS")
    if not models_env:
        raise ValueError(
            "ISTAROTH_AVAILABLE_MODELS environment variable is required. "
            "Set it to 'all' or a comma-separated list of model IDs, e.g., "
            "'gemini-2.5-flash-lite,gemini-2.5-flash,gpt-5-mini'"
        )

    # Check for special value
    if models_env.strip().lower() == "all":
        return _ALL_SUPPORTED_MODELS.copy()

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

    _available_models_cache = requested_models
    # Return in speed order (preserve order from _ALL_SUPPORTED_MODELS)
    return [
        model for model in _ALL_SUPPORTED_MODELS if model in _available_models_cache
    ]


def create_llm(model_name: str, **kwargs) -> language_models.BaseLanguageModel:
    """Create LLM instance for the specified model name."""
    available_models = get_available_models()

    if model_name not in available_models:
        raise ValueError(
            f"Model '{model_name}' is not available. Available models: {', '.join(available_models)}"
        )

    # Google models
    if model_name.startswith("gemini-"):
        return google_chat_models.ChatGoogleGenerativeAI(model=model_name, **kwargs)
    # OpenAI models
    elif model_name.startswith("gpt-"):
        return openai_llms.ChatOpenAI(model=model_name, **kwargs)
    else:
        raise ValueError(f"Unknown model provider for '{model_name}'.")


class LLMManager:
    """Manager for multiple LLM instances with lazy loading and caching."""

    def __init__(self, default_model: str | None = None):
        """Initialize LLM manager with empty cache."""
        self._llm_cache: dict[str, language_models.BaseLanguageModel] = {}
        self._default_model = typing.cast(
            str,
            default_model
            or os.environ.get("ISTAROTH_PIPELINE_MODEL", "gemini-2.5-flash-lite"),
        )

    def get_default_llm(self, **kwargs) -> language_models.BaseLanguageModel:
        """Get default LLM instance based on environment variable."""
        return self.get_llm(self._default_model, **kwargs)

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
