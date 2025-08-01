"""RAG pipeline for end-to-end question answering."""

import typing

import attrs
from langchain import prompts
from langchain_core import language_models, messages
from langchain_core.runnables import RunnableConfig

from istaroth.rag import document_store, tracing


@attrs.define
class _SourceDocument:
    """Source document with similarity score."""

    content: str
    score: float
    index: int


@attrs.define
class _AnswerWithMetadata:
    """Answer with sources."""

    answer: str
    sources: list[_SourceDocument]


class RAGPipeline:
    """RAG pipeline for Genshin Impact lore questions."""

    _SYSTEM_PROMPT: typing.ClassVar[
        str
    ] = """你是一位了解《原神》世界观与剧情细节的专家学者，精通提瓦特大陆的历史、人物关系、神明传说与各类事件背景。你将根据提供的资料（如对话文本、任务描述、角色档案等）来回答用户提出的关于《原神》剧情、角色背景与世界观的问题。
请确保回答准确、详实，引用资料时要清晰、贴合上下文，不要编造原作中不存在的内容。若资料中没有明确提及，请指出"原文未明示"，避免主观臆断。
请用中文回答。"""

    _USER_PROMPT_TEMPLATE: typing.ClassVar[
        str
    ] = """用户提问：{user_question}

请根据以下资料进行回答：
{retrieved_context}

请基于资料内容，结合你对《原神》剧情的理解，简洁清晰地回答用户问题。"""

    def __init__(
        self,
        document_store: document_store.DocumentStore,
        llm: language_models.BaseLanguageModel,
        k: int = 5,
    ):
        """Initialize RAG pipeline."""
        self._document_store = document_store
        self._llm = llm
        self._k = k

        # Check tracing requirements
        tracing.check_tracing_requirements()

        # Create the prompt template
        self._prompt = prompts.ChatPromptTemplate.from_messages(
            [
                ("system", self._SYSTEM_PROMPT),
                ("user", self._USER_PROMPT_TEMPLATE),
            ]
        )

        # Create the chain
        self._chain = self._prompt | self._llm

    def _retrieve_context(self, query: str) -> str:
        """Retrieve and format documents as context."""
        results = self._document_store.search(query, k=self._k)

        if not results:
            return "（未找到相关资料）"

        # Format the retrieved documents
        return "\n\n".join(
            f"【资料{i}】\n{content}" for i, (content, _) in enumerate(results, 1)
        )

    def answer_with_sources(self, question: str) -> _AnswerWithMetadata:
        """Answer question with source documents."""

        # Retrieve relevant documents
        results = self._document_store.search(question, k=self._k)

        # Add tracing metadata
        run_metadata = {
            "question": question,
            "k": self._k,
            "num_documents": self._document_store.num_documents,
            "num_retrieved": len(results),
            "retrieval_scores": [score for _, score in results],
        }

        # Format context
        if not results:
            retrieved_context = "（未找到相关资料）"
            sources = []
        else:
            retrieved_context = "\n\n".join(
                f"【资料{i}】\n{content}" for i, (content, _) in enumerate(results, 1)
            )
            sources = [
                _SourceDocument(content=content, score=score, index=i)
                for i, (content, score) in enumerate(results, 1)
            ]

        # Generate answer with tracing context
        config: RunnableConfig = {"metadata": run_metadata}
        response = self._chain.invoke(
            {
                "user_question": question,
                "retrieved_context": retrieved_context,
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

        return _AnswerWithMetadata(answer=answer, sources=sources)
