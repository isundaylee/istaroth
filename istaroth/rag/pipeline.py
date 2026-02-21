"""RAG pipeline for end-to-end question answering."""

import logging
import typing

import attrs
from langchain_core import language_models, prompts
from langchain_core.runnables import RunnableConfig

from istaroth import langsmith_utils, llm_manager
from istaroth.agd import localization
from istaroth.rag import (
    output_rendering,
    prompt_set,
    text_set,
    types,
)

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
    def answer(self, question: str, *, k: int, chunk_context: int) -> str:
        """Answer question with source documents using the specified LLM."""

        # Preprocess the question into multiple retrieval queries
        retrieval_queries = self._preprocess_question(question)
        logger.info(
            "Preprocessed question into %d queries: %s",
            len(retrieval_queries),
            retrieval_queries,
        )

        # Retrieve documents for each query
        retrieve_outputs = []
        total_documents = 0
        for i, query in enumerate(retrieval_queries):
            retrieve_output = self._retriever.retrieve(
                query, k=k, chunk_context=chunk_context
            )
            retrieve_outputs.append(retrieve_output)
            total_documents += retrieve_output.total_documents
            logger.info(
                "Query %d ('%s') retrieved %d documents",
                i,
                query,
                retrieve_output.total_documents,
            )

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

        # Generate answer with tracing context
        config: RunnableConfig = {
            "metadata": {
                "question": question,
                "retrieval_queries": retrieval_queries,
                "k": k,
                "model": llm_manager.get_model_name(self._llm),
                "num_documents": self._retriever.num_documents,
                "num_retrieved": len(combined_retrieve_output.results),
                "retrieval_scores": [
                    score for score, _ in combined_retrieve_output.results
                ],
            }
        }
        response = chain.invoke(
            {
                "user_question": question,
                "retrieved_context": output_rendering.render_retrieve_output(
                    combined_retrieve_output.results,
                    text_set=self._text_set,
                ),
            },
            config=config,
        )

        # Extract answer text
        return llm_manager.extract_text_from_response(response)
