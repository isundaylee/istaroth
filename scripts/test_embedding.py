#!/usr/bin/env python3
"""Test script for the DocumentStore."""

import pathlib
import sys

import click

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.rag.embedding import DocumentStore


@click.command()  # type: ignore[misc]
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--query", default="Archon", help="Search query to test")  # type: ignore[misc]
def main(path: pathlib.Path, query: str) -> None:
    """Test the DocumentStore with content from a file or folder."""

    # Build list of files to process
    if path.is_file():
        files_to_process = [path]
        print(f"Reading content from file: {path}")
    elif path.is_dir():
        files_to_process = list(path.glob("*.txt"))
        print(f"Reading content from folder: {path}")
        if not files_to_process:
            print("No .txt files found in the folder.")
            return
    else:
        print(f"Path {path} is neither a file nor a directory.")
        return

    # Create document store and process all files
    store = DocumentStore()

    for file_path in files_to_process:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            metadata = {
                "source": str(file_path),
                "type": "test_document",
                "filename": file_path.name,
            }
            store.add_text(content.strip(), metadata=metadata)
            print(f"Added file: {file_path.name} ({len(content)} characters)")

        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")

    print(f"\nTotal documents in store: {store.num_documents}")

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
