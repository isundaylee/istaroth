"""Retrieval result comparison and analysis functionality."""

from __future__ import annotations

import json
import pathlib
from typing import Any, TypeAlias

import attrs
from langchain_core.documents import Document
from tabulate import tabulate

from istaroth.rag import types

# Type alias for document chunk identifier (file_id, chunk_index)
_ChunkKey: TypeAlias = tuple[str, int]

# Constants for formatting
_SECTION_DIVIDER_WIDTH = 80
_CONTENT_EXCERPT_LENGTH = 50
_CONTENT_TRUNCATE_LENGTH = 200
_SCORE_CONTENT_TRUNCATE_LENGTH = 100
_MAX_SCORE_DIFFS_SHOWN = 5


@attrs.define
class RetrievalDiff:
    """Comparison result between two retrieval outputs."""

    # Filenames for display
    filename1: str
    filename2: str

    # Metadata from both files
    meta1: dict[str, Any]
    meta2: dict[str, Any]

    # Document sets (using (file_id, chunk_index) as identifier)
    docs1: set[_ChunkKey]
    docs2: set[_ChunkKey]
    common: set[_ChunkKey]
    only_in_1: set[_ChunkKey]
    only_in_2: set[_ChunkKey]

    # Document information mappings
    info1: dict[_ChunkKey, Document]
    info2: dict[_ChunkKey, Document]

    # Rank mappings for documents
    ranks1: dict[_ChunkKey, int]
    ranks2: dict[_ChunkKey, int]


def _load_retrieval_json(
    file_path: pathlib.Path,
) -> tuple[dict[str, Any], types.RetrieveOutput]:
    """Load a retrieval JSON file and return metadata and results."""
    data = json.loads(file_path.read_text())
    query_info = data["query"]
    env_info = data["env"]
    results = types.RetrieveOutput.from_dict(data["results"])
    metadata = {
        "query": query_info,
        "env": env_info,
        "filename": file_path.name,
    }
    return metadata, results


def _get_document_id_set(results: types.RetrieveOutput) -> set[_ChunkKey]:
    """Extract all document (file_id, chunk_index) identifiers from results."""
    id_set = set()
    for _, documents in results.results:
        for doc in documents:
            file_id = doc.metadata["file_id"]
            chunk_index = doc.metadata["chunk_index"]
            id_set.add((file_id, chunk_index))
    return id_set


def _collect_document_info(results: types.RetrieveOutput) -> dict[_ChunkKey, Document]:
    """Collect document info: (file_id, chunk_index) -> Document."""
    doc_info = {}
    for _, documents in results.results:
        for doc in documents:
            file_id = doc.metadata["file_id"]
            chunk_index = doc.metadata["chunk_index"]
            doc_info[(file_id, chunk_index)] = doc
    return doc_info


def _create_document_rank_map(results: types.RetrieveOutput) -> dict[_ChunkKey, int]:
    """Map document (file_id, chunk_index) to its rank (1-based)."""
    # Collect all documents with their scores
    all_docs = []
    for score, documents in results.results:
        for doc in documents:
            file_id = doc.metadata["file_id"]
            chunk_index = doc.metadata["chunk_index"]
            doc_id = (file_id, chunk_index)
            all_docs.append((score, doc_id))

    # Sort by score (descending) to get ranking
    all_docs.sort(key=lambda x: x[0], reverse=True)

    # Create rank mapping
    doc_ranks = {}
    for rank, (_, doc_id) in enumerate(all_docs, 1):
        doc_ranks[doc_id] = rank

    return doc_ranks


def compare_retrievals(
    json1: dict[str, Any], json2: dict[str, Any], *, filename1: str, filename2: str
) -> RetrievalDiff:
    """Compare two retrieval JSON objects and return a RetrievalDiff."""
    # Parse metadata and results
    meta1 = {
        "query": json1["query"],
        "env": json1["env"],
    }
    meta2 = {
        "query": json2["query"],
        "env": json2["env"],
    }

    results1 = types.RetrieveOutput.from_dict(json1)
    results2 = types.RetrieveOutput.from_dict(json2)

    # Extract document ID sets
    docs1 = _get_document_id_set(results1)
    docs2 = _get_document_id_set(results2)

    # Find differences
    common = docs1 & docs2
    only_in_1 = docs1 - docs2
    only_in_2 = docs2 - docs1

    # Collect document information
    info1 = _collect_document_info(results1)
    info2 = _collect_document_info(results2)

    # Create rank mappings
    ranks1 = _create_document_rank_map(results1)
    ranks2 = _create_document_rank_map(results2)

    return RetrievalDiff(
        filename1=filename1,
        filename2=filename2,
        meta1=meta1,
        meta2=meta2,
        docs1=docs1,
        docs2=docs2,
        common=common,
        only_in_1=only_in_1,
        only_in_2=only_in_2,
        info1=info1,
        info2=info2,
        ranks1=ranks1,
        ranks2=ranks2,
    )


