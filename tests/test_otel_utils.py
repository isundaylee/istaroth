"""Tests for the OTel GenAI span helper."""

from typing import Any, cast

import anyio
import orjson
import pytest
from langchain_core import language_models, messages
from opentelemetry import trace

from istaroth import llm_manager, otel_utils


class _FakeLLM:
    model_name = "fake-model"


_LLM = cast(language_models.BaseLanguageModel, _FakeLLM())


def _single_span(span_exporter: Any, name: str) -> Any:
    (span,) = [s for s in span_exporter.get_finished_spans() if s.name == name]
    return span


def test_llm_span_records_chat_response(span_exporter: Any) -> None:
    response = messages.AIMessage(
        content="hello",
        usage_metadata={"input_tokens": 3, "output_tokens": 5, "total_tokens": 8},
    )
    with otel_utils.llm_span("chat_call", llm=_LLM, prompt="hi") as gen_span:
        assert gen_span.record_response(response) is response
    span = _single_span(span_exporter, "chat_call")
    assert span.attributes["gen_ai.request.model"] == "fake-model"
    assert span.attributes["gen_ai.prompt"] == "hi"
    assert span.attributes["gen_ai.completion"] == "hello"
    assert span.attributes["gen_ai.usage.input_tokens"] == 3
    assert span.attributes["gen_ai.usage.output_tokens"] == 5


def test_llm_span_string_response_has_no_usage(span_exporter: Any) -> None:
    with otel_utils.llm_span("string_call", llm=_LLM, prompt="hi") as gen_span:
        gen_span.record_response("plain text")
    span = _single_span(span_exporter, "string_call")
    assert span.attributes["gen_ai.completion"] == "plain text"
    assert "gen_ai.usage.input_tokens" not in span.attributes
    assert "gen_ai.usage.output_tokens" not in span.attributes


def test_llm_span_message_prompt_rendered_as_json(span_exporter: Any) -> None:
    prompt = [
        messages.SystemMessage(content="sys"),
        messages.HumanMessage(content="user"),
    ]
    with otel_utils.llm_span("msg_call", llm=_LLM, prompt=prompt) as gen_span:
        gen_span.record_response("ok")
    rendered = orjson.loads(
        cast(str, _single_span(span_exporter, "msg_call").attributes["gen_ai.prompt"])
    )
    assert rendered == [
        {"role": "system", "content": "sys"},
        {"role": "human", "content": "user"},
    ]


def test_llm_span_tool_call_completion(span_exporter: Any) -> None:
    response = messages.AIMessage(
        content="",
        tool_calls=[{"name": "f", "args": {"x": 1}, "id": "1", "type": "tool_call"}],
    )
    with otel_utils.llm_span("tool_call", llm=_LLM, prompt="hi") as gen_span:
        gen_span.record_response(response)
    completion = orjson.loads(
        cast(
            str,
            _single_span(span_exporter, "tool_call").attributes["gen_ai.completion"],
        )
    )
    assert completion[0]["name"] == "f"


def test_llm_span_async_nesting(span_exporter: Any) -> None:
    async def _run() -> None:
        with trace.get_tracer(__name__).start_as_current_span("parent"):
            with otel_utils.llm_span("child", llm=_LLM, prompt="q") as gen_span:
                gen_span.record_response(await anyio.to_thread.run_sync(lambda: "resp"))

    anyio.run(_run)
    child = _single_span(span_exporter, "child")
    parent = _single_span(span_exporter, "parent")
    assert child.parent.span_id == parent.context.span_id


@pytest.mark.parametrize(
    ("attrs_dict", "expected"),
    [
        ({"model_name": "gpt-4o"}, "gpt-4o"),
        ({"model": "gemini-3.1-flash"}, "gemini-3.1-flash"),
        ({"model": "models/gemini-3.1-flash"}, "gemini-3.1-flash"),
        ({}, "_Bare"),
    ],
)
def test_get_model_name(attrs_dict: dict[str, str], expected: str) -> None:
    llm = cast(language_models.BaseLanguageModel, type("_Bare", (), attrs_dict)())
    assert llm_manager.get_model_name(llm) == expected
