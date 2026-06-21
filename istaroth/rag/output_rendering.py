import copy
from typing import cast

from langchain_core.documents import Document

from istaroth.rag import text_set, types


def _deduplicate_chunk_overlaps(docs: list[Document]) -> list[Document]:
    """Remove overlapping content between consecutive chunks using character indexes.

    When chunks are created with overlapping windows, consecutive chunks from the
    same file may contain duplicate content. This trims the beginning of each
    subsequent chunk so there is no overlap with the previous chunk's end position.
    """
    if len(docs) <= 1:
        return docs

    result: list[Document] = [docs[0]]

    for i in range(1, len(docs)):
        prev_meta = cast(types.DocumentMetadata, docs[i - 1].metadata)
        curr_meta = cast(types.DocumentMetadata, docs[i].metadata)

        overlap = prev_meta["end_index"] - curr_meta["start_index"]

        if overlap <= 0:
            result.append(docs[i])
            continue

        content = docs[i].page_content
        if overlap < len(content):
            trimmed_content = content[overlap:]
        else:
            trimmed_content = ""

        result.append(
            Document(
                page_content=trimmed_content,
                metadata=copy.deepcopy(docs[i].metadata),
            )
        )

    return result


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
        file_docs = _deduplicate_chunk_overlaps(file_docs)
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
