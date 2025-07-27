#!/usr/bin/env python3
"""Test script for the DocumentStore."""

import pathlib
import random
import sys

import click
from tqdm import tqdm

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.rag.embedding import DocumentStore


def _get_files_to_process(path: pathlib.Path) -> list[pathlib.Path]:
    """Get a list of .txt files to process from the given path."""
    if path.is_file():
        return [path]
    elif path.is_dir():
        paths = list(path.glob("**/*.txt"))
        random.shuffle(paths)
        return paths
    else:
        raise ValueError(f"Path {path} is neither a file nor a directory.")


@click.command()  # type: ignore[misc]
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--query", default="Archon", help="Search query to test")  # type: ignore[misc]
@click.option("--save-path", type=click.Path(path_type=pathlib.Path), help="Path to save/load document store")  # type: ignore[misc]
def main(path: pathlib.Path, query: str, save_path: pathlib.Path | None) -> None:
    """Test the DocumentStore with content from a file or folder."""

    # Create document store
    store = DocumentStore()

    # Load existing state if save path exists
    if save_path and save_path.exists():
        print(f"Loading existing document store from: {save_path}")
        store.load(save_path)
        print(f"Loaded store with {store.num_documents} existing documents")

    try:
        with tqdm(
            _get_files_to_process(path), desc="Adding documents", unit="file"
        ) as pbar:
            for file_path in pbar:
                pbar.set_postfix(file=file_path.name)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                metadata = {
                    "source": str(file_path),
                    "type": "test_document",
                    "filename": file_path.name,
                }
                # Use file path as unique key
                store.add_text(content.strip(), key=str(file_path), metadata=metadata)
    finally:
        print(f"\nTotal documents in store: {store.num_documents}")

        # Save state if save path is provided
        if save_path:
            print(f"Saving document store to: {save_path}")
            save_path.mkdir(exist_ok=True)
            store.save(save_path)

    # Test search functionality
    print(f"\nSearching for: '{query}'")
    results = store.search(query, k=3)

    if not results:
        print("No results found.")
        return

    for i, (text, score) in enumerate(results):
        print(f"\nResult {i + 1} (score: {score:.4f}):")
        print(f"  Text: {''.join(text.splitlines())}")


if __name__ == "__main__":
    main()
