from istaroth.rag.document_store import Document


def render_retrieve_output(r: list[tuple[float, list[Document]]]) -> str:
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

        last_chunk_index: int | None = None
        for doc in file_docs:
            chunk_index = doc.metadata["chunk_index"]
            if last_chunk_index is not None and chunk_index != last_chunk_index + 1:
                parts.append(
                    f"（注意：文件片段 ck{last_chunk_index} 和 ck{chunk_index} 之间有省略）\n"
                )
            last_chunk_index = chunk_index

            parts.append(f"------------------- 文件片段 ck{chunk_index}:\n")
            parts.append(doc.page_content)
            parts.append("\n")

    return "\n".join(parts) + "\n"
