"""LLM judge that rescues false-miss facets in the retrieval eval.

The deterministic anchor matcher (``retrieval.py``) reports a facet as missing
whenever no hard-coded passage is a verbatim substring of a retrieved source. That
under-counts: retrieval may surface a *different* valid source that attests the
facet in other words. This judge re-grades only those missing facets — given the
retrieved passages and a short description of each missing facet, a cheap model is
asked whether any passage attests the facet and, if so, to copy the supporting
verbatim span. The caller verifies the span really occurs in the retrieved text
and persists it as a new anchor, so the judge fires once and the fixture
self-hardens.

The model runs on DeepInfra's OpenAI-compatible endpoint (same provider already
used for embeddings); it is deliberately kept out of ``istaroth.llm_manager`` so
the production model registry is not polluted by an eval-only judge.
"""

import os
from collections.abc import Callable

import attrs
import pydantic
from langchain_core import messages
from langchain_openai import chat_models

_DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
DEFAULT_JUDGE_MODEL = "deepseek-ai/DeepSeek-V4-Flash"

_SYSTEM_PROMPT = (
    "You grade retrieval for a Genshin Impact lore QA system. Given a user query, "
    "a numbered list of retrieved passages, and a list of facets (each an aspect a "
    "complete answer should cover), decide for EACH facet whether ANY retrieved "
    "passage actually attests it.\n"
    "Rules:\n"
    "- A passage attests a facet only if its text states the fact, not merely "
    "mentions a related name in passing.\n"
    "- Use ONLY the passage text. Do NOT rely on your own knowledge of Genshin lore.\n"
    "- If attested, copy a SHORT verbatim span (roughly 8-40 characters) DIRECTLY "
    "from the passages — exact characters including punctuation (「」、，。…). Do NOT "
    "paraphrase, translate, summarize, or invent text; the span must appear "
    "character-for-character in the passages.\n"
    "- If no passage attests the facet, return an empty string for its span.\n"
    "- Return exactly one verdict per facet."
)


class _FacetVerdict(pydantic.BaseModel):
    facet: str = pydantic.Field(description="the facet id being judged")
    span: str = pydantic.Field(
        description=(
            "a verbatim substring copied character-for-character from the passages "
            "that attests the facet; empty string if no passage attests it"
        )
    )


class _JudgeOutput(pydantic.BaseModel):
    verdicts: list[_FacetVerdict]


@attrs.frozen
class JudgeUsage:
    """Token usage accumulated across judge calls."""

    calls: int
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "JudgeUsage") -> "JudgeUsage":
        return JudgeUsage(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )

    @classmethod
    def zero(cls) -> "JudgeUsage":
        return cls(calls=0, input_tokens=0, output_tokens=0)


def _build_user_message(
    query: str, ranked_texts: list[str], facets: dict[str, str]
) -> str:
    facet_block = "\n".join(f"- {facet}: {desc}" for facet, desc in facets.items())
    passage_block = "\n\n".join(
        f"[{i}] {text}" for i, text in enumerate(ranked_texts, start=1)
    )
    return (
        f"User query:\n{query}\n\n"
        f"Facets to judge:\n{facet_block}\n\n"
        f"Retrieved passages:\n{passage_block}"
    )


def make_judge(
    model: str = DEFAULT_JUDGE_MODEL,
) -> Callable[[str, list[str], dict[str, str]], tuple[dict[str, str], JudgeUsage]]:
    """Build a judge that maps missing facets to a supporting verbatim span.

    Returns a function
    ``judge(query, ranked_texts, facets) -> ({facet: span}, JudgeUsage)`` covering
    only facets the model found attested (non-empty span), plus the token usage of
    the call. The span is NOT yet verified against the retrieved text — the caller
    must confirm it actually occurs (see ``retrieval.locate_span``).
    """
    llm = chat_models.ChatOpenAI(
        model=model,
        base_url=_DEEPINFRA_BASE_URL,
        api_key=pydantic.SecretStr(os.environ["DEEPINFRA_API_KEY"]),
        temperature=0,
        max_retries=2,
    )
    structured = llm.with_structured_output(_JudgeOutput, include_raw=True)

    def judge(
        query: str, ranked_texts: list[str], facets: dict[str, str]
    ) -> tuple[dict[str, str], JudgeUsage]:
        if not facets or not ranked_texts:
            return {}, JudgeUsage.zero()
        result = structured.invoke(
            [
                messages.SystemMessage(content=_SYSTEM_PROMPT),
                messages.HumanMessage(
                    content=_build_user_message(query, ranked_texts, facets)
                ),
            ]
        )
        parsed = result["parsed"]
        assert isinstance(parsed, _JudgeOutput)
        um = result["raw"].usage_metadata
        assert um is not None, "judge response is missing usage_metadata"
        usage = JudgeUsage(
            calls=1,
            input_tokens=um["input_tokens"],
            output_tokens=um["output_tokens"],
        )
        spans = {
            v.facet: v.span
            for v in parsed.verdicts
            if v.facet in facets and v.span.strip()
        }
        return spans, usage

    return judge
