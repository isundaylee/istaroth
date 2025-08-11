"""RAG pipeline for end-to-end question answering."""

import os
import typing

import attrs
from langchain import prompts
from langchain_core import language_models, messages
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import llms as google_llms
from langchain_openai import chat_models as openai_llms

from istaroth import langsmith_utils
from istaroth.agd import localization
from istaroth.rag import document_store, output_rendering, prompt_set, tracing


def create_llm(model_name: str) -> language_models.BaseLanguageModel:
    """Create LLM instance for the specified model name.

    Supported models:
    - gemini-2.5-flash-lite (default)
    - gemini-2.5-flash
    - gemini-2.5-pro
    - gpt-5-mini
    """
    # Only allow specific models
    if model_name in {"gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"}:
        return google_llms.GoogleGenerativeAI(model=model_name)
    elif model_name in {"gpt-5-mini", "gpt-5-nano"}:
        return openai_llms.ChatOpenAI(model=model_name)
    else:
        raise ValueError(f"Unsupported model '{model_name}'.")


def create_llm_from_env() -> language_models.BaseLanguageModel:
    """Create LLM instance using ISTAROTH_PIPELINE_MODEL environment variable."""
    model_name = os.environ.get("ISTAROTH_PIPELINE_MODEL", "gemini-2.5-flash-lite")
    return create_llm(model_name)


class LLMManager:
    """Manager for multiple LLM instances with lazy loading and caching."""

    def __init__(self):
        """Initialize LLM manager with empty cache."""
        self._llm_cache: dict[str, language_models.BaseLanguageModel] = {}
        self._default_model = os.environ.get(
            "ISTAROTH_PIPELINE_MODEL", "gemini-2.5-flash-lite"
        )

    def get_llm(
        self, model_name: str | None = None
    ) -> language_models.BaseLanguageModel:
        """Get LLM instance for the specified model, with caching.

        Args:
            model_name: Name of the model. If None, uses default from environment.

        Returns:
            Cached or newly created LLM instance.

        Raises:
            ValueError: If model name is not recognized.
        """
        if model_name is None:
            model_name = self._default_model

        if model_name not in self._llm_cache:
            self._llm_cache[model_name] = create_llm(model_name)

        return self._llm_cache[model_name]


class RAGPipeline:
    """RAG pipeline for Genshin Impact lore questions."""

    def __init__(
        self,
        document_store: document_store.DocumentStore,
        language: localization.Language,
    ):
        """Initialize RAG pipeline with language-specific prompts."""
        self._document_store = document_store
        self._language = language

        # Get language-specific prompts
        self._prompt_set = prompt_set.get_rag_prompts(language)

        # Create the prompt template (chain will be created per-query)
        self._prompt = prompts.ChatPromptTemplate.from_messages(
            [
                ("system", self._prompt_set.system_prompt),
                ("user", self._prompt_set.user_prompt_template),
            ]
        )

    @langsmith_utils.traceable(name="pipeline_query")
    def answer(
        self, question: str, *, k: int, llm: language_models.BaseLanguageModel
    ) -> str:
        """Answer question with source documents using the specified LLM."""

        # Retrieve relevant documents
        retrieve_output = self._document_store.retrieve(question, k=k)

        # Create the chain with the provided LLM
        chain = self._prompt | llm

        # Generate answer with tracing context
        config: RunnableConfig = {
            "metadata": {
                "question": question,
                "k": k,
                "model": getattr(llm, "model", getattr(llm, "model_name", "unknown")),
                "num_documents": self._document_store.num_documents,
                "num_retrieved": len(retrieve_output.results),
                "retrieval_scores": [score for score, _ in retrieve_output.results],
            }
        }
        response = chain.invoke(
            {
                "user_question": question,
                "retrieved_context": output_rendering.render_retrieve_output(
                    retrieve_output.results
                ),
            },
            config=config,
        )

        # Extract answer text
        if isinstance(response, messages.AIMessage):
            answer = str(response.content)
        elif isinstance(response, str):
            answer = response
        else:
            answer = str(response)

        return answer
