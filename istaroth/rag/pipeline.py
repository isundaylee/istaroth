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
from istaroth.rag import document_store, output_rendering, tracing


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

    _SYSTEM_PROMPT: typing.ClassVar[
        str
    ] = """你是一位专精《原神》世界观与剧情的学者，对提瓦特大陆拥有深厚的研究基础。你的专业领域包括：

- **历史脉络**：从古代文明、神魔战争到各国兴衰，掌握完整时间线
- **神明体系**：七神权能、魔神残留、神之眼赋予原理等知识
- **人物关系**：角色背景、人际网络、组织架构与政治格局
- **预言传说**：古籍记载、民间传说与其现实对应关系

回答原则：
- **准确性第一**：严格基于提供的资料内容，绝不编造或臆测不存在的情节
- **明确资料边界**：当资料不足时，明确指出"资料未明示"或"原文未详述"
- **逻辑推理**：在资料支撑下，可进行合理的逻辑推导，但需明确区分事实与推论
- **结构清晰**：按逻辑层次组织答案，重要信息优先，次要细节补充
- **引用原文**：当需要引用原文的时候，必须在回答重复原始文本段落，使用引号标注。用户无法看到检索的上下文，因此你需要在答案中重复关键原文。无需提供引用的文件与片段编号
- **原文展示**：对于关键论据，应完整引用相关原文段落，而非仅做概括总结

请始终用中文回答，语言准确专业，避免过度解读或主观臆断。记住：用户看不到你检索到的资料，所以必须在回答中充分引用原文。"""

    _USER_PROMPT_TEMPLATE: typing.ClassVar[
        str
    ] = """用户提问：{user_question}

请根据以下资料进行回答：
{retrieved_context}

回答要求：

请基于资料内容，结合你对《原神》剧情的理解，简洁清晰地回答用户问题。"""

    def __init__(self, document_store: document_store.DocumentStore):
        """Initialize RAG pipeline."""
        self._document_store = document_store

        # Create the prompt template (chain will be created per-query)
        self._prompt = prompts.ChatPromptTemplate.from_messages(
            [
                ("system", self._SYSTEM_PROMPT),
                ("user", self._USER_PROMPT_TEMPLATE),
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
