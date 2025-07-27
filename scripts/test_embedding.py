#!/usr/bin/env python3
"""Test script for the DocumentStore."""

import pathlib
import sys

import click

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.rag.embedding import DocumentStore


@click.command()  # type: ignore[misc]
@click.argument("txt_file", type=click.Path(exists=True, readable=True))  # type: ignore[misc]
@click.option("--query", default="Archon", help="Search query to test")  # type: ignore[misc]
def main(txt_file: str, query: str) -> None:
    """Test the DocumentStore with content from a .txt file."""
    print(f"Reading content from: {txt_file}")

    with open(txt_file, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"Content length: {len(content)} characters")
    print("Creating document store and adding content...")

    # Create document store and add content
    store = DocumentStore()

    # Add content with metadata
    metadata = {"source": txt_file, "type": "test_document"}
    store.add_text(content.strip(), metadata=metadata)

    print(f"Number of documents in store: {store.num_documents}")

    # Test search functionality
    print(f"\nSearching for: '{query}'")
    results = store.search(query, k=3)

    for i, (text, score) in enumerate(results):
        print(f"\nResult {i + 1} (score: {score:.4f}):")
        print(f"  Text preview: {''.join(text.splitlines())}")


if __name__ == "__main__":
    main()
