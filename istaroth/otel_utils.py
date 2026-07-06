"""OpenTelemetry GenAI span helpers for LLM call sites."""

import collections.abc
import contextlib
from typing import TypeVar

import attrs
import orjson
from langchain_core import language_models, messages
from opentelemetry import trace

from istaroth import llm_manager

_tracer = trace.get_tracer(__name__)

_T = TypeVar("_T")

PromptLike = str | collections.abc.Sequence[messages.BaseMessage]


def _render_prompt(prompt: PromptLike) -> str:
    if isinstance(prompt, str):
        return prompt
    return orjson.dumps(
        [{"role": m.type, "content": m.content} for m in prompt]
    ).decode()


@attrs.define
class GenAISpan:
    """Handle for recording an LLM response onto the active GenAI span."""

    _span: trace.Span

    def record_response(self, response: _T) -> _T:
        """Record completion text and token usage; returns response for chaining."""
        text = llm_manager.extract_text_from_response(response)
        if (
            not text
            and isinstance(response, messages.AIMessage)
            and response.tool_calls
        ):
            text = orjson.dumps(response.tool_calls).decode()
        self._span.set_attribute("gen_ai.completion", text)
        if isinstance(response, messages.AIMessage) and (
            usage := response.usage_metadata
        ):
            self._span.set_attribute("gen_ai.usage.input_tokens", usage["input_tokens"])
            self._span.set_attribute(
                "gen_ai.usage.output_tokens", usage["output_tokens"]
            )
        return response


@contextlib.contextmanager
def llm_span(
    name: str, *, llm: language_models.BaseLanguageModel, prompt: PromptLike
) -> collections.abc.Iterator[GenAISpan]:
    """Span around one LLM call, carrying model, prompt, completion, and usage."""
    with _tracer.start_as_current_span(name, kind=trace.SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.request.model", llm_manager.get_model_name(llm))
        span.set_attribute("gen_ai.prompt", _render_prompt(prompt))
        yield GenAISpan(span)
