"""Tests for answer streaming in the RAG generate node."""

from typing import Any, AsyncIterator

import pytest
from langchain_core import callbacks, messages, outputs, prompts
from langchain_core.language_models import chat_models

from istaroth import llm_manager
from istaroth.agd import localization
from istaroth.rag import pipeline, progress, prompt_set, types


class _RecordingReporter(progress.ProgressReporter):
    """Reporter that collects every emitted event for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[progress.ProgressEvent] = []

    def _emit(self, event: progress.ProgressEvent) -> None:
        self.events.append(event)


class _ChunkStreamingModel(chat_models.BaseChatModel):
    """Fake chat model that streams a fixed list of predefined chunks."""

    chunks: list[messages.AIMessageChunk]

    @property
    def _llm_type(self) -> str:
        return "chunk-streaming-fake"

    def _generate(
        self,
        messages: list[messages.BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> outputs.ChatResult:
        raise NotImplementedError("streaming only")

    async def _astream(
        self,
        messages: list[messages.BaseMessage],
        stop: list[str] | None = None,
        run_manager: callbacks.AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[outputs.ChatGenerationChunk]:
        for chunk in self.chunks:
            yield outputs.ChatGenerationChunk(message=chunk)


def _make_pipeline_stub(llm: chat_models.BaseChatModel) -> Any:
    """Build a minimal object carrying only what ``_generate_node`` reads."""
    stub: Any = object.__new__(pipeline.RAGPipeline)
    stub._llm = llm
    stub._language = localization.Language.CHS
    rag_prompts = prompt_set.get_rag_prompts(localization.Language.CHS)
    stub._generation_prompt = prompts.ChatPromptTemplate.from_messages(
        [
            ("system", rag_prompts.generation_system_prompt),
            ("user", rag_prompts.generation_user_prompt_template),
        ]
    )

    class _Retriever:
        num_documents = 3

    stub._retriever = _Retriever()
    return stub


def _make_state(reporter: progress.ProgressReporter) -> Any:
    return {
        "question": "谁是钟离",
        "retrieved_context": "context",
        "reporter": reporter,
        "budget": 35,
        "intent": pipeline._budget.QueryIntent.BALANCED,
        "retrieval_queries": ["钟离"],
        "combined_retrieve_output": types.CombinedRetrieveOutput(
            queries=[], results=[]
        ),
    }


def test_answer_chunk_wire_shape():
    assert progress.AnswerChunk(text="hi").to_dict() == {
        "type": "answer_chunk",
        "text": "hi",
    }


@pytest.mark.parametrize(
    "content,expected",
    [
        ("plain", "plain"),
        ([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}], "ab"),
        # Plain-string list items (a legal langchain_google_genai shape) stream.
        (["Hello world"], "Hello world"),
        (["a", {"type": "text", "text": "b"}], "ab"),
        # Non-text parts (thinking/thought) are dropped so reasoning never leaks.
        ([{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "x"}], "x"),
    ],
)
def test_extract_streamed_chunk_text_filters_non_text(content, expected):
    assert (
        llm_manager.extract_streamed_chunk_text(
            messages.AIMessageChunk(content=content)
        )
        == expected
    )


@pytest.mark.parametrize(
    "chunks,expected_texts,expected_answer",
    [
        # Plain string content: chunks stream through, answer is concatenation.
        (
            [
                messages.AIMessageChunk(content="Hello"),
                messages.AIMessageChunk(content=" world"),
            ],
            ["Hello", " world"],
            "Hello world",
        ),
        # Gemini-style list content: text parts stream through per-chunk and the
        # answer is extracted from the index-merged aggregate message.
        (
            [
                messages.AIMessageChunk(
                    content=[{"type": "text", "text": "Part A", "index": 0}]
                ),
                messages.AIMessageChunk(
                    content=[{"type": "text", "text": " and B", "index": 0}]
                ),
            ],
            ["Part A", " and B"],
            "Part A and B",
        ),
    ],
)
async def test_generate_node_streams_chunks(chunks, expected_texts, expected_answer):
    reporter = _RecordingReporter()
    stub = _make_pipeline_stub(_ChunkStreamingModel(chunks=chunks))
    result = await pipeline.RAGPipeline._generate_node(stub, _make_state(reporter))

    assert [
        e.text for e in reporter.events if isinstance(e, progress.AnswerChunk)
    ] == expected_texts
    assert result["answer"] == expected_answer


async def test_generate_node_raises_without_chunks():
    reporter = _RecordingReporter()
    stub = _make_pipeline_stub(_ChunkStreamingModel(chunks=[]))
    with pytest.raises(Exception):
        await pipeline.RAGPipeline._generate_node(stub, _make_state(reporter))
