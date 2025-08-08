#!/usr/bin/env python3
"""HTTP/WebSocket MCP server for Istaroth RAG functionality."""

import pathlib
import sys

from fastmcp import FastMCP

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import langsmith as ls

from istaroth.rag import document_store, output_rendering

# Create an MCP server
mcp = FastMCP("istaroth")
store = document_store.DocumentStore.from_env()


@mcp.tool()  # type: ignore[misc]
def get_file_content(file_id: str, max_chunks: int = 50, start_index: int = 0) -> str:
    """获取指定文件的内容块

    根据文件ID返回文件中的内容片段，支持分页获取。

    参数：
    - file_id: 文件ID（MD5哈希值）
    - max_chunks: 返回的最大片段数，默认50个
    - start_index: 起始片段索引，默认从0开始

    返回：
    - 文件的内容片段，每个片段包含索引和内容
    """
    try:
        if store.num_documents == 0:
            return "错误：文档库为空。"

        # Get all chunks for the file
        all_chunks = store.get_file_chunks(file_id)

        if all_chunks is None:
            return f"错误：未找到文件ID '{file_id}'。"

        total_chunks = len(all_chunks)

        # Validate start_index
        if start_index < 0 or start_index >= total_chunks:
            return f"错误：起始索引 {start_index} 超出范围。文件共有 {total_chunks} 个片段。"

        # Apply pagination
        end_index = min(start_index + max_chunks, total_chunks)
        chunks = all_chunks[start_index:end_index]

        # Format output
        output_lines = [
            f"文件ID: {file_id}",
            f"总片段数: {total_chunks}",
            f"返回片段: {start_index} 至 {end_index - 1}",
            "=" * 60,
            "",
        ]

        for i, doc in enumerate(chunks, start=start_index):
            output_lines.append(f"【片段 {i}】")
            output_lines.append(doc.page_content)
            output_lines.append("-" * 60)

        # Add navigation info if there are more chunks
        if end_index < total_chunks:
            remaining = total_chunks - end_index
            output_lines.append(
                f"\n还有 {remaining} 个片段未显示。使用 start_index={end_index} 获取下一批。"
            )

        return "\n".join(output_lines)

    except Exception as e:
        return f"获取文件时发生错误：{e}"


@mcp.tool()  # type: ignore[misc]
def retrieve(query: str, k: int = 10, chunk_context: int = 5) -> str:
    """从Istaroth原神知识库中检索相关文档

    这是一个智能文档检索工具，专门用于查找原神游戏相关的背景故事、角色设定、世界观等内容。最好使用完整的句子或问题形式，以便更准确地匹配相关文档。

    参数：
    - query: 查询问题；最好使用完整的句子或问题形式，以便更准确地匹配相关文档。
    - k: 返回文档数量，默认10个；建议设置为10至20之间，以获取更全面的结果。
    - chunk_context: 返回匹配文档块周围的上下文块数量，默认5个

    适用场景：
    - 查询角色背景故事和关系
    - 搜索地区历史和传说
    - 了解游戏世界观设定
    - 探索剧情细节和彩蛋
    """
    try:
        if store.num_documents == 0:
            return "错误：文档库为空，请先添加文档。"

        with ls.trace(
            "mcp_retrieve",
            "chain",
            inputs={"query": query, "k": k, "chunk_context": chunk_context},
        ) as rt:
            retrieve_output = store.retrieve(query, k=k, chunk_context=chunk_context)

            if not retrieve_output.results:
                formatted_output = "未找到相关结果。"
            else:
                formatted_output = "\n".join(
                    [
                        f"查询 '{query}' 检索到 {len(retrieve_output.results)} 个文件：",
                        "",
                        output_rendering.render_retrieve_output(
                            retrieve_output.results
                        ),
                        "",
                        "=" * 60,
                        "提示：如需获取某个文件的完整内容，请使用 get_file_content 工具，",
                        "传入上面结果中的文件ID（file_id）即可获取该文件的所有内容片段。",
                    ]
                )

            rt.end(outputs=retrieve_output.to_langsmith_output(formatted_output))

        return formatted_output
    except Exception as e:
        return f"检索文档时发生错误：{e}"


if __name__ == "__main__":
    mcp.run()
