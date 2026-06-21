#!/usr/bin/env python3
"""HTTP/WebSocket MCP server for Istaroth RAG functionality."""

import hashlib
import os
import pathlib
import sys
import traceback

from fastmcp import FastMCP

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import langsmith as ls

from istaroth.agd import hierarchy_nav, localization, processed_types
from istaroth.rag import document_store_set, output_rendering
from istaroth.text import types as text_types

mcp: FastMCP = FastMCP("istaroth")

_HINT_GET_FILE_CONTENT = "\n".join(
    [
        "=" * 60,
        "提示：如需获取某个文件的完整内容，请使用 get_file_content 工具，",
        "传入上面结果中的文件ID（file_id）即可获取该文件的所有内容片段。",
        "注意：大文件可能需要多次调用，使用不同的 start_index 参数来获取所有内容。",
    ]
)

try:
    if os.getenv("ISTAROTH_RETRIEVAL_SERVICE_URL"):
        _store_set = document_store_set.DocumentStoreSet.from_retrieval_service()
    else:
        _store_set = document_store_set.DocumentStoreSet.from_env()
    _mcp_language_str = os.environ["ISTAROTH_MCP_LANGUAGE"]
    _mcp_language = localization.Language(_mcp_language_str.upper())
    _store = _store_set.get_store(_mcp_language)
    _text_set = _store_set.get_text_set(_mcp_language)
except Exception as e:
    raise RuntimeError(
        f"Failed to initialize document store: {e} from \n\n{"".join(traceback.format_exc())}"
    ) from e


def _node_label(node: processed_types.HierarchyNode) -> str:
    return node.title or node.key


@mcp.tool()
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
        if _store.num_documents == 0:
            return "错误：文档库为空。"

        with ls.trace(
            "mcp_get_file_content",
            "chain",
            inputs={
                "file_id": file_id,
                "max_chunks": max_chunks,
                "start_index": start_index,
            },
        ) as rt:
            # Get all chunks for the file
            all_chunks = _store.get_file_chunks(file_id)

            if all_chunks is None:
                error_msg = f"错误：未找到文件ID '{file_id}'。"
                rt.end(outputs={"error": error_msg})
                return error_msg

            total_chunks = len(all_chunks)

            # Validate start_index
            if start_index < 0 or start_index >= total_chunks:
                error_msg = f"错误：起始索引 {start_index} 超出范围。文件共有 {total_chunks} 个片段。"
                rt.end(outputs={"error": error_msg})
                return error_msg

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

            formatted_output = "\n".join(output_lines)

            # Log to LangSmith with metadata about the retrieved chunks
            rt.end(
                outputs={
                    "file_id": file_id,
                    "total_chunks": total_chunks,
                    "chunks_returned": len(chunks),
                    "start_index": start_index,
                    "end_index": end_index - 1,
                    "has_more": end_index < total_chunks,
                    "output": formatted_output,
                }
            )

            return formatted_output

    except Exception as e:
        return f"获取文件时发生错误：{e}"


@mcp.tool()
def retrieve(query: str, k: int = 10, chunk_context: int = 5) -> str:
    """从Istaroth原神知识库中检索相关文档

    这是一个智能文档检索工具，专门用于查找原神游戏相关的背景故事、角色设定、世界观等内容。最好使用完整的句子或问题形式，以便更准确地匹配相关文档。

    参数：
    - query: 查询问题；最好使用完整的句子或问题形式，以便更准确地匹配相关文档。
    - k: 返回文档数量，默认10个；建议设置为10至20之间，以获取更全面的结果。
    - chunk_context: 返回匹配文档块周围的上下文块数量，默认5个

    适用场景（语义检索）：
    - 查询角色背景故事和关系
    - 搜索地区历史和传说
    - 了解游戏世界观设定
    - 探索剧情细节和彩蛋

    如需关键词精确检索，请使用retrieve_bm25工具：
    - 查找特定角色名称、地名或物品的精确出现
    - 验证某个具体术语是否在知识库中出现
    - 需要精确字面匹配而非语义理解的结果
    """
    try:
        if _store.num_documents == 0:
            return "错误：文档库为空，请先添加文档。"

        with ls.trace(
            "mcp_retrieve",
            "chain",
            inputs={"query": query, "k": k, "chunk_context": chunk_context},
        ) as rt:
            retrieve_output = _store.retrieve(query, k=k, chunk_context=chunk_context)

            if not retrieve_output.results:
                formatted_output = "未找到相关结果。"
            else:
                formatted_output = "\n".join(
                    [
                        f"查询 '{query}' 检索到 {len(retrieve_output.results)} 个文件：",
                        "",
                        output_rendering.render_retrieve_output(
                            retrieve_output.results, text_set=_text_set
                        ),
                        "",
                        "=" * 60,
                        _HINT_GET_FILE_CONTENT,
                    ]
                )

            rt.end(
                outputs=retrieve_output.to_langsmith_output(
                    formatted_output, text_set=_text_set
                )
            )

        return formatted_output
    except Exception as e:
        return f"检索文档时发生错误：{e}"


