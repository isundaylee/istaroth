#!/usr/bin/env python3
"""HTTP/WebSocket MCP server for Istaroth RAG functionality."""

import pathlib
import sys

from fastmcp import FastMCP
from langsmith import traceable

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.rag import embedding

# Create an MCP server
mcp = FastMCP("istaroth")
store = embedding.DocumentStore.from_env()


@mcp.tool()  # type: ignore[misc]
@traceable(name="mcp_retrieve")  # type: ignore[misc]
def retrieve(query: str, k: int = 5) -> str:
    """从Istaroth原神知识库中检索相关文档

    这是一个智能文档检索工具，专门用于查找原神游戏相关的背景故事、角色设定、世界观等内容。最好使用完整的句子或问题形式，以便更准确地匹配相关文档。

    参数：
    - query: 查询问题；最好使用完整的句子或问题形式，以便更准确地匹配相关文档。
    - k: 返回文档数量，默认5个

    适用场景：
    - 查询角色背景故事和关系
    - 搜索地区历史和传说
    - 了解游戏世界观设定
    - 探索剧情细节和彩蛋
    """
    try:
        if store.num_documents == 0:
            return "错误：文档库为空，请先添加文档。"

        results = store.search(query, k=k)

        if not results:
            return "未找到相关结果。"

        output_parts = [
            f"查询 '{query}' 检索到 {len(results)} 个文档：",
            "",
        ]

        for i, (text, _) in enumerate(results):
            output_parts.append(f"==================== 文档 {i + 1}：")
            output_parts.append(text)
            output_parts.append("")

        return "\n".join(output_parts)
    except Exception as e:
        return f"检索文档时发生错误：{e}"


if __name__ == "__main__":
    mcp.run()
