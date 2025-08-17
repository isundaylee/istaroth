"""Tools for reasoning pipeline."""

import logging
from typing import Any

from langchain_core import tools
from langchain_core.tools import BaseTool, Tool
from pydantic import BaseModel, Field

from istaroth.agd import localization
from istaroth.rag import document_store, output_rendering

logger = logging.getLogger(__name__)


class DocumentRetrievalInput(BaseModel):
    """Input schema for document retrieval tool."""

    query: str = Field(
        description=(
            "《原神》相关内容的搜索查询。必须只关注一个概念。"
            "使用单个关键词（角色名、地点、物品）或关于单个特定主题的完整句子/问题。"
            "示例：'钟离'、'什么是灾祸？'、'散兵的起源'。"
        )
    )
    k: int = Field(default=5, description="要检索的文件结果数量。")
    chunk_context: int = Field(
        default=5,
        description="每个文件结果要包含多少个周围的上下文块。",
    )


class DocumentRetrievalTool(BaseTool):
    """Document retrieval from RAG store."""

    name: str = "document_retrieval"
    description: str = """
        搜索《原神》相关文档。重要：每次查询只能关注一个概念。
        查询格式：单个关键词（角色名、地点名、物品名）或关于单个特定主题的完整句子/问题。
        重要：不要在一个查询中组合多个概念！
    """
    args_schema: type[BaseModel] = DocumentRetrievalInput

    def __init__(
        self,
        document_store: document_store.DocumentStore,
        *,
        language: localization.Language = localization.Language.ENG,
    ):
        """Initialize with document store and language."""
        super().__init__()
        self._document_store = document_store
        self._language = language

    def _run(self, query: str, k: int = 5, chunk_context: int = 5) -> str:
        """Execute document retrieval."""
        # Retrieve documents
        return output_rendering.render_retrieve_output(
            self._document_store.retrieve(
                query, k=k, chunk_context=chunk_context
            ).results
        )

    async def _arun(self, query: str, k: int = 5, chunk_context: int = 5) -> str:
        """Async version."""
        return self._run(query, k, chunk_context)


def get_default_tools(
    document_store: document_store.DocumentStore,
    *,
    language: localization.Language = localization.Language.ENG,
) -> list[BaseTool]:
    """Get default tools for reasoning."""
    return [DocumentRetrievalTool(document_store, language=language)]
