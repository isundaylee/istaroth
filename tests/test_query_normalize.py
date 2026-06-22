"""Tests for query normalization."""

import pytest

from istaroth.rag import query_normalize


class _FakeLLM:
    """Minimal stand-in for a LangChain LLM yielding canned invoke() output."""

    def __init__(self, response: str, raises: Exception | None = None) -> None:
        self._response = response
        self._raises = raises
        self.last_prompt: str | None = None

    def invoke(self, prompt: str) -> str:
        if self._raises is not None:
            raise self._raises
        self.last_prompt = prompt
        return self._response


def test_identity_normalizer_returns_input_unchanged():
    normalizer = query_normalize.IdentityNormalizer()
    assert normalizer.normalize("钟梨") == "钟梨"
    assert normalizer.normalize("anything") == "anything"


def test_llm_normalizer_corrects_single_line():
    normalizer = query_normalize.LLMQueryNormalizer(
        _FakeLLM("钟离")  # type: ignore[arg-type]
    )
    assert normalizer.normalize("钟梨") == "钟离"


def test_llm_normalizer_passes_through_already_correct():
    normalizer = query_normalize.LLMQueryNormalizer(
        _FakeLLM("钟离")  # type: ignore[arg-type]
    )
    assert normalizer.normalize("钟离") == "钟离"


def test_llm_normalizer_keeps_original_on_multiline_output():
    normalizer = query_normalize.LLMQueryNormalizer(
        _FakeLLM("钟离\n摩拉克斯")  # type: ignore[arg-type]
    )
    assert normalizer.normalize("钟梨") == "钟梨"


def test_llm_normalizer_keeps_original_on_empty_output():
    normalizer = query_normalize.LLMQueryNormalizer(
        _FakeLLM("   ")  # type: ignore[arg-type]
    )
    assert normalizer.normalize("钟梨") == "钟梨"


def test_llm_normalizer_keeps_original_on_llm_error():
    normalizer = query_normalize.LLMQueryNormalizer(
        _FakeLLM("", raises=RuntimeError("api down"))  # type: ignore[arg-type]
    )
    assert normalizer.normalize("钟梨") == "钟梨"


def test_llm_normalizer_passes_through_blank_query():
    normalizer = query_normalize.LLMQueryNormalizer(
        _FakeLLM("should not be called")  # type: ignore[arg-type]
    )
    assert normalizer.normalize("") == ""
    assert normalizer.normalize("   ") == "   "


def test_llm_normalizer_injects_phonetically_matching_candidates():
    fake = _FakeLLM("钟离")
    normalizer = query_normalize.LLMQueryNormalizer(
        fake,  # type: ignore[arg-type]
        vocabulary=("钟离", "摩拉克斯"),
    )
    normalizer.normalize("钟梨")
    assert fake.last_prompt is not None
    # 钟离 shares {zhong, li} (>=2 syllables) with 钟梨 -> included
    assert "钟离" in fake.last_prompt
    # 摩拉克斯 shares no syllable with 钟梨 -> filtered out
    assert "摩拉克斯" not in fake.last_prompt


def test_llm_normalizer_omits_vocabulary_section_when_empty():
    fake = _FakeLLM("钟离")
    normalizer = query_normalize.LLMQueryNormalizer(fake)  # type: ignore[arg-type]
    normalizer.normalize("钟梨")
    assert fake.last_prompt is not None
    assert "参考列表" not in fake.last_prompt


def test_llm_normalizer_omits_vocabulary_section_when_no_phonetic_match():
    fake = _FakeLLM("钟离")
    normalizer = query_normalize.LLMQueryNormalizer(
        fake,  # type: ignore[arg-type]
        vocabulary=("摩拉克斯",),  # no phonetic overlap with 钟梨
    )
    normalizer.normalize("钟梨")
    assert fake.last_prompt is not None
    assert "参考列表" not in fake.last_prompt


def test_from_env_defaults_to_identity(monkeypatch):
    monkeypatch.delenv("ISTAROTH_QUERY_NORMALIZER", raising=False)
    assert isinstance(
        query_normalize.QueryNormalizer.from_env(), query_normalize.IdentityNormalizer
    )


def test_from_env_identity_explicit(monkeypatch):
    monkeypatch.setenv("ISTAROTH_QUERY_NORMALIZER", "identity")
    assert isinstance(
        query_normalize.QueryNormalizer.from_env(), query_normalize.IdentityNormalizer
    )


def test_from_env_llm(monkeypatch):
    monkeypatch.setenv("ISTAROTH_QUERY_NORMALIZER", "llm")
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-key-for-construction")
    assert isinstance(
        query_normalize.QueryNormalizer.from_env(), query_normalize.LLMQueryNormalizer
    )


def test_from_env_unknown_raises(monkeypatch):
    monkeypatch.setenv("ISTAROTH_QUERY_NORMALIZER", "bogus")
    with pytest.raises(ValueError, match="Unknown ISTAROTH_QUERY_NORMALIZER"):
        query_normalize.QueryNormalizer.from_env()