def render_summary_table(diff: RetrievalDiff) -> str:
    """Render the summary table for a RetrievalDiff."""
    lines = []
    lines.append("📋 Summary Table:")
    lines.append("=" * _SECTION_DIVIDER_WIDTH)

    # Get all unique document IDs
    all_doc_ids = diff.docs1 | diff.docs2

    # Create table data
    table_data = []
    for doc_id in sorted(all_doc_ids):  # Sort by (file_id, chunk_index)
        file_id, chunk_index = doc_id

        # Determine which files contain this document
        in_file1 = doc_id in diff.docs1
        in_file2 = doc_id in diff.docs2
        is_common = in_file1 and in_file2

        # Get document (prefer file1 if available, otherwise file2)
        if in_file1:
            doc = diff.info1[doc_id]
        else:
            doc = diff.info2[doc_id]

        # Create excerpt (first 50 chars)
        content = doc.page_content
        excerpt = content.replace("\n", " ").strip()
        if len(excerpt) > _CONTENT_EXCERPT_LENGTH:
            excerpt = excerpt[: _CONTENT_EXCERPT_LENGTH - 3] + "..."

        # Calculate rank difference for common documents
        rank_diff = ""
        if is_common and doc_id in diff.ranks1 and doc_id in diff.ranks2:
            diff_val = (
                diff.ranks2[doc_id] - diff.ranks1[doc_id]
            )  # positive means higher rank in file1
            rank_diff = f"{diff_val:+d}" if diff_val != 0 else "0"

        table_data.append(
            [
                file_id,
                chunk_index,
                "✓" if is_common else "",
                "✓" if (in_file1 and not in_file2) else "",
                "✓" if (in_file2 and not in_file1) else "",
                rank_diff,
                excerpt,
            ]
        )

    # Create table with headers
    headers = [
        "File ID",
        "Chunk",
        "Common",
        "Only-A",
        "Only-B",
        "Rank Diff",
        "Content Excerpt",
    ]
    table = tabulate(table_data, headers=headers)

    lines.append(table)
    return "\n".join(lines)


def _render_document_list(
    doc_ids: set[_ChunkKey], doc_info: dict[_ChunkKey, Document], title: str
) -> list[str]:
    """Helper function to render a list of documents with consistent formatting."""
    lines = []
    if doc_ids:
        lines.append(f"📄 {title} ({len(doc_ids)} documents):")
        lines.append("-" * _SECTION_DIVIDER_WIDTH)
        for i, doc_id in enumerate(sorted(doc_ids), 1):
            doc = doc_info[doc_id]
            content = doc.page_content
            # Split into lines and indent continuation lines
            content_lines = content.split("\n")
            lines.append(f"{i:2d}. {content_lines[0]}")
            for line in content_lines[1:]:
                lines.append(f"    {line}")
            if i < len(
                doc_ids
            ):  # Add empty line between documents except after the last one
                lines.append("")
        # Add empty line after section
        lines.append("")
    return lines