@mcp.tool()
def retrieve_bm25(query: str, k: int = 10, chunk_context: int = 5) -> str:
    """从Istaroth原神知识库中检索相关文档（BM25关键词精确匹配）

    这是一个基于BM25关键词的精确检索工具，专门用于查找包含特定名称、术语或专有名词的文档。与retrieve工具不同，
    本工具不涉及语义/向量检索，仅进行精确的关键词匹配。

    参数：
    - query: 查询关键词；建议使用具体的人物名、地名、物品名等专有名词，以获得最佳匹配效果。
    - k: 返回文档数量，默认10个；建议设置为10至20之间，以获取更全面的结果。
    - chunk_context: 返回匹配文档块周围的上下文块数量，默认5个

    本工具适用场景（BM25关键词检索）：
    - 查找特定角色名称、地名或物品的精确出现
    - 验证某个具体术语是否在知识库中出现
    - 需要精确字面匹配而非语义理解的结果

    如需语义/概念检索，请使用retrieve工具：
    - 语义/概念查询，需要模糊匹配和理解
    - 用完整句子或问题形式提问
    - 需要基于语义相似度而非字面匹配的检索
    """
    try:
        if _store.num_documents == 0:
            return "错误：文档库为空，请先添加文档。"

        with ls.trace(
            "mcp_retrieve_bm25",
            "chain",
            inputs={"query": query, "k": k, "chunk_context": chunk_context},
        ) as rt:
            retrieve_output = _store.retrieve_bm25(
                query, k=k, chunk_context=chunk_context
            )

            if not retrieve_output.results:
                formatted_output = "未找到相关结果。"
            else:
                formatted_output = "\n".join(
                    [
                        f"查询 '{query}' 检索到 {len(retrieve_output.results)} 个文件：",
                        "",
                        output_rendering.render_retrieve_output(
                            retrieve_output.results, text_set=_text_set
                        ),
                        "",
                        "=" * 60,
                        _HINT_GET_FILE_CONTENT,
                    ]
                )

            rt.end(
                outputs=retrieve_output.to_langsmith_output(
                    formatted_output, text_set=_text_set
                )
            )

        return formatted_output
    except Exception as e:
        return f"检索文档时发生错误：{e}"


