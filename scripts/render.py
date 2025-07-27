#!/usr/bin/env python3
"""CLI tool for rendering AGD content into RAG-suitable format."""

import os
import pathlib
import sys

import click

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.agd import processing, rendering, repo


@click.group()  # type: ignore[misc]
def cli() -> None:
    """Render AGD content into RAG-suitable text format."""
    pass


@cli.command()  # type: ignore[misc]
@click.argument("readable_path")  # type: ignore[misc]
def readable(readable_path: str) -> None:
    """Render readable content from the given path."""
    try:
        data_repo = repo.DataRepo.from_env()

        # Get readable metadata
        metadata = processing.get_readable_metadata(readable_path, data_repo=data_repo)

        # Read the actual readable content
        readable_file_path = data_repo.agd_path / readable_path
        with open(readable_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Render the content
        rendered = rendering.render_readable(content, metadata)

        # Output only the content
        click.echo(rendered.content)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
