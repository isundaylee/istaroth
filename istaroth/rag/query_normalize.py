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
你是《原神》知识检索系统的查询规范化工具。你只做一件事：同音字纠错——把查询里读音正确但写错的字，改成《原神》中的标准写法，输出恰好一行结果。
{vocabulary_section}\
严格限制：
- 纠正后的查询字数必须与原查询完全相同，且第 i 个字必须与原查询第 i 个字读音相同（允许仅声调不同）；输出前请逐字核对读音，只要有一个字读音对不上，就不要那样改
- 你只能逐字替换写错的同音字（繁体转简体读音不变，也算同音纠错）；不得增字、删字、重排，不得改写、扩写、翻译或分解
- 读音不同就一定是不同的词：绝不能因为查询与参考列表中的某个名词意思相近、或有部分相同的字，就替换成那个名词
- 如果查询读音上已无错字，即使它不在参考列表中，也必须原样输出
- 拿不准时一律保持原样，宁可不改也不要改错
- 只输出纠正后的查询本身，必须只有一行，不要解释、编号或任何多余文字

示例：
查询：钟梨
纠正结果：钟离
查询：那西妲
纠正结果：纳西妲

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
        model: str = "gemini-3-flash-preview",
        vocabulary: tuple[str, ...] = (),
    ) -> "LLMQueryNormalizer":
        """Create an LLM-backed normalizer using a Gemini model.

        Uses ``flash`` rather than ``flash-lite``: the lite model does not reliably
        obey the strict same-reading homophone constraint and substitutes a
        phonetically-adjacent proper noun from the vocabulary for a valid query
        (#240, e.g. 山中好长日 → 长日一灯明).
        """
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
            "以下是《原神》中专有名词的标准写法参考，仅用于确认同音错字的正确写法。"
            "只有当查询与某个条目读音相同、只是个别字写错时，才替换成该条目；读音不同"
            "则一律保持原样：\n" + "\n".join(candidates) + "\n"
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