@mcp.tool()
def get_document_hierarchy(file_id: str) -> str:
    """获取指定文档的层级归属与目录

    根据文件ID返回该文档在游戏内容层级中的位置（如任务类型→系列→章节），
    以及同级文档的目录列表，帮助用户理解文档在叙事上下文中的位置。

    参数：
    - file_id: 文件ID（MD5哈希值）

    返回：
    - 文件的层级归属信息（面包屑路径）
    - 同级文档目录列表（含各文件的file_id，可供 get_file_content 使用）
    """
    try:
        if _store.num_documents == 0:
            return "错误：文档库为空。"

        with ls.trace(
            "mcp_get_document_hierarchy",
            "chain",
            inputs={"file_id": file_id},
        ) as rt:
            chunks = _store.get_file_chunks(file_id)
            if chunks is None:
                error_msg = f"错误：未找到文件ID '{file_id}'。"
                rt.end(outputs={"error": error_msg})
                return error_msg

            relative_path = chunks[0].metadata["path"]
            manifest_item = _text_set.get_manifest_item_by_relative_path(relative_path)
            if manifest_item is None:
                error_msg = f"错误：未找到文件路径 '{relative_path}' 的清单条目。"
                rt.end(outputs={"error": error_msg})
                return error_msg

            category = manifest_item.category
            doc_id = manifest_item.id

            hierarchy_dict = _text_set.get_hierarchy_for_category(category.value)
            if hierarchy_dict is None:
                cat_label = localization.get_category_label(
                    category, language=_mcp_language
                )
                result = f"文件“{manifest_item.title}”属于扁平分类（{cat_label}），无层级归属。"
                rt.end(
                    outputs={"result": result, "category": category.value, "id": doc_id}
                )
                return result

            hierarchy = processed_types.Hierarchy.from_dict(hierarchy_dict)
            path = hierarchy_nav.find_leaf_path(hierarchy.nodes, doc_id)
            if path is None:
                result = f"文件“{manifest_item.title}”未在层级中找到对应位置。"
                rt.end(
                    outputs={"result": result, "category": category.value, "id": doc_id}
                )
                return result

            ancestors = path[:-1]
            current = path[-1]
            breadcrumb = " → ".join(_node_label(n) for n in [*ancestors, current])

            toc_root = hierarchy_nav.compute_toc(path)
            output_lines = [f"文件层级归属：", breadcrumb, ""]

            if toc_root is not None and toc_root.children:
                toc_title = _node_label(toc_root)
                output_lines.append(f"目录 — {toc_title}：")

                has_groups = any(c.children is not None for c in toc_root.children)
                for child in toc_root.children:
                    if has_groups:
                        group_label = _node_label(child)
                        if group_label:
                            output_lines.append(f"  {group_label}：")
                        sub_children = child.children or []
                    else:
                        sub_children = [child]

                    for leaf in sub_children:
                        assert leaf.file_id is not None
                        leaf_manifest = _text_set.get_manifest_item(
                            category, leaf.file_id
                        )
                        leaf_md5 = (
                            hashlib.md5(
                                leaf_manifest.relative_path.encode("utf-8")
                            ).hexdigest()
                            if leaf_manifest is not None
                            else "?"
                        )
                        marker = " ← 当前文件" if leaf.file_id == doc_id else ""
                        output_lines.append(
                            f"    - {leaf.title or _node_label(leaf)} (file_id: {leaf_md5}){marker}"
                        )
                output_lines.append("")
                output_lines.append(
                    "提示：如需获取某个文件的完整内容，请使用 get_file_content 工具，"
                )
                output_lines.append("传入上面结果中的 file_id 即可。")
            else:
                output_lines.append("（该文件无同级目录列表。）")

            formatted_output = "\n".join(output_lines)

            rt.end(
                outputs={
                    "file_id": file_id,
                    "category": category.value,
                    "id": doc_id,
                    "breadcrumb": breadcrumb,
                    "has_toc": toc_root is not None,
                    "output": formatted_output,
                }
            )

            return formatted_output

    except Exception as e:
        return f"获取文档层级时发生错误：{e}"


@mcp.tool()
def list_categories() -> str:
    """列出语料库中的所有分类及其文件数量

    返回所有可用分类的列表，每个分类包含其名称、本地化标签和文件数量。
    可用于浏览语料库结构，再配合 get_category_hierarchy 深入查看具体分类。

    返回：
    - 分类列表，每行包含分类名称、标签和文件数量
    """
    try:
        with ls.trace("mcp_list_categories", "chain") as rt:
            manifest = _text_set.get_manifest()
            category_counts: dict[str, int] = {}
            for item in manifest:
                cat_val = item.category.value
                category_counts[cat_val] = category_counts.get(cat_val, 0) + 1

            sorted_categories = sorted(category_counts.items())

            output_lines = [
                "语料库分类列表：",
                "=" * 60,
            ]
            for cat_val, count in sorted_categories:
                cat_enum = text_types.TextCategory(cat_val)
                label = localization.get_category_label(
                    cat_enum, language=_mcp_language
                )
                output_lines.append(f"  {cat_val} ({label}) — {count} 个文件")

            formatted_output = "\n".join(output_lines)

            rt.end(
                outputs={
                    "categories": [
                        {"value": v, "count": c} for v, c in sorted_categories
                    ],
                    "output": formatted_output,
                }
            )

            return formatted_output
    except Exception as e:
        return f"获取分类列表时发生错误：{e}"