def render_document_sections(diff: RetrievalDiff) -> str:
    """Render the detailed document sections showing unique documents."""
    lines = []

    # Show documents only in file 1
    lines.extend(
        _render_document_list(diff.only_in_1, diff.info1, f"Documents only in File A")
    )

    # Show documents only in file 2
    lines.extend(
        _render_document_list(diff.only_in_2, diff.info2, f"Documents only in File B")
    )

    # Show rank comparison for common documents
    if diff.common and diff.ranks1 and diff.ranks2:
        lines.append("📊 Rank Comparison for Common Documents:")
        lines.append("-" * _SECTION_DIVIDER_WIDTH)

        rank_diffs = []
        for doc_id in diff.common:
            if doc_id in diff.ranks1 and doc_id in diff.ranks2:
                diff_val = (
                    diff.ranks2[doc_id] - diff.ranks1[doc_id]
                )  # positive means higher rank in file1
                # Get the document content for display
                doc = diff.info1[doc_id] if doc_id in diff.info1 else diff.info2[doc_id]
                content = doc.page_content
                rank_diffs.append(
                    (diff_val, content, diff.ranks1[doc_id], diff.ranks2[doc_id])
                )

        # Sort by rank difference (largest absolute difference first)
        rank_diffs.sort(key=lambda x: abs(x[0]), reverse=True)

        # Show top 5 rank differences
        for i, (diff_val, content, rank1, rank2) in enumerate(
            rank_diffs[:_MAX_SCORE_DIFFS_SHOWN], 1
        ):
            if diff_val > 0:
                direction = f"ranked {diff_val} positions higher in File B"
            elif diff_val < 0:
                direction = f"ranked {abs(diff_val)} positions higher in File A"
            else:
                direction = "same rank"

            lines.append(
                f"{i:2d}. Rank diff: {diff_val:+d} (#{rank1} vs #{rank2}) - {direction}"
            )
            # Split into lines and indent continuation lines
            content_lines = content.split("\n")
            lines.append(f"    {content_lines[0]}")
            for line in content_lines[1:]:
                lines.append(f"    {line}")
            if i < len(
                rank_diffs[:_MAX_SCORE_DIFFS_SHOWN]
            ):  # Add empty line between documents except after the last one
                lines.append("")
        # Add empty line after section
        if rank_diffs:
            lines.append("")

    return "\n".join(lines)


def render_comparison_headers(diff: RetrievalDiff) -> str:
    """Render the query and environment comparison headers."""
    lines = []

    lines.append(f"Comparing retrieval results:")
    lines.append(f"File A: {diff.filename1}")
    lines.append(f"File B: {diff.filename2}")
    lines.append("=" * _SECTION_DIVIDER_WIDTH)

    # Compare query parameters
    lines.append("")
    lines.append("Query Comparison:")
    lines.append("-" * 80)
    if diff.meta1["query"] == diff.meta2["query"]:
        lines.append("✓ Same query parameters")
        lines.append(f"  Query: {diff.meta1['query']['query']}")
        lines.append(
            f"  k: {diff.meta1['query']['k']}, chunk_context: {diff.meta1['query']['chunk_context']}"
        )
    else:
        lines.append("✗ Different query parameters")
        lines.append(
            f"  File A - Query: {diff.meta1['query']['query']}, k: {diff.meta1['query']['k']}, chunk_context: {diff.meta1['query']['chunk_context']}"
        )
        lines.append(
            f"  File B - Query: {diff.meta2['query']['query']}, k: {diff.meta2['query']['k']}, chunk_context: {diff.meta2['query']['chunk_context']}"
        )

    # Compare environment settings
    lines.append("")
    lines.append("Environment Comparison:")
    lines.append("-" * 80)
    env_keys = set(diff.meta1["env"].keys()) | set(diff.meta2["env"].keys())
    env_diff = False
    for key in sorted(env_keys):
        val1 = diff.meta1["env"].get(key, "<not set>")
        val2 = diff.meta2["env"].get(key, "<not set>")
        if val1 != val2:
            lines.append(f"✗ {key}: '{val1}' vs '{val2}'")
            env_diff = True
    if not env_diff:
        lines.append("✓ Same environment settings")

    # Document comparison statistics
    lines.append("")
    lines.append("Document Comparison:")
    lines.append("-" * 80)
    lines.append(f"Total documents in File A: {len(diff.docs1)}")
    lines.append(f"Total documents in File B: {len(diff.docs2)}")
    lines.append(f"Common documents: {len(diff.common)}")
    lines.append(f"Only in File A: {len(diff.only_in_1)}")
    lines.append(f"Only in File B: {len(diff.only_in_2)}")

    return "\n".join(lines)


def render_final_summary(diff: RetrievalDiff) -> str:
    """Render the final summary section."""
    lines = []

    lines.append("Summary:")
    lines.append("=" * _SECTION_DIVIDER_WIDTH)
    if len(diff.only_in_1) == 0 and len(diff.only_in_2) == 0:
        lines.append("✓ Both files contain identical document sets")
    else:
        lines.append("✗ Document sets differ:")
        lines.append(f"  - {len(diff.only_in_1)} documents unique to File A")
        lines.append(f"  - {len(diff.only_in_2)} documents unique to File B")
        lines.append(f"  - {len(diff.common)} documents in common")

    return "\n".join(lines)
