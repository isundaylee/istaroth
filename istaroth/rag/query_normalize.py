"""Query normalization for typo/homophone/traditional-simplified correction.

Unlike :mod:`istaroth.rag.query_transform` (semantic multi-query *rewriting*
inside hybrid retrieval), normalization is a strict 1:1 surface-form correction:
one query in, one corrected query out, no additional queries produced. It runs as
the first node in the RAG pipeline graph, *before* decomposition, so the
decomposer and both retrieval backends (BM25 + vector) see corrected text.
"""

import logging
import os
import typing
from abc import ABC, abstractmethod

import attrs
import pypinyin
from langchain_core import language_models
from langchain_google_genai import llms as google_llms

logger = logging.getLogger(__name__)

# A vocabulary term is a candidate if it shares at least this many tone-less
# pinyin syllables with the query. ≥2 keeps recall for typo/homophone names
# (桑多捏→桑多涅 shares {sang, duo, nie}) while excluding the thousands of terms
# that merely share a single common syllable (的→de, 是→shi) with the query.
_PHONETIC_MATCH_MIN_SYLLABLES = 2


def _phonetic_signature(text: str) -> frozenset[str]:
    """Set of all tone-less pinyin readings (incl. heteronyms) across ``text``."""
    syllables: set[str] = set()
    for char_readings in pypinyin.pinyin(
        text, style=pypinyin.Style.NORMAL, heteronym=True
    ):
        syllables.update(char_readings)
    return frozenset(syllables)


class QueryNormalizer(ABC):
    """Abstract base class for query normalizers (strict 1:1 correction)."""

    @abstractmethod
    def normalize(self, query: str) -> str:
        """Return the surface-corrected form of ``query`` (one in, one out).

        If no correction applies the original query is returned unchanged.
        """

    @classmethod
    def from_env(cls, *, vocabulary: tuple[str, ...] = ()) -> "QueryNormalizer":
        """Select a normalizer via the ``ISTAROTH_QUERY_NORMALIZER`` env var.

        - ``identity`` (default): no-op normalizer.
        - ``llm``: LLM-driven typo/homophone/trad-simp correction, grounded
          in ``vocabulary`` (the canon proper-noun list) so corrections target
          real Genshin names.

        Args:
            vocabulary: Canon proper nouns to inject into the LLM prompt as a
                reference; ignored by ``identity``.
        """
        match (nv := os.environ.get("ISTAROTH_QUERY_NORMALIZER", "identity")):
            case "identity":
                return IdentityNormalizer()
            case "llm":
                return LLMQueryNormalizer.create(vocabulary=vocabulary)
            case _:
                raise ValueError(f"Unknown ISTAROTH_QUERY_NORMALIZER: {nv}")


class IdentityNormalizer(QueryNormalizer):
    """No-op normalizer returning the query unchanged."""

    def normalize(self, query: str) -> str:
        """Return ``query`` unchanged."""
        return query


@attrs.define
class LLMQueryNormalizer(QueryNormalizer):
    """LLM-driven normalizer for typo/homophone/trad-simp correction."""

    _PROMPT_TEMPLATE: typing.ClassVar[
        str
    ] = """\
你是《原神》知识检索系统的查询规范化工具。请对用户输入的检索查询进行表面形式纠错，输出恰好一行纠正后的查询。
{vocabulary_section}\
需要纠正的错误类型：
- 中文错别字或同音字误用（如"钟梨"→"钟离"，"温迪尔"→"温迪"）
- 繁体字转简体（如"鍾離"→"钟离"）
- 英文拼写错误（如"Zhongil"→"Zhongli"，"Raidnen"→"Raiden"）
- 全角/半角混用、多余空格、标点规范化

严格要求：
- 不得改变查询的语义和意图
- 不得改写、扩写、翻译或分解查询
- 不得增删实质信息内容
- 如果查询已经正确，原样输出
- 只输出纠正后的查询本身，不要解释、编号或任何多余文字
- 必须只输出一行

查询：{query}
纠正结果："""

    _llm: language_models.BaseLLM = attrs.field()
    _vocabulary: tuple[str, ...] = attrs.field(default=())
    # Precomputed (term, pinyin-signature) pairs; built once in __attrs_post_init__.
    _vocab_signatures: list[tuple[str, frozenset[str]]] = attrs.field(
        init=False, factory=list
    )

    def __attrs_post_init__(self) -> None:
        self._vocab_signatures = [
            (term, _phonetic_signature(term)) for term in self._vocabulary
        ]

    @classmethod
    def create(
        cls,
        *,
        model: str = "gemini-3.1-flash-lite-preview",
        vocabulary: tuple[str, ...] = (),
    ) -> "LLMQueryNormalizer":
        """Create an LLM-backed normalizer using a cheap Gemini model."""
        return cls(google_llms.GoogleGenerativeAI(model=model), vocabulary=vocabulary)

    def _candidate_vocabulary(self, query: str) -> list[str]:
        """Vocabulary terms sharing ≥2 pinyin syllables with ``query``."""
        query_sig = _phonetic_signature(query)
        if len(query_sig) < _PHONETIC_MATCH_MIN_SYLLABLES:
            return []
        return [
            term
            for term, term_sig in self._vocab_signatures
            if len(term_sig & query_sig) >= _PHONETIC_MATCH_MIN_SYLLABLES
        ]

    def normalize(self, query: str) -> str:
        """Return the LLM-corrected form of ``query``.

        Falls back to the original query on any error or if the model violates
        the one-line contract.
        """
        if not query.strip():
            return query

        candidates = self._candidate_vocabulary(query)
        vocabulary_section = (
            "以下是《原神》中专有名词的参考列表，纠正时应优先匹配其中的条目：\n"
            + "\n".join(candidates)
            + "\n"
            if candidates
            else ""
        )
        prompt = self._PROMPT_TEMPLATE.format(
            query=query, vocabulary_section=vocabulary_section
        )
        try:
            response = self._llm.invoke(prompt)
        except Exception as e:
            logger.warning("Failed to normalize query %r: %s", query, e)
            return query

        lines = [ln.strip() for ln in response.strip().splitlines() if ln.strip()]
        if len(lines) != 1:
            logger.warning(
                "Normalizer returned %d lines for %r; keeping original",
                len(lines),
                query,
            )
            return query
        return lines[0]
