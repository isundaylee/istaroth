"""RAG pipeline for end-to-end question answering."""

import logging
import time
from typing import Any

import anyio
import attrs
from langchain_core import language_models
from langchain_core import messages as langchain_messages
from langchain_core import prompts
from langchain_core.runnables import RunnableConfig

from istaroth import langsmith_utils, llm_manager
from istaroth.agd import localization
from istaroth.rag import (
    output_rendering,
    progress,
    prompt_set,
    text_set,
    types,
)
from istaroth.services.common import metrics
from istaroth.text import proper_nouns

logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG pipeline for Genshin Impact lore questions."""

    def __init__(
        self,
        retriever: types.Retriever,
        language: localization.Language,
        *,
        llm: language_models.BaseLanguageModel,
        preprocessing_llm: language_models.BaseLanguageModel,
        text_set: text_set.TextSet,
    ):
        """Initialize RAG pipeline with language-specific prompts and preprocessing LLM."""
        self._retriever = retriever
        self._language = language
        self._llm = llm
        self._preprocessing_llm = preprocessing_llm
        self._text_set = text_set

        # Get language-specific prompts
        self._prompt_set = prompt_set.get_rag_prompts(language)

        # Create the generation prompt template
        self._generation_prompt = prompts.ChatPromptTemplate.from_messages(
            [
                ("system", self._prompt_set.generation_system_prompt),
                ("user", self._prompt_set.generation_user_prompt_template),
            ]
        )

        # Create the preprocessing prompt template
        self._preprocess_prompt = prompts.ChatPromptTemplate.from_messages(
            [("user", self._prompt_set.question_preprocess_prompt)]
        )

    @langsmith_utils.traceable(name="preprocess_question")
    def _preprocess_question(self, question: str) -> list[str]:
        """Convert question into 1-3 optimized retrieval queries."""
        chain = self._preprocess_prompt | self._preprocessing_llm
        response = chain.invoke({"question": question})
        preprocessed = llm_manager.extract_text_from_response(response).strip()

        # Split into individual queries (one per line)
        queries = [q.strip() for q in preprocessed.splitlines() if q.strip()]

        # Limit to 3 queries and ensure at least one
        if not queries:
            return [question]
        return queries[:3]

    @langsmith_utils.traceable(name="pipeline_query")
    async def answer(
        self,
        question: str,
        *,
        k: int,
        chunk_context: int,
        reporter: progress.ProgressReporter = progress.NULL_REPORTER,
    ) -> types.AnswerResult:
        """Answer question with source documents using the specified LLM."""
        model = llm_manager.get_model_name(self._llm)
        language = self._language.value

        # Preprocess the question into multiple retrieval queries
        preprocess_start = time.perf_counter()
        with reporter.step("augmenting"):
            retrieval_queries = await anyio.to_thread.run_sync(
                lambda: self._preprocess_question(question)
            )
        metrics.rag_pipeline_stage_preprocessing_duration_seconds.observe(
            time.perf_counter() - preprocess_start
        )
        logger.info(
            "Preprocessed question into %d queries: %s",
            len(retrieval_queries),
            retrieval_queries,
        )

        # Retrieve documents for each query in parallel
        retrieval_start = time.perf_counter()
        _retrieve_outputs: dict[int, types.RetrieveOutput] = {}

        async def _retrieve(i: int, q: str) -> None:
            with reporter.step("searching", q):
                _retrieve_outputs[i] = await self._retriever.aretrieve(
                    q, k=k, chunk_context=chunk_context
                )

        async with anyio.create_task_group() as tg:
            for i, q in enumerate(retrieval_queries):
                tg.start_soon(_retrieve, i, q)
        retrieve_outputs = [_retrieve_outputs[i] for i in range(len(retrieval_queries))]
        total_documents = 0
        for i, (query, retrieve_output) in enumerate(
            zip(retrieval_queries, retrieve_outputs)
        ):
            total_documents += retrieve_output.total_documents
            logger.info(
                "Query %d ('%s') retrieved %d documents",
                i,
                query,
                retrieve_output.total_documents,
            )
        metrics.rag_pipeline_stage_retrieval_duration_seconds.labels(
            model=model, language=language
        ).observe(time.perf_counter() - retrieval_start)

        # Combine all retrieval outputs with deduplication
        combined_retrieve_output = types.CombinedRetrieveOutput.from_multiple_outputs(
            retrieve_outputs
        )

        # Log retrieval statistics
        logger.info(
            "Retrieved %d total documents across all queries, merged to %d unique documents",
            total_documents,
            combined_retrieve_output.total_documents,
        )

        # Create the chain with the provided LLM
        chain = self._generation_prompt | self._llm
        retrieved_context = output_rendering.render_retrieve_output(
            combined_retrieve_output.results,
            text_set=self._text_set,
        )
        generation_inputs = {
            "user_question": question,
            "retrieved_context": retrieved_context,
        }
        final_generation_input_text_length = _count_message_text_length(
            self._generation_prompt.format_messages(**generation_inputs)
        )

        # Generate answer with tracing context
        config: RunnableConfig = {
            "metadata": {
                "question": question,
                "retrieval_queries": retrieval_queries,
                "k": k,
                "model": model,
                "num_documents": self._retriever.num_documents,
                "num_retrieved": len(combined_retrieve_output.results),
                "retrieval_scores": [
                    score for score, _ in combined_retrieve_output.results
                ],
            }
        }
        gen_start = time.perf_counter()
        with reporter.step("generating"):
            response = await anyio.to_thread.run_sync(
                lambda: chain.invoke(
                    generation_inputs,
                    config=config,
                )
            )
        metrics.rag_pipeline_stage_generation_duration_seconds.labels(
            model=model, language=language
        ).observe(time.perf_counter() - gen_start)

        answer_text = llm_manager.extract_text_from_response(response)

        # Extract proper nouns from the answer
        with reporter.step("extracting"):
            terms = await anyio.to_thread.run_sync(
                proper_nouns.load_terms, self._text_set.text_path
            )
            answer_lower = answer_text.lower()
            answer_proper_nouns = [t for t in terms if t.lower() in answer_lower]

        return types.AnswerResult(
            answer=answer_text,
            proper_nouns=answer_proper_nouns,
            stats=types.GenerationStats(
                final_generation_input_text_length=final_generation_input_text_length,
                retrieval_unique_chunk_count=combined_retrieve_output.total_documents,
                retrieval_unique_file_count=len(combined_retrieve_output.results),
            ),
        )


def _count_message_text_length(
    messages: list[langchain_messages.BaseMessage],
) -> int:
    return sum(_message_content_text_length(message.content) for message in messages)


def _message_content_text_length(content: str | list[Any]) -> int:
    if isinstance(content, str):
        return len(content)
    raise TypeError(f"Unexpected non-text generation prompt content: {content!r}")
