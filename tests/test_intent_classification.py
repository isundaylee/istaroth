"""Opt-in integration tests for LLM query-intent classification.

These call a real model and therefore cost tokens, so they are OPT-IN via the
``llm`` marker: they only run with ``--run-llm`` (and require the usual model env
— ``ISTAROTH_AVAILABLE_MODELS`` plus the provider key). They guard the
``question_preprocess_prompt`` intent classification that drives adaptive
retrieval budget (``budget.allocate``): in particular that low-context-need
queries (names, definitions, enumerations, broad histories) route to ``variety``
(breadth, small context window) rather than ``context`` (few sources, deep
context), and that genuine single-scene narrative queries still keep a
non-minimal context window.

Run with: ``uv run pytest --run-llm tests/test_intent_classification.py``

These go through the real ``pipeline.preprocess_question`` (same prompt, schema,
parsing and fallback the production pipeline uses) for fidelity. LLM output is
not perfectly deterministic even at temperature 0; treat these as high-signal
smoke checks rather than hard guarantees.
"""

import pytest

from istaroth import llm_manager
from istaroth.agd import localization
from istaroth.rag import budget, pipeline, prompt_set

pytestmark = pytest.mark.llm

_MODEL = "gemini-3.1-flash-lite-preview"


def _classify(query: str, language: localization.Language) -> budget.QueryIntent:
    _, intent = pipeline.preprocess_question(
        query,
        rag_prompts=prompt_set.get_rag_prompts(language),
        preprocessing_llm=llm_manager.LLMManager().get_llm(_MODEL, temperature=0),
    )
    return intent


_LOW_CONTEXT_QUERIES = [
    (localization.Language.CHS, "卡特的全名叫什么？"),  # name lookup
    (localization.Language.CHS, "神之眼代表着什么？"),  # definition / multi-aspect
    (localization.Language.CHS, "提瓦特的七位执政官分别是谁？"),  # enumeration
    (localization.Language.CHS, "钟离的真实身份是什么？"),  # single fact
    (localization.Language.CHS, "坎瑞亚灾变的历史"),  # broad history across sources
    (localization.Language.ENG, "What is Carter's full name?"),
    (localization.Language.ENG, "Who are the seven Archons of Teyvat?"),
]

_NARRATIVE_SCENE_QUERIES = [
    (localization.Language.CHS, "在送仙典仪上，钟离与旅行者之间发生了怎样的对话？"),
    (localization.Language.CHS, "「螭骨剑」任务里魈经历了怎样的一段剧情？"),
]


@pytest.mark.parametrize(
    "language,query", _LOW_CONTEXT_QUERIES, ids=lambda v: getattr(v, "value", v)
)
def test_low_context_queries_route_to_variety(
    language: localization.Language, query: str
) -> None:
    """Factoid / enumeration / broad-history queries should prefer breadth."""
    assert _classify(query, language) is budget.QueryIntent.VARIETY


@pytest.mark.parametrize(
    "language,query", _NARRATIVE_SCENE_QUERIES, ids=lambda v: getattr(v, "value", v)
)
def test_narrative_scene_queries_keep_context_window(
    language: localization.Language, query: str
) -> None:
    """A single continuous-scene query should keep a non-minimal context window."""
    intent = _classify(query, language)
    _, chunk_context = budget.allocate(110, intent)
    assert intent is not budget.QueryIntent.VARIETY
    assert chunk_context > 1
