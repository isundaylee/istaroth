#!/usr/bin/env python3
"""RAG tools for document management and querying."""

import json
import logging
import pathlib
import re
import shutil
import sys

import click

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from langchain_google_genai import llms as google_llms

from istaroth.agd import localization
from istaroth.rag import document_store, output_rendering, pipeline, tracing


def _create_llm() -> google_llms.GoogleGenerativeAI:
    """Create Google Gemini LLM instance."""
    return google_llms.GoogleGenerativeAI(model="gemini-2.5-flash")


def _get_files_to_process(path: pathlib.Path) -> list[pathlib.Path]:
    """Get a list of .txt files to process from the given path."""
    if path.is_file():
        if path.suffix != ".txt":
            print(f"Error: File {path} is not a .txt file.")
            sys.exit(1)
        return [path]
    elif path.is_dir():
        return list(path.glob("**/*.txt"))
    else:
        print(f"Error: Path {path} is neither a file nor a directory.")
        sys.exit(1)


def _load_or_create_store() -> document_store.DocumentStore:
    """Load existing document store or create new one."""
    store = document_store.DocumentStore.from_env()
    if store.num_documents > 0:
        print(f"Loaded store with {store.num_documents} existing documents")
    return store


@click.group()  # type: ignore[misc]
def cli() -> None:
    """RAG tools for document management and querying."""
    pass


@cli.command()  # type: ignore[misc]
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))  # type: ignore[misc]
@click.option("-f", "--force", is_flag=True, help="Delete target if it exists")  # type: ignore[misc]
def build(path: pathlib.Path, force: bool) -> None:
    """Build document store from a file or folder."""
    # Get target path from environment
    target_path = document_store.get_document_store_path()

    # Check if target exists
    if target_path.exists():
        if not force:
            print(f"Error: Target {target_path} already exists. Use -f to overwrite.")
            sys.exit(1)
        else:
            print(f"Removing existing target: {target_path}")
            shutil.rmtree(target_path)

    files_to_process = _get_files_to_process(path)

    if not files_to_process:
        print("Error: No .txt files found to process.")
        sys.exit(1)

    metadata = json.loads((path / "metadata.json").read_text())

    match localization.Language(metadata["language"]):
        case localization.Language.CHS:
            chunk_size_multiplier = 1.0
        case localization.Language.ENG:
            chunk_size_multiplier = 3.5
        case _:
            raise RuntimeError(f"Unsupported language: {metadata['language']}.")

    print(f"Building document store from {len(files_to_process)} files in: {path}")
    store = document_store.DocumentStore.build(
        files_to_process,
        chunk_size_multiplier=chunk_size_multiplier,
        show_progress=True,
    )

    print(f"\nTotal documents in store: {store.num_documents}")
    store.save_to_env()


@cli.command()  # type: ignore[misc]
@click.argument("query", type=str)  # type: ignore[misc]
@click.option("-k", "--k", default=5, help="Number of results to return")  # type: ignore[misc]
@click.option("-c", "--chunk-context", default=5, help="Context size for each chunk")  # type: ignore[misc]
def retrieve(query: str, *, k: int, chunk_context: int) -> None:
    """Retrieve similar documents from the document store."""
    store = _load_or_create_store()

    if store.num_documents == 0:
        print("Error: No documents in store. Use 'add-documents' command first.")
        sys.exit(1)

    print(f"Searching for: '{query}'\n")
    retrieve_output = store.retrieve(query, k=k, chunk_context=chunk_context)

    if not retrieve_output.results:
        print("No results found.")
        return

    print(output_rendering.render_retrieve_output(retrieve_output.results))


