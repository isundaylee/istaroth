#!/usr/bin/env python3
"""RAG tools for document management and querying."""

import os
import pathlib
import sys

import click
from tqdm import tqdm

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from langchain_google_genai import llms as google_llms

from istorath.rag import embedding, pipeline


def _create_llm() -> google_llms.GoogleGenerativeAI:
    """Create Google Gemini LLM instance."""
    return google_llms.GoogleGenerativeAI(model="gemini-2.5-flash")


def _get_document_store_path() -> pathlib.Path:
    """Get document store path from environment variable."""
    path_str = os.getenv("ISTORATH_DOCUMENT_STORE")
    if not path_str:
        print("Error: ISTORATH_DOCUMENT_STORE environment variable is required.")
        print(
            "Please set it to the path where you want to store the document database."
        )
        sys.exit(1)
    return pathlib.Path(path_str)


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


def _load_or_create_store() -> embedding.DocumentStore:
    """Load existing document store or create new one."""
    store = embedding.DocumentStore()
    store_path = _get_document_store_path()

    if store_path.exists():
        print(f"Loading existing document store from: {store_path}")
        try:
            store.load(store_path)
            print(f"Loaded store with {store.num_documents} existing documents")
        except Exception as e:
            print(f"Error loading document store: {e}")
            sys.exit(1)

    return store


def _save_store(store: embedding.DocumentStore) -> None:
    """Save document store."""
    store_path = _get_document_store_path()
    print(f"Saving document store to: {store_path}")
    try:
        store_path.mkdir(parents=True, exist_ok=True)
        store.save(store_path)
    except Exception as e:
        print(f"Error saving document store: {e}")
        sys.exit(1)


@click.group()  # type: ignore[misc]
def cli() -> None:
    """RAG tools for document management and querying."""
    pass


@cli.command()  # type: ignore[misc]
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))  # type: ignore[misc]
def add_documents(path: pathlib.Path) -> None:
    """Add documents from a file or folder to the document store."""
    store = _load_or_create_store()

    try:
        files_to_process = _get_files_to_process(path)

        if not files_to_process:
            print("Error: No .txt files found to process.")
            sys.exit(1)

        print(f"Processing {len(files_to_process)} files from: {path}")
        with tqdm(files_to_process, desc="Adding documents", unit="file") as pbar:
            for file_path in pbar:
                if not store.add_file(file_path):
                    tqdm.write(f"Skipped {file_path.name} (already added)")

    finally:
        print(f"\nTotal documents in store: {store.num_documents}")
        _save_store(store)


@cli.command()  # type: ignore[misc]
@click.argument("query", type=str)  # type: ignore[misc]
@click.option("--k", default=5, help="Number of results to return")  # type: ignore[misc]
def retrieve(query: str, k: int) -> None:
    """Retrieve similar documents from the document store."""
    store = _load_or_create_store()

    if store.num_documents == 0:
        print("Error: No documents in store. Use 'add-documents' command first.")
        sys.exit(1)

    print(f"Searching for: '{query}'")
    results = store.search(query, k=k)

    if not results:
        print("No results found.")
        return

    for i, (text, score) in enumerate(results):
        print(f"\nResult {i + 1} (score: {score:.4f}):")
        print(f"  Text: {''.join(text.splitlines())[:200]}...")


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


if __name__ == "__main__":
    cli()
