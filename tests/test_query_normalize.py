"""Tests for query normalization."""

import pytest

from istaroth.rag import query_normalize


class _FakeLLM:
    """Minimal stand-in for a LangChain LLM yielding canned invoke() output."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str | None = None

    def invoke(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


@pytest.mark.parametrize(
    "original,candidate,expected",
    [
        # Genuine same-length homophone corrections (tone may differ).
        ("钟梨", "钟离", True),
        ("桑多捏", "桑多涅", True),
        ("鍾離", "钟离", True),  # traditional -> simplified, same reading
        ("钟离", "钟离", True),  # unchanged
        ("钟梨是谁", "钟离是谁", True),  # corrected term embedded in a longer query
        # #240: substituting an unrelated proper noun that only shares some
        # syllables must be rejected (different length-aligned readings).
        ("山中好长日", "长日一灯明", False),
        ("山中好长日", "山中长日明", False),  # reordered, not a per-position homophone
        ("钟离", "钟离的身份", False),  # length change
    ],
)
def test_is_homophone_rewrite(original: str, candidate: str, expected: bool) -> None:
    assert query_normalize._is_homophone_rewrite(original, candidate) is expected


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


# Faithful slice of the deployed candidate set for the queries below: the
# registered furnishing 「长日一灯明」 and the correction targets 婕德/桑多涅, plus
# other 山中/长 terms that legitimately share ≥2 pinyin syllables. The quest title
# 山中好长日 is deliberately absent (as in prod) — a valid query need not be listed.
_NORMALIZER_VOCABULARY = (
    "「长日一灯明」",
    "山中人氏",
    "山中国度",
    "山中老叟",
    "山中部民",
    "长野原",
    "长风",
    "长正",
    "婕德",
    "婕德·塔尼特",
    "桑多涅",
    "钟离",
)


@pytest.mark.llm
@pytest.mark.parametrize(
    "query,expected",
    [
        # #240: a valid quest-group title ("A Long Day in the Mountains") must
        # survive even though it is absent from the vocab and shares 长日 with the
        # registered furnishing 「长日一灯明」 — it must NOT be substituted for it.
        ("山中好长日", "山中好长日"),
        # Genuine character-level corrections (typo / near-homophone) must still
        # resolve to the canonical registered spelling.
        ("捷德", "婕德"),
        ("桑多捏", "桑多涅"),
        # Same corrections when the misspelled term is only part of a longer
        # query, not the whole query — the rest of the sentence is untouched.
        ("捷德是谁", "婕德是谁"),
        ("桑多捏的故事讲了什么", "桑多涅的故事讲了什么"),
    ],
)
def test_llm_normalizer_corrects_typos_without_substituting_entities(
    query: str, expected: str
) -> None:
    """The normalizer fixes wrong characters but never swaps in a different entity.

    Calls a real model (opt-in via ``--run-llm``); see #240 for the over-correction
    bug this guards against.
    """
    normalizer = query_normalize.LLMQueryNormalizer.create(
        vocabulary=_NORMALIZER_VOCABULARY
    )
    assert normalizer.normalize(query) == expected
