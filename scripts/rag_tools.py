#!/usr/bin/env python3
"""RAG tools for document management and querying."""

import datetime
import hashlib
import json
import logging
import pathlib
import shutil
import sys

import click

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import langsmith as ls

from istaroth import llm_manager, utils
from istaroth.agd import localization
from istaroth.rag import document_store, output_rendering, pipeline, retrieval_diff
from istaroth.rag.eval import dataset

logger = logging.getLogger(__name__)


def _get_files_to_process(text_path: pathlib.Path) -> list[pathlib.Path]:
    """Get a list of .txt files to process from the given path."""
    assert text_path.is_dir(), f"Path {text_path} must be a directory"
    return list(text_path.glob("**/*.txt"))


def _load_or_create_store() -> document_store.DocumentStore:
    """Load existing document store or create new one."""
    store = document_store.DocumentStore.from_env()
    if store.num_documents > 0:
        logger.info("Loaded store with %d existing documents", store.num_documents)
    return store


@click.group()
def cli() -> None:
    """RAG tools for document management and querying."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)-35s %(message)s",
        datefmt="%Y%m%d %H:%M:%S",
    )


@cli.command()
@click.argument("text_path", type=pathlib.Path)
@click.argument("checkpoint_path", type=pathlib.Path)
@click.option("-f", "--force", is_flag=True, help="Delete target if it exists")
def build(text_path: pathlib.Path, checkpoint_path: pathlib.Path, force: bool) -> None:
    """Build document store from a file or folder."""
    # Check if target exists
    if checkpoint_path.exists():
        if not force:
            logger.error(
                "Target %s already exists. Use -f to overwrite.", checkpoint_path
            )
            sys.exit(1)
        else:
            logger.info("Removing existing target: %s", checkpoint_path)
            shutil.rmtree(checkpoint_path)

    files_to_process = _get_files_to_process(text_path)

    if not files_to_process:
        logger.error("No .txt files found to process.")
        sys.exit(1)

    metadata = json.loads((text_path / "metadata.json").read_text())

    match localization.Language(metadata["language"]):
        case localization.Language.CHS:
            chunk_size_multiplier = 1.0
        case localization.Language.ENG:
            chunk_size_multiplier = 3.5
        case _:
            raise RuntimeError(f"Unsupported language: {metadata['language']}.")

    logger.info(
        "Building document store from %d files in: %s", len(files_to_process), text_path
    )
    store = document_store.DocumentStore.build(
        files_to_process,
        chunk_size_multiplier=chunk_size_multiplier,
        show_progress=True,
    )

    logger.info("Total documents in store: %d", store.num_documents)

    checkpoint_path.mkdir(parents=True, exist_ok=True)
    store.save(checkpoint_path)


@cli.command()
@click.argument("query", type=str)
@click.option("-k", "--k", default=5, help="Number of results to return")
@click.option("-c", "--chunk-context", default=5, help="Context size for each chunk")
@click.option("--save", type=pathlib.Path)
def retrieve(
    query: str, *, k: int, chunk_context: int, save: pathlib.Path | None
) -> None:
    """Retrieve similar documents from the document store."""

    with ls.trace(
        "rag_tools_retrieve",
        "chain",
        inputs={"query": query, "k": k, "chunk_context": chunk_context},
    ) as rt:
        store = _load_or_create_store()

        if store.num_documents == 0:
            logger.error("No documents in store. Use 'add-documents' command first.")
            sys.exit(1)

        logger.info("Searching for: '%s'", query)
        retrieve_output = store.retrieve(query, k=k, chunk_context=chunk_context)

        if not retrieve_output.results:
            logger.info("No results found.")
            return

        formatted_output = output_rendering.render_retrieve_output(
            retrieve_output.results
        )
        rt.end(outputs=retrieve_output.to_langsmith_output(formatted_output))

        if save is not None:
            save_path = save / (
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
                + utils.make_safe_filename_part(query, max_length=50)
                + ".txt"
            )
            save_path.write_text(json.dumps(retrieve_output.to_dict()))

        print(formatted_output)


@cli.command()
@click.argument("output", type=pathlib.Path)
@click.option("-k", "--k", default=5, help="Number of results to return")
@click.option("-c", "--chunk-context", default=5, help="Context size for each chunk")
def retrieve_eval(output: pathlib.Path, *, k: int, chunk_context: int) -> None:
    """Evaluate retrieval on a fixed dataset and save into the output path."""

    store = _load_or_create_store()

    for query in dataset.RETRIEVAL_QUESTIONS:
        with ls.trace(
            "rag_tools_retrieve_eval",
            "chain",
            inputs={"query": query, "k": k, "chunk_context": chunk_context},
        ) as rt:
            retrieve_output = store.retrieve(query, k=k, chunk_context=chunk_context)
            rt.end(outputs=retrieve_output.to_langsmith_output(None))

            query_hash = hashlib.md5(query.encode()).hexdigest()
            output.mkdir(parents=True, exist_ok=True)
            (output / f"{query_hash}.json").write_text(
                json.dumps(retrieve_output.to_dict())
            )


@cli.command()
@click.argument("question", type=str)
@click.option("--k", default=10)
@click.option("--chunk-context", default=10)
def query(question: str, *, k: int, chunk_context: int) -> None:
    """Answer a question using RAG pipeline."""
    store = _load_or_create_store()

    if store.num_documents == 0:
        logger.error("No documents in store.")
        sys.exit(1)

    print(f"问题: {question}")
    print("=" * 50)

    # Create RAG pipeline and LLM
    lm = llm_manager.LLMManager()

    rag = pipeline.RAGPipeline(
        store,
        language=localization.Language.CHS,
        llm=lm.get_default_llm(),
        preprocessing_llm=lm.get_llm("gemini-2.5-flash-lite"),
    )

    answer = rag.answer(question, k=k, chunk_context=chunk_context)
    print(f"回答: {answer}")


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.option(
    "--chunk-size-multiplier", default=1.0, type=float, help="Multiplier for chunk size"
)
def chunk_stats(path: pathlib.Path, *, chunk_size_multiplier: float) -> None:
    """Show statistics about document chunks from a file or folder."""
    files_to_process = _get_files_to_process(path)

    if not files_to_process:
        logger.error("No .txt files found to process.")
        sys.exit(1)

    logger.info("Analyzing chunks from %d files...", len(files_to_process))

    # Chunk the documents
    all_documents = document_store.chunk_documents(
        files_to_process,
        chunk_size_multiplier=chunk_size_multiplier,
        show_progress=True,
    )

    # Collect chunk lengths and content
    chunk_data = []
    file_count = len(all_documents)

    for file_docs in all_documents.values():
        for doc in file_docs.values():
            chunk_data.append((len(doc.page_content), doc.page_content))

    chunk_lengths = [length for length, _ in chunk_data]

    if not chunk_lengths:
        print("No chunks were generated.")
        return

    # Calculate distribution (bins of 50 characters) and collect examples
    bins: dict[int, int] = {}
    bin_examples: dict[int, list[str]] = {}
    bin_size = 50
    for length, content in chunk_data:
        bin_key = (length // bin_size) * bin_size
        bins[bin_key] = bins.get(bin_key, 0) + 1
        if bin_key not in bin_examples:
            bin_examples[bin_key] = []
        if len(bin_examples[bin_key]) < 3:
            bin_examples[bin_key].append(content)

    # Display statistics
    print("\nDocument Chunk Statistics")
    print("=" * 40)
    print(f"Total files: {file_count}")
    print(f"Total chunks: {len(chunk_lengths)}")
    print(
        f"Average chunk length: {sum(chunk_lengths) / len(chunk_lengths):.1f} characters"
    )
    print(f"Sum chunk length: {sum(chunk_lengths):.1f} characters")
    print(f"Min chunk length: {min(chunk_lengths)} characters")
    print(f"Max chunk length: {max(chunk_lengths)} characters")

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

    print("\nExamples by Size Range:")
    print("=" * 60)
    for bin_start in sorted(bin_examples.keys()):
        print(
            f"\n{bin_start}-{bin_start + bin_size - 1} characters ({bins[bin_start]} chunks):"
        )
        print("-" * 30)

        for i, example in enumerate(bin_examples[bin_start], 1):
            print(f"Example {i}:")
            print("─" * 80)
            print(example)
            print("─" * 80)
            print()


@cli.command("chunk-file")
@click.argument("file", type=click.Path(exists=True, path_type=pathlib.Path))
@click.option(
    "--chunk-size-multiplier", default=1.0, type=float, help="Multiplier for chunk size"
)
def chunk_file(file: pathlib.Path, *, chunk_size_multiplier: float) -> None:
    """Chunk a single text file and print individual chunks."""
    if not file.is_file() or file.suffix != ".txt":
        logger.error("%s must be a .txt file", file)
        sys.exit(1)

    logger.info("Chunking file: %s", file)
    print("=" * 60)

    # Use the existing chunk_documents function from document_store
    all_documents = document_store.chunk_documents(
        [file], chunk_size_multiplier=chunk_size_multiplier
    )

    # Get the documents for this file
    file_id = list(all_documents.keys())[0]
    file_documents = all_documents[file_id]

    # Print each chunk
    for chunk_index, doc in file_documents.items():
        chunk_content = doc.page_content
        print(f"\n--- Chunk {chunk_index + 1} (length: {len(chunk_content)} chars) ---")
        print(chunk_content)
        print("-" * 60)

    # Print summary
    chunks_list = [doc.page_content for doc in file_documents.values()]
    print(f"\nSummary:")
    print(f"  Total chunks: {len(chunks_list)}")
    print(
        f"  Average chunk size: {sum(len(c) for c in chunks_list) / len(chunks_list):.1f} chars"
    )
    print(f"  Min chunk size: {min(len(c) for c in chunks_list)} chars")
    print(f"  Max chunk size: {max(len(c) for c in chunks_list)} chars")


@cli.command("diff-retrieval")
@click.argument("file1", type=click.Path(exists=True, path_type=pathlib.Path))
@click.argument("file2", type=click.Path(exists=True, path_type=pathlib.Path))
def diff_retrieval(file1: pathlib.Path, file2: pathlib.Path) -> None:
    """Compare two retrieval result files and show differences."""
    # Load and compare the JSON files
    json1 = json.loads(file1.read_text())
    json2 = json.loads(file2.read_text())

    # Create the diff object
    diff = retrieval_diff.compare_retrievals(
        json1, json2, filename1=file1.name, filename2=file2.name
    )

    # Render all sections
    print(retrieval_diff.render_comparison_headers(diff))
    print()
    print(retrieval_diff.render_document_sections(diff))
    print()
    print(retrieval_diff.render_summary_table(diff))
    print()
    print(retrieval_diff.render_final_summary(diff))


if __name__ == "__main__":
    cli()
