#!/usr/bin/env python3
"""Upload generated files to LlamaCloud index."""

import hashlib
import json
import os
import pathlib
import sys
from typing import Any, List, Set, Tuple, TypedDict

import attrs
import click
from llama_cloud.client import LlamaCloud
from llama_cloud.types import CloudDocumentCreate


@attrs.define
class UploadDatabase:
    """Structure of the upload tracking database."""

    uploaded_hashes: set[str]


def _load_upload_database(database_path: pathlib.Path) -> UploadDatabase:
    """Load upload database from disk."""
    try:
        with open(database_path, "r") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        click.echo("Starting with empty upload database")
        return UploadDatabase(uploaded_hashes=set())
    else:
        data = UploadDatabase(uploaded_hashes=set(raw_data["uploaded_hashes"]))
        click.echo(
            f"Loaded upload database with {len(data.uploaded_hashes)} document hashes"
        )
        return data


def _save_upload_database(
    database_path: pathlib.Path, database: UploadDatabase
) -> None:
    """Save upload database to disk."""
    with open(database_path, "w") as f:
        json.dump({"uploaded_hashes": sorted(database.uploaded_hashes)}, f, indent=2)
    click.echo(
        f"Saved upload database with {len(database.uploaded_hashes)} document hashes"
    )


def _find_pipeline(client: LlamaCloud, pipeline_name: str) -> Any:
    """Find pipeline by name."""
    click.echo(f"Searching for pipeline: {pipeline_name}")
    try:
        pipelines = client.pipelines.search_pipelines(pipeline_name=pipeline_name)
        if pipelines:
            pipeline = pipelines[0]
            click.echo(f"Found pipeline: {pipeline.id} ({pipeline.name})")
            return pipeline
        else:
            click.echo(
                f"No pipeline found with name '{pipeline_name}'. Please create it first.",
                err=True,
            )
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error searching for pipeline: {e}", err=True)
        sys.exit(1)


def _prepare_documents(
    txt_files: List[pathlib.Path], input_dir: pathlib.Path, uploaded_hashes: Set[str]
) -> Tuple[List[CloudDocumentCreate], List[str]]:
    """Prepare documents for upload, filtering out duplicates based on content hash."""
    click.echo(f"Checking {len(txt_files)} documents for duplicates...")
    new_documents = []
    new_hashes = []
    skipped_count = 0

    for file_path in txt_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Calculate MD5 hash of content
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

        if content_hash in uploaded_hashes:
            skipped_count += 1
            continue

        doc = CloudDocumentCreate(
            text=content,
            metadata={
                "file_name": file_path.name,
                "file_path": str(file_path.relative_to(input_dir)),
                "source": "istorath-generate",
                "content_hash": content_hash,
            },
        )
        new_documents.append(doc)
        new_hashes.append(content_hash)

    click.echo(
        f"Found {len(new_documents)} new documents to upload, skipped {skipped_count} duplicates"
    )
    return new_documents, new_hashes


def _upload_documents_batch(
    client: LlamaCloud, pipeline_id: str, documents: List[CloudDocumentCreate]
) -> None:
    """Upload a single batch of documents to LlamaCloud pipeline."""
    click.echo(
        f"Uploading batch of {len(documents)} documents to pipeline {pipeline_id}..."
    )
    try:
        result = client.pipelines.create_batch_pipeline_documents(
            pipeline_id, request=documents
        )
        click.echo(
            f"Batch upload completed successfully! Created {len(result)} documents."
        )
    except Exception as e:
        click.echo(f"Error uploading batch: {e}", err=True)
        raise


def _upload_documents_in_batches(
    client: LlamaCloud,
    pipeline_id: str,
    documents: List[CloudDocumentCreate],
    hashes: List[str],
    batch_size: int,
    uploaded_hashes: Set[str],
) -> None:
    """Upload documents in batches, saving progress after each successful batch."""
    total_documents = len(documents)
    total_uploaded = 0

    for i in range(0, total_documents, batch_size):
        batch_end = min(i + batch_size, total_documents)
        batch_docs = documents[i:batch_end]
        batch_hashes = hashes[i:batch_end]

        _upload_documents_batch(client, pipeline_id, batch_docs)
        uploaded_hashes.update(set(batch_hashes))
        total_uploaded += len(batch_docs)

        click.echo(f"Progress: {total_uploaded}/{total_documents} documents uploaded")

    click.echo(f"\nAll {total_uploaded} documents uploaded successfully!")


@click.command()  # type: ignore[misc]
@click.argument("input_dir", type=click.Path(exists=True, path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--database-path", required=True, type=click.Path(path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--limit", default=1, help="Number of documents to upload (for testing); 0 to disable the limit")  # type: ignore[misc]
@click.option("--batch-size", default=10, help="Number of documents to upload per batch")  # type: ignore[misc]
@click.option("--pipeline-name", required=True, help="Name of the pipeline to upload to")  # type: ignore[misc]
def main(
    input_dir: pathlib.Path,
    *,
    database_path: pathlib.Path,
    limit: int,
    batch_size: int,
    pipeline_name: str,
) -> None:
    """Upload generated files to LlamaCloud index.

    INPUT_DIR: Directory containing generated .txt files from generate.py
    UPLOAD_DATA_PATH: Path to store upload tracking data (MD5 hashes)
    """
    # Validate API key
    api_key = os.getenv("LLAMACLOUD_API_KEY")
    if not api_key:
        click.echo("Error: LLAMACLOUD_API_KEY environment variable not set", err=True)
        sys.exit(1)

    # Load upload database
    database = _load_upload_database(database_path)

    # Find .txt files
    click.echo(f"Finding .txt documents in {input_dir}...")
    txt_files = list(input_dir.rglob("*.txt"))

    if not txt_files:
        click.echo("No .txt files found to upload", err=True)
        sys.exit(1)

    # Create LlamaCloud client
    click.echo("Connecting to LlamaCloud...")
    client = LlamaCloud(token=api_key)

    # Find pipeline
    pipeline = _find_pipeline(client, pipeline_name)

    # Prepare documents (filter duplicates)
    new_documents, new_hashes = _prepare_documents(
        txt_files, input_dir, database.uploaded_hashes
    )

    # Apply limit if specified
    if limit > 0 and len(new_documents) > limit:
        new_documents = new_documents[:limit]
        new_hashes = new_hashes[:limit]
        click.echo(f"Limited to {len(new_documents)} documents for testing")

    if not new_documents:
        click.echo("No new documents to upload!")
        return

    # Upload documents in batches
    try:
        _upload_documents_in_batches(
            client=client,
            pipeline_id=pipeline.id,
            documents=new_documents,
            hashes=new_hashes,
            batch_size=batch_size,
            uploaded_hashes=database.uploaded_hashes,
        )
    finally:
        _save_upload_database(database_path, database)


if __name__ == "__main__":
    main()
