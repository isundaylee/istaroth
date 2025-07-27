#!/usr/bin/env python3
"""Test script for the DocumentStore."""

import pathlib
import sys

import click
from tqdm import tqdm

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.rag.embedding import DocumentStore


@click.command()  # type: ignore[misc]
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--query", default="Archon", help="Search query to test")  # type: ignore[misc]
@click.option("--save-path", type=click.Path(path_type=pathlib.Path), help="Path to save/load document store")  # type: ignore[misc]
def main(path: pathlib.Path, query: str, save_path: pathlib.Path | None) -> None:
    """Test the DocumentStore with content from a file or folder."""

    # Build list of files to process
    if path.is_file():
        files_to_process = [path]
        print(f"Reading content from file: {path}")
    elif path.is_dir():
        files_to_process = list(path.glob("**/*.txt"))
        print(f"Reading content from folder: {path}")
        if not files_to_process:
            print("No .txt files found in the folder.")
            return
    else:
        print(f"Path {path} is neither a file nor a directory.")
        return

    # Create document store
    store = DocumentStore()

    # Load existing state if save path exists
    if save_path and save_path.exists():
        print(f"Loading existing document store from: {save_path}")
        store.load(save_path)
        print(f"Loaded store with {store.num_documents} existing documents")

    with tqdm(files_to_process, desc="Adding documents", unit="file") as pbar:
        for file_path in pbar:
            try:
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

            except Exception as e:
                tqdm.write(f"Error reading {file_path.name}: {e}")

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
