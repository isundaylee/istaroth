"""LLM-based on-the-fly proper-noun extraction from text content."""

import collections
import hashlib
import logging
import os
import threading
import time

from langchain_core import language_models, messages

from istaroth import llm_manager, otel_utils

logger = logging.getLogger(__name__)


class CharBudgetExceededError(Exception):
    """Raised when the daily character budget for LLM extraction is exhausted."""


_DAY_SECONDS = 86400


class _RollingCharBudget:
    """Per-process rolling-window cap on characters sent to the LLM.

    Guards against runaway cost: the window resets once its duration elapses, and
    once breached callers fall back to the static list. Per-process (like the
    cache), so multiple replicas multiply it.
    """

    def __init__(self, limit: int, *, window_seconds: float) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._window_start = 0.0
        self._window_chars = 0

    @property
    def limit(self) -> int:
        return self._limit

    def try_consume(self, n: int) -> bool:
        """Reserve ``n`` characters in the current window; False if over budget."""
        now = time.monotonic()
        with self._lock:
            if now - self._window_start >= self._window_seconds:
                self._window_start = now
                self._window_chars = 0
            if self._window_chars + n > self._limit:
                return False
            self._window_chars += n
            return True


_char_budget = _RollingCharBudget(
    int(os.environ.get("ISTAROTH_PROPER_NOUN_CHAR_BUDGET_PER_DAY", "1000000")),
    window_seconds=_DAY_SECONDS,
)


SYSTEM_PROMPT = """\
你是一个专门从文本中提取专有名词的工具。请从给定文本中提取所有专有名词，包括：
- 人名（角色、历史人物、神明等）
- 地名（城市、区域、遗迹、自然地标等）
- 组织名（骑士团、教会、势力等）
- 特殊物品名（武器、圣遗物、书名等）
- 种族/物种名
- 事件名（战争、仪式等）
- 头衔/称号

规则：
- 每行输出一个专有名词，不要编号
- 只输出原文中出现的原始文本，不要翻译或解释
- 不要输出普通名词或形容词
- 不要输出任何说明文字"""

# Bound the in-process cache so a long-lived backend doesn't grow unbounded; the
# corpus is static per deployment, so a hot page costs the LLM call only once.
_CACHE_MAX_SIZE = 512
_cache: collections.OrderedDict[str, list[str]] = collections.OrderedDict()


async def extract_proper_nouns(
    content: str, *, llm: language_models.BaseLanguageModel
) -> list[str]:
    """Extract proper nouns from text content using the given LLM."""
    prompt_messages = [
        messages.SystemMessage(content=SYSTEM_PROMPT),
        messages.HumanMessage(content=content),
    ]
    with otel_utils.llm_span(
        "extract_proper_nouns", llm=llm, prompt=prompt_messages
    ) as gen_span:
        response = gen_span.record_response(await llm.ainvoke(prompt_messages))
    raw = llm_manager.extract_text_from_response(response)
    return [line.strip() for line in raw.strip().splitlines() if line.strip()]


async def extract_proper_nouns_cached(
    content: str, *, llm: language_models.BaseLanguageModel
) -> list[str]:
    """Extract proper nouns, caching the raw LLM output by content hash.

    Cache hits are free; a cache miss consumes the daily character budget and
    raises ``CharBudgetExceededError`` when it would be exceeded.
    """
    key = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if (cached := _cache.get(key)) is not None:
        _cache.move_to_end(key)
        return cached
    if not _char_budget.try_consume(len(content)):
        raise CharBudgetExceededError(
            f"Daily proper-noun extraction budget of {_char_budget.limit} "
            "characters exceeded"
        )
    result = await extract_proper_nouns(content, llm=llm)
    _cache[key] = result
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX_SIZE:
        _cache.popitem(last=False)
    return result