@mcp.tool()
def get_category_hierarchy(category: str) -> str:
    """获取指定分类的层级结构

    对于有预建层级结构的分类（如任务 agd_quest、逸闻 agd_coop），返回多级树形结构，
    便于浏览内容组织方式。
    对于扁平分类（如阅读物 agd_readable、角色故事 agd_character_story 等），返回按ID
    排序的文件列表，每行包含标题和 file_id。

    参数：
    - category: 分类名称，例如 agd_quest、agd_readable、agd_character_story 等

    可通过 list_categories 获取所有可用的分类名称。
    """
    try:
        with ls.trace(
            "mcp_get_category_hierarchy",
            "chain",
            inputs={"category": category},
        ) as rt:
            hierarchy_dict = _text_set.get_hierarchy_for_category(category)

            if hierarchy_dict is not None:
                # Pre-baked hierarchy (quests, hangouts) — render multi-level tree
                hierarchy = processed_types.Hierarchy.from_dict(hierarchy_dict)
                output_lines = [f"分类“{category}”层级结构：", ""]

                def _render_node(
                    node: processed_types.HierarchyNode, indent: int = 0
                ) -> None:
                    prefix = "  " * indent
                    label = _node_label(node)
                    if node.children is not None:
                        output_lines.append(f"{prefix}{label}：")
                        for child in node.children:
                            _render_node(child, indent + 1)
                    else:
                        file_id_str: str = "?"
                        if node.file_id is not None:
                            leaf_manifest = _text_set.get_manifest_item(
                                text_types.TextCategory(category), node.file_id
                            )
                            if leaf_manifest is not None:
                                file_id_str = hashlib.md5(
                                    leaf_manifest.relative_path.encode("utf-8")
                                ).hexdigest()
                        output_lines.append(
                            f"{prefix}- {label} (file_id: {file_id_str})"
                        )

                for node in hierarchy.nodes:
                    _render_node(node)

                output_lines.extend(
                    [
                        "",
                        "提示：如需获取某个文件的完整内容，请使用 get_file_content 工具，",
                        "传入上面结果中的 file_id 即可。",
                    ]
                )

                formatted_output = "\n".join(output_lines)
                rt.end(
                    outputs={
                        "category": category,
                        "has_hierarchy": True,
                        "output": formatted_output,
                    }
                )
                return formatted_output

            # Flat category: synthesize a depth-1 list from the manifest.
            try:
                text_category = text_types.TextCategory(category)
            except ValueError:
                error_msg = (
                    f"错误：未知分类 '{category}'。请使用 list_categories"
                    " 查看所有可用分类。"
                )
                rt.end(outputs={"error": error_msg, "category": category})
                return error_msg

            items = sorted(
                (
                    item
                    for item in _text_set.get_manifest()
                    if item.category == text_category
                ),
                key=lambda item: item.id,
            )

            cat_label = localization.get_category_label(
                text_category, language=_mcp_language
            )
            output_lines = [
                f"分类“{cat_label}”（{category}）— 共 {len(items)} 个文件：",
                "",
            ]
            for item in items:
                file_id = hashlib.md5(item.relative_path.encode("utf-8")).hexdigest()
                output_lines.append(f"  - {item.title} (file_id: {file_id})")

            output_lines.extend(
                [
                    "",
                    "提示：如需获取某个文件的完整内容，请使用 get_file_content 工具，",
                    "传入上面结果中的 file_id 即可。",
                ]
            )

            formatted_output = "\n".join(output_lines)
            rt.end(
                outputs={
                    "category": category,
                    "has_hierarchy": False,
                    "item_count": len(items),
                    "output": formatted_output,
                }
            )
            return formatted_output

    except Exception as e:
        return f"获取层级结构时发生错误：{e}"


if __name__ == "__main__":
    mcp.run()
