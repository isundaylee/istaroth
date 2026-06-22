"""Tests for LLM provider selection."""

import pytest
from langchain_openai import chat_models as openai_llms

from istaroth import llm_manager


def _reset_available_models_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_manager, "_available_models_cache", None)


def test_deepinfra_models_are_available_under_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_available_models_cache(monkeypatch)
    monkeypatch.setenv("ISTAROTH_AVAILABLE_MODELS", "all")

    assert llm_manager.get_available_models()[:3] == [
        "gemini-3.1-flash-lite-preview",
        "zai-org/GLM-4.7-Flash",
        "deepseek-ai/DeepSeek-V4-Flash",
    ]


@pytest.mark.parametrize(
    "model",
    ["zai-org/GLM-4.7-Flash", "deepseek-ai/DeepSeek-V4-Flash"],
)
def test_deepinfra_models_use_openai_compatible_endpoint(
    model: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_available_models_cache(monkeypatch)
    monkeypatch.setenv("ISTAROTH_AVAILABLE_MODELS", model)
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")

    llm = llm_manager.create_llm(model)

    assert isinstance(llm, openai_llms.ChatOpenAI)
    assert llm.model_name == model
    assert llm.openai_api_base == "https://api.deepinfra.com/v1/openai"
    assert llm.max_retries == 1
