"""Shared on-the-fly proper-noun extraction for frontend highlighting.

Used by both the library file viewer and the query answer: extract proper nouns
from rendered content via the LLM, filter against the curated negative list, and
keep only terms that literally appear in the content so the frontend trie can
highlight them (guards against LLM paraphrase/hallucination).
"""

import logging

from langchain_core import language_models

from istaroth.rag import text_set
from istaroth.text import proper_noun_extraction, proper_nouns

logger = logging.getLogger(__name__)


async def extract_highlight_nouns(
    content: str,
    *,
    text_set_obj: text_set.TextSet,
    llm: language_models.BaseLanguageModel,
) -> list[str]:
    """Extract highlightable proper nouns from ``content``.

    On a cache miss this consumes the daily extraction budget; once exhausted it
    degrades to the static curated list. Either way only terms present in
    ``content`` are returned, sorted and deduplicated.
    """
    negative_terms = proper_nouns.parse_terms(
        text_set_obj.get_content(
            proper_nouns.PROPER_NOUNS_NEGATIVE_RELATIVE_PATH.as_posix()
        )
    )
    try:
        extracted = await proper_noun_extraction.extract_proper_nouns_cached(
            content, llm=llm
        )
    except proper_noun_extraction.CharBudgetExceededError:
        logger.warning("Proper-noun extraction budget exceeded; serving static list")
        extracted = proper_nouns.parse_terms(
            text_set_obj.get_content(proper_nouns.PROPER_NOUNS_RELATIVE_PATH.as_posix())
        )
    return sorted(
        {
            term
            for term in proper_nouns.filter_terms(extracted, negative_terms)
            if term in content
        }
    )