@cli.command()  # type: ignore[misc]
@click.argument("question", type=str)  # type: ignore[misc]
@click.option("--k", default=5, help="Number of documents to retrieve")  # type: ignore[misc]
@click.option("--show-sources", is_flag=True, help="Show source documents")  # type: ignore[misc]
def query(question: str, k: int, show_sources: bool) -> None:
    """Answer a question using RAG pipeline."""
    store = _load_or_create_store()

    if store.num_documents == 0:
        print("Error: No documents in store. Use 'add-documents' command first.")
        sys.exit(1)

    print(f"问题: {question}")
    print("=" * 50)

    # Create RAG pipeline with Google Gemini
    llm = _create_llm()
    rag = pipeline.RAGPipeline(store, llm=llm, k=k)

    result = rag.answer_with_sources(question)
    print(f"回答: {result.answer}")

    if show_sources and result.sources:
        print(f"\n使用的资料源 ({len(result.sources)} 个):")
        for source in result.sources:
            print(f"\n【资料{source.index}】(相似度: {source.score:.4f})")
            print(f"{source.content[:200]}...")

    # Show trace URL if tracing is enabled
    if tracing.is_tracing_enabled():
        trace_url = tracing.get_trace_url()
        if trace_url:
            print(f"\n🔗 View traces: {trace_url}")


@cli.command()  # type: ignore[misc]
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--chunk-size-multiplier", default=1.0, type=float, help="Multiplier for chunk size")  # type: ignore[misc]
def chunk_stats(path: pathlib.Path, *, chunk_size_multiplier: float) -> None:
    """Show statistics about document chunks from a file or folder."""
    files_to_process = _get_files_to_process(path)

    if not files_to_process:
        print("Error: No .txt files found to process.")
        sys.exit(1)

    print(f"Analyzing chunks from {len(files_to_process)} files...")

    # Chunk the documents
    all_documents = document_store.chunk_documents(
        files_to_process,
        chunk_size_multiplier=chunk_size_multiplier,
        show_progress=True,
    )

    # Collect chunk lengths
    chunk_lengths = []
    file_count = len(all_documents)

    for file_docs in all_documents.values():
        for doc in file_docs.values():
            chunk_lengths.append(len(doc.page_content))

    if not chunk_lengths:
        print("No chunks were generated.")
        return

    # Calculate statistics
    total_chunks = len(chunk_lengths)
    avg_length = sum(chunk_lengths) / total_chunks
    min_length = min(chunk_lengths)
    max_length = max(chunk_lengths)

    # Calculate distribution (bins of 50 characters)
    bins: dict[int, int] = {}
    bin_size = 50
    for length in chunk_lengths:
        bin_key = (length // bin_size) * bin_size
        if bin_key in bins:
            bins[bin_key] += 1
        else:
            bins[bin_key] = 1

    # Display statistics
    print("\nDocument Chunk Statistics")
    print("=" * 40)
    print(f"Total files: {file_count}")
    print(f"Total chunks: {total_chunks}")
    print(f"Average chunk length: {avg_length:.1f} characters")
    print(f"Min chunk length: {min_length} characters")
    print(f"Max chunk length: {max_length} characters")

    print("\nLength Distribution:")
    print("-" * 40)

    # Sort bins and display histogram
    max_count = max(bins.values())
    for bin_start in sorted(bins.keys()):
        bin_end = bin_start + bin_size - 1
        count = bins[bin_start]
        bar_length = int((count / max_count) * 40)
        bar = "█" * bar_length
        print(f"{bin_start:3d}-{bin_end:3d}: {bar} {count:4d} chunks")

    # Calculate percentiles
    sorted_lengths = sorted(chunk_lengths)
    p25 = sorted_lengths[len(sorted_lengths) // 4]
    p50 = sorted_lengths[len(sorted_lengths) // 2]
    p75 = sorted_lengths[3 * len(sorted_lengths) // 4]

    print("\nPercentiles:")
    print("-" * 40)
    print(f"25th percentile: {p25} characters")
    print(f"50th percentile (median): {p50} characters")
    print(f"75th percentile: {p75} characters")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)-35s %(message)s",
        datefmt="%Y%m%d %H:%M:%S",
    )

    cli()
