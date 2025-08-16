"""RAG pipeline for end-to-end question answering."""

import logging
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

logger = logging.getLogger(__name__)

# All technically supported models in order of decreasing speed
_ALL_SUPPORTED_MODELS: list[str] = [
    "gemini-2.5-flash-lite",  # Fastest
    "gemini-2.5-flash",
    "gpt-5-nano",
    "gpt-5-mini",
    "gemini-2.5-pro",  # Slowest
]

# Cache for available models from environment
_available_models_cache: set[str] | None = None


def get_available_models() -> list[str]:
    """Get sorted list of available model IDs from environment variable.

    Reads from ISTAROTH_AVAILABLE_MODELS environment variable.

    Special values:
    - "all": Enable all supported models

    Otherwise expects a comma-separated list of model IDs.
    """
    global _available_models_cache

    if _available_models_cache is not None:
        return sorted(_available_models_cache)

    models_env = os.environ.get("ISTAROTH_AVAILABLE_MODELS")
    if not models_env:
        raise ValueError(
            "ISTAROTH_AVAILABLE_MODELS environment variable is required. "
            "Set it to 'all' or a comma-separated list of model IDs, e.g., "
            "'gemini-2.5-flash-lite,gemini-2.5-flash,gpt-5-mini'"
        )

    # Check for special value
    if models_env.strip().lower() == "all":
        return _ALL_SUPPORTED_MODELS.copy()

    # Parse comma-separated list
    requested_models = {m.strip() for m in models_env.split(",") if m.strip()}

    if not requested_models:
        raise ValueError("ISTAROTH_AVAILABLE_MODELS cannot be empty")

    # Validate that all requested models are supported
    unsupported = requested_models - set(_ALL_SUPPORTED_MODELS)
    if unsupported:
        raise ValueError(
            f"Unsupported models in ISTAROTH_AVAILABLE_MODELS: {', '.join(sorted(unsupported))}. "
            f"Supported models are: {', '.join(_ALL_SUPPORTED_MODELS)}"
        )

    _available_models_cache = requested_models
    # Return in speed order (preserve order from _ALL_SUPPORTED_MODELS)
    return [
        model for model in _ALL_SUPPORTED_MODELS if model in _available_models_cache
    ]


def create_llm(model_name: str) -> language_models.BaseLanguageModel:
    """Create LLM instance for the specified model name."""
    available_models = get_available_models()

    if model_name not in available_models:
        raise ValueError(
            f"Model '{model_name}' is not available. Available models: {', '.join(available_models)}"
        )

    # Google models
    if model_name.startswith("gemini-"):
        return google_llms.GoogleGenerativeAI(model=model_name)
    # OpenAI models
    elif model_name.startswith("gpt-"):
        return openai_llms.ChatOpenAI(model=model_name)
    else:
        raise ValueError(f"Unknown model provider for '{model_name}'.")


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


def _extract_text_from_response(response: typing.Any) -> str:
    """Extract text content from various LLM response types."""
    if isinstance(response, messages.AIMessage):
        return str(response.content)
    elif isinstance(response, str):
        return response
    else:
        return str(response)


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
    def _preprocess_question(
        self, question: str, *, llm: language_models.BaseLanguageModel
    ) -> str:
        """Optimize question for retrieval."""
        chain = self._preprocess_prompt | llm
        response = chain.invoke({"question": question})
        preprocessed = _extract_text_from_response(response).strip()
        return preprocessed if preprocessed else question

    @langsmith_utils.traceable(name="pipeline_query")
    def answer(
        self, question: str, *, k: int, llm: language_models.BaseLanguageModel
    ) -> str:
        """Answer question with source documents using the specified LLM."""

        # Preprocess the question for better retrieval
        retrieval_query = self._preprocess_question(question, llm=llm)

        # Log if the query was modified
        if retrieval_query != question:
            logger.info(
                f"Preprocessed question from '{question}' to '{retrieval_query}'"
            )

        # Retrieve relevant documents using the preprocessed query
        retrieve_output = self._document_store.retrieve(retrieval_query, k=k)

        # Create the chain with the provided LLM
        chain = self._generation_prompt | llm

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
        return _extract_text_from_response(response)
