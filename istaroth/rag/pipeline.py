"""RAG pipeline for end-to-end question answering."""

import logging
import time
from typing import Any, Literal

import anyio
import pydantic
from langchain_core import language_models
from langchain_core import messages as langchain_messages
from langchain_core import prompts
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from istaroth import langsmith_utils, llm_manager
from istaroth.agd import localization
from istaroth.rag import budget as _budget
from istaroth.rag import (
    output_rendering,
    progress,
    prompt_set,
    query_normalize,
    text_set,
    types,
)
from istaroth.services.common import metrics
from istaroth.text import proper_noun_extraction, proper_nouns

logger = logging.getLogger(__name__)


class _PreprocessOutput(pydantic.BaseModel):
    intent: Literal["variety", "balanced", "context"]
    queries: list[str]


class _PipelineState(TypedDict):
    question: str
    normalized_question: str
    budget: int
    intent: _budget.QueryIntent
    k: int
    chunk_context: int
    reporter: progress.ProgressReporter
    retrieval_queries: list[str]
    combined_retrieve_output: types.CombinedRetrieveOutput
    retrieved_context: str
    answer: str
    stats: types.GenerationStats
    proper_nouns: list[str]


class RAGPipeline:
    """RAG pipeline for Genshin Impact lore questions."""

    def __init__(
        self,
        retriever: types.Retriever,
        language: localization.Language,
        *,
        llm: language_models.BaseLanguageModel,
        preprocessing_llm: language_models.BaseLanguageModel,
        proper_noun_llm: language_models.BaseLanguageModel,
        text_set: text_set.TextSet,
    ):
        """Initialize RAG pipeline with language-specific prompts, LLMs and graph."""
        self._retriever = retriever
        self._language = language
        self._llm = llm
        self._preprocessing_llm = preprocessing_llm
        self._proper_noun_llm = proper_noun_llm
        self._text_set = text_set
        self._normalizer = query_normalize.QueryNormalizer.from_env(
            vocabulary=self._load_proper_noun_vocabulary()
        )

        self._prompt_set = prompt_set.get_rag_prompts(language)

        self._generation_prompt = prompts.ChatPromptTemplate.from_messages(
            [
                ("system", self._prompt_set.generation_system_prompt),
                ("user", self._prompt_set.generation_user_prompt_template),
            ]
        )

        self._preprocess_prompt = prompts.ChatPromptTemplate.from_messages(
            [("user", self._prompt_set.question_preprocess_prompt)]
        )

        builder = StateGraph(_PipelineState)
        builder.add_node("normalize", self._normalize_node)
        builder.add_node("preprocess", self._preprocess_node)
        builder.add_node("retrieve", self._retrieve_node)
        builder.add_node("generate", self._generate_node)
        builder.add_node("extract_proper_nouns", self._extract_proper_nouns_node)
        builder.add_edge(START, "normalize")
        builder.add_edge("normalize", "preprocess")
        builder.add_edge("preprocess", "retrieve")
        builder.add_edge("retrieve", "generate")
        builder.add_edge("generate", "extract_proper_nouns")
        builder.add_edge("extract_proper_nouns", END)
        self._graph = builder.compile()

    async def _normalize_node(self, state: _PipelineState) -> dict[str, object]:
        with state["reporter"].step("normalizing"):
            normalized = await anyio.to_thread.run_sync(
                lambda: self._normalizer.normalize(state["question"])
            )
        logger.info("Normalized question %r -> %r", state["question"], normalized)
        return {"normalized_question": normalized}

    def _load_proper_noun_vocabulary(self) -> tuple[str, ...]:
        """Load the canon proper-noun list to ground the normalizer LLM."""
        return tuple(proper_nouns.load_terms(self._text_set.text_path))

    @langsmith_utils.traceable(name="preprocess_question")
    def _preprocess_question(
        self, question: str
    ) -> tuple[list[str], _budget.QueryIntent]:
        chain = (
            self._preprocess_prompt
            | self._preprocessing_llm.with_structured_output(_PreprocessOutput)
        )
        try:
            result = chain.invoke({"question": question})
            if isinstance(result, _PreprocessOutput):
                queries = result.queries[:3] if result.queries else [question]
                intent = _budget.QueryIntent(result.intent)
            else:
                logger.warning(
                    "Preprocessing response was not structured output (type=%s), falling back",
                    type(result).__name__,
                )
                queries, intent = [question], _budget.QueryIntent.BALANCED
            return queries, intent
        except Exception:
            logger.warning(
                "Preprocessing structured output failed, falling back", exc_info=True
            )
            return [question], _budget.QueryIntent.BALANCED

    async def _preprocess_node(self, state: _PipelineState) -> dict[str, object]:
        preprocess_start = time.perf_counter()
        with state["reporter"].step("augmenting"):
            retrieval_queries, intent = await anyio.to_thread.run_sync(
                lambda: self._preprocess_question(state["normalized_question"])
            )
        metrics.rag_pipeline_stage_preprocessing_duration_seconds.observe(
            time.perf_counter() - preprocess_start
        )
        logger.info(
            "Preprocessed question into %d queries: %s, intent=%s",
            len(retrieval_queries),
            retrieval_queries,
            intent.value,
        )
        return {"retrieval_queries": retrieval_queries, "intent": intent}

    async def _retrieve_node(self, state: _PipelineState) -> dict[str, object]:
        retrieval_start = time.perf_counter()
        k, cc = _budget.allocate(state["budget"], state["intent"])
        logger.info(
            "Budget=%d intent=%s → allocated k=%d chunk_context=%d",
            state["budget"],
            state["intent"].value,
            k,
            cc,
        )

        _retrieve_outputs: dict[int, types.RetrieveOutput] = {}

        async def _retrieve(i: int, q: str) -> None:
            with state["reporter"].step("searching", q):
                _retrieve_outputs[i] = await self._retriever.aretrieve(
                    q, k=k, chunk_context=cc
                )

        async with anyio.create_task_group() as tg:
            for i, q in enumerate(state["retrieval_queries"]):
                tg.start_soon(_retrieve, i, q)

        retrieve_outputs = [
            _retrieve_outputs[i] for i in range(len(state["retrieval_queries"]))
        ]
        total_documents = 0
        for i, (query, retrieve_output) in enumerate(
            zip(state["retrieval_queries"], retrieve_outputs)
        ):
            total_documents += retrieve_output.total_documents
            logger.info(
                "Query %d ('%s') retrieved %d documents",
                i,
                query,
                retrieve_output.total_documents,
            )

        model = llm_manager.get_model_name(self._llm)
        language = self._language.value
        metrics.rag_pipeline_stage_retrieval_duration_seconds.labels(
            model=model, language=language
        ).observe(time.perf_counter() - retrieval_start)

        combined = types.CombinedRetrieveOutput.from_multiple_outputs(retrieve_outputs)
        logger.info(
            "Retrieved %d total documents across all queries, merged to %d unique documents",
            total_documents,
            combined.total_documents,
        )

        retrieved_context = output_rendering.render_retrieve_output(
            combined.results,
            text_set=self._text_set,
        )

        return {
            "combined_retrieve_output": combined,
            "retrieved_context": retrieved_context,
            "k": k,
            "chunk_context": cc,
        }

    async def _generate_node(self, state: _PipelineState) -> dict[str, object]:
        model = llm_manager.get_model_name(self._llm)
        language = self._language.value

        chain = self._generation_prompt | self._llm
        generation_inputs = {
            "user_question": state["question"],
            "retrieved_context": state["retrieved_context"],
        }
        final_generation_input_text_length = _count_message_text_length(
            self._generation_prompt.format_messages(**generation_inputs)
        )

        config: RunnableConfig = {
            "metadata": {
                "question": state["question"],
                "retrieval_queries": state["retrieval_queries"],
                "budget": state["budget"],
                "intent": state["intent"].value,
                "k": state["k"],
                "chunk_context": state["chunk_context"],
                "model": model,
                "num_documents": self._retriever.num_documents,
                "num_retrieved": len(state["combined_retrieve_output"].results),
                "retrieval_scores": [
                    score for score, _ in state["combined_retrieve_output"].results
                ],
            }
        }

        gen_start = time.perf_counter()
        with state["reporter"].step("generating"):
            response = await anyio.to_thread.run_sync(
                lambda: chain.invoke(
                    generation_inputs,
                    config=config,
                )
            )
        metrics.rag_pipeline_stage_generation_duration_seconds.labels(
            model=model, language=language
        ).observe(time.perf_counter() - gen_start)

        return {
            "answer": llm_manager.extract_text_from_response(response),
            "stats": types.GenerationStats(
                final_generation_input_text_length=final_generation_input_text_length,
                retrieval_unique_chunk_count=state[
                    "combined_retrieve_output"
                ].total_documents,
                retrieval_unique_file_count=len(
                    state["combined_retrieve_output"].results
                ),
            ),
        }

    async def _extract_proper_nouns_node(
        self, state: _PipelineState
    ) -> dict[str, object]:
        if self._language is not localization.Language.CHS:
            return {"proper_nouns": []}
        with state["reporter"].step("extracting_proper_nouns"):
            try:
                negative_terms = proper_nouns.parse_terms(
                    self._text_set.get_content(
                        proper_nouns.PROPER_NOUNS_NEGATIVE_RELATIVE_PATH.as_posix()
                    )
                )
                try:
                    extracted = (
                        await proper_noun_extraction.extract_proper_nouns_cached(
                            state["answer"], llm=self._proper_noun_llm
                        )
                    )
                except proper_noun_extraction.CharBudgetExceededError:
                    logger.warning(
                        "Proper-noun extraction budget exceeded; serving static list"
                    )
                    extracted = proper_nouns.parse_terms(
                        self._text_set.get_content(
                            proper_nouns.PROPER_NOUNS_RELATIVE_PATH.as_posix()
                        )
                    )
                result = sorted(
                    {
                        term
                        for term in proper_nouns.filter_terms(extracted, negative_terms)
                        if term in state["answer"]
                    }
                )
            except Exception:
                logger.warning("Answer proper-noun extraction failed", exc_info=True)
                result = []
        return {"proper_nouns": result}

    @langsmith_utils.traceable(name="pipeline_query")
    async def answer(
        self,
        question: str,
        *,
        budget: int,
        reporter: progress.ProgressReporter = progress.NULL_REPORTER,
        intent_override: _budget.QueryIntent | None = None,
    ) -> types.AnswerResult:
        """Answer question using the LangGraph pipeline."""
        _intent = intent_override or _budget.QueryIntent.BALANCED
        initial_state: _PipelineState = {
            "question": question,
            "normalized_question": question,
            "budget": budget,
            "intent": _intent,
            "k": 0,
            "chunk_context": 0,
            "reporter": reporter,
            "retrieval_queries": [],
            "combined_retrieve_output": types.CombinedRetrieveOutput(
                queries=[], results=[]
            ),
            "retrieved_context": "",
            "answer": "",
            "stats": types.GenerationStats(
                final_generation_input_text_length=0,
                retrieval_unique_chunk_count=0,
                retrieval_unique_file_count=0,
            ),
            "proper_nouns": [],
        }
        state = await self._graph.ainvoke(initial_state)  # type: ignore[arg-type]
        return types.AnswerResult(
            answer=state["answer"],
            stats=state["stats"],
            proper_nouns=state["proper_nouns"],
        )


def _count_message_text_length(
    messages: list[langchain_messages.BaseMessage],
) -> int:
    return sum(_message_content_text_length(message.content) for message in messages)


def _message_content_text_length(content: str | list[Any]) -> int:
    if isinstance(content, str):
        return len(content)
    raise TypeError(f"Unexpected non-text generation prompt content: {content!r}")
