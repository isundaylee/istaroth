"""Tests for query normalization."""

from istaroth.rag import query_normalize


class _FakeLLM:
    """Minimal stand-in for a LangChain LLM yielding canned invoke() output."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str | None = None

    def invoke(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


def test_llm_normalizer_filters_vocabulary_by_phonetic_match():
    fake = _FakeLLM("钟离")
    normalizer = query_normalize.LLMQueryNormalizer(
        fake,  # type: ignore[arg-type]
        vocabulary=("钟离", "摩拉克斯"),
    )
    normalizer.normalize("钟梨")
    assert fake.last_prompt is not None
    assert "钟离" in fake.last_prompt
    assert "摩拉克斯" not in fake.last_prompt
