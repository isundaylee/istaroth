from istaroth.rag import text_set
from istaroth.rag.document_store import Document


def _get_file_note(ts: text_set.TextSet, path: str) -> str:
    """Look up the category note for a file via the manifest."""
    metadata = ts.get_manifest_item_by_relative_path(path)
    if metadata is None:
        raise ValueError(f"No manifest entry for retrieved document path: {path}")
    return metadata.category.get_note()


def render_retrieve_output(
    r: list[tuple[float, list[Document]]], *, text_set: text_set.TextSet
) -> str:
    if not r:
        return "未找到相关文档。"

    parts = list[str]()

    for i, (score, file_docs) in enumerate(r):
        file_id = file_docs[0].metadata["file_id"]
        chunk_start = file_docs[0].metadata["chunk_index"]
        chunk_end = file_docs[-1].metadata["chunk_index"]

        parts.append("#" * 80)
        parts.append(
            f"# 文件 {i + 1} "
            f"(相关性分数: {score:.4f}, "
            f"文件ID: {file_id}, "
            f"文件片段序号: ck{chunk_start} 到 ck{chunk_end}):\n"
        )

        parts.append(
            f"# 【注意：{_get_file_note(text_set, file_docs[0].metadata['path'])}】\n"
        )

        last_chunk_index: int | None = None
        for doc in file_docs:
            chunk_index = doc.metadata["chunk_index"]
            if last_chunk_index is not None and chunk_index != last_chunk_index + 1:
                parts.append(
                    f"（注意：文件片段 ck{last_chunk_index} 和 ck{chunk_index} 之间有省略）\n"
                )
            last_chunk_index = chunk_index

            parts.append(
                f"------------------- 文件ID {file_id} 片段 ck{chunk_index}:\n"
            )
            parts.append(doc.page_content)
            parts.append("\n")

    return "\n".join(parts) + "\n"
