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

Judging is two-pass to guard against the leniency leak (the model crediting a
facet on a span that merely mentions a related term): pass 1 finds candidate
spans with a justification; pass 2 independently and adversarially re-checks each
candidate span IN ISOLATION — does this span, on its own, state the fact? — and
drops the ones that don't. The span-in-isolation check is what kills "比如…神之心"
type fragments that only co-occur with the facet.

The model is resolved through ``istaroth.llm_manager`` (DeepSeek V4 Flash on
DeepInfra by default); it must be listed in ``ISTAROTH_AVAILABLE_MODELS``.
"""

import typing
from collections.abc import Callable

import attrs
import pydantic
from langchain_core import messages

from istaroth import llm_manager

DEFAULT_JUDGE_MODEL = "deepseek-ai/DeepSeek-V4-Flash"

_SYSTEM_PROMPT = (
    "You grade retrieval for a Genshin Impact lore QA system. Given a user query, "
    "a numbered list of retrieved passages, and a list of facets (each an aspect a "
    "complete answer should cover), find for EACH facet the passage span that best "
    "supports it. A separate strict verifier will re-check your spans, so surface "
    "the strongest candidate rather than over-rejecting.\n"
    "Rules:\n"
    "- Use ONLY the passage text. Do NOT rely on your own knowledge of Genshin lore.\n"
    "- First write a one-line justification — the corroborating evidence for how the "
    "span supports the facet — THEN give the span.\n"
    "- The span must be a SHORT verbatim substring (roughly 8-40 characters) copied "
    "character-for-character from the passages — exact characters including "
    "punctuation (「」、，。…). Do NOT paraphrase, translate, summarize, or invent.\n"
    "- If no passage is relevant to the facet, return an empty string for its span.\n"
    "- Return exactly one verdict per facet."
)

_VERIFY_SYSTEM_PROMPT = (
    "You are a strict, adversarial verifier. You are given the user query (for "
    "referential context ONLY — e.g. to resolve who 'you' / 'the traveler' refers "
    "to) and, for each (facet, span) pair, a short span copied from a retrieved "
    "passage. Decide whether the span — read with the query's referents but "
    "WITHOUT any surrounding passage text and WITHOUT outside lore knowledge — "
    "explicitly STATES the claim.\n"
    "Answer attested=true ONLY if the span itself asserts the specific claim. "
    "Answer attested=false if the span merely mentions a name or term from the "
    "claim, is a fragment, or would need the surrounding passage to support the "
    "claim. When in doubt, answer false. Echo the given facet id verbatim in the "
    "`facet` field, one verdict per pair."
)


class _FacetVerdict(pydantic.BaseModel):
    facet: str = pydantic.Field(description="the facet id being judged")
    justification: str = pydantic.Field(
        description="one line: how the span states the fact, or why none does"
    )
    span: str = pydantic.Field(
        description=(
            "a verbatim substring copied character-for-character from the passages "
            "that states the facet on its own; empty string if no passage states it"
        )
    )


class _JudgeOutput(pydantic.BaseModel):
    verdicts: list[_FacetVerdict]


class _VerifyVerdict(pydantic.BaseModel):
    facet: str = pydantic.Field(description="the facet id being verified")
    attested: bool = pydantic.Field(
        description="true only if the span alone explicitly states the facet"
    )


class _VerifyOutput(pydantic.BaseModel):
    verdicts: list[_VerifyVerdict]


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


def _usage_of(raw: typing.Any) -> JudgeUsage:
    um = raw.usage_metadata
    assert um is not None, "judge response is missing usage_metadata"
    return JudgeUsage(
        calls=1, input_tokens=um["input_tokens"], output_tokens=um["output_tokens"]
    )


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


def _build_verify_message(
    query: str, facets: dict[str, str], candidates: dict[str, str]
) -> str:
    pairs = "\n\n".join(
        f"Facet id: {facet}\nClaim: {facets[facet]}\nSpan: 「{span}」"
        for facet, span in candidates.items()
    )
    return f"User query (context only):\n{query}\n\n{pairs}"


def make_judge(
    model: str = DEFAULT_JUDGE_MODEL,
) -> Callable[[str, list[str], dict[str, str]], tuple[dict[str, str], JudgeUsage]]:
    """Build a two-pass judge that maps missing facets to a supporting verbatim span.

    Returns a function
    ``judge(query, ranked_texts, facets) -> ({facet: span}, JudgeUsage)`` covering
    only facets the model found attested AND that survive the adversarial
    span-in-isolation verification, plus the token usage of both passes. The span
    is NOT yet verified against the retrieved text — the caller must confirm it
    actually occurs (see ``retrieval.locate_span``).
    """
    llm = llm_manager.LLMManager().get_llm(model, temperature=0)
    finder = llm.with_structured_output(_JudgeOutput, include_raw=True)
    verifier = llm.with_structured_output(_VerifyOutput, include_raw=True)

    def judge(
        query: str, ranked_texts: list[str], facets: dict[str, str]
    ) -> tuple[dict[str, str], JudgeUsage]:
        if not facets or not ranked_texts:
            return {}, JudgeUsage.zero()
        result = finder.invoke(
            [
                messages.SystemMessage(content=_SYSTEM_PROMPT),
                messages.HumanMessage(
                    content=_build_user_message(query, ranked_texts, facets)
                ),
            ]
        )
        assert isinstance(result, dict)  # include_raw=True returns raw/parsed/error
        parsed = result["parsed"]
        assert isinstance(parsed, _JudgeOutput)
        usage = _usage_of(result["raw"])
        candidates = {
            v.facet: v.span
            for v in parsed.verdicts
            if v.facet in facets and v.span.strip()
        }
        if not candidates:
            return {}, usage

        # Pass 2: adversarially re-check each candidate span in isolation.
        vresult = verifier.invoke(
            [
                messages.SystemMessage(content=_VERIFY_SYSTEM_PROMPT),
                messages.HumanMessage(
                    content=_build_verify_message(query, facets, candidates)
                ),
            ]
        )
        assert isinstance(vresult, dict)
        vparsed = vresult["parsed"]
        assert isinstance(vparsed, _VerifyOutput)
        usage = usage + _usage_of(vresult["raw"])
        confirmed = {v.facet for v in vparsed.verdicts if v.attested}
        spans = {
            facet: span for facet, span in candidates.items() if facet in confirmed
        }
        return spans, usage

    return judge
