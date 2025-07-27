#!/usr/bin/env python3
"""AGD tools for processing and rendering game content."""

import pathlib
import sys
from typing import TextIO

import click
from tqdm import tqdm

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.agd import processing, rendering, repo
from istorath.agd.renderable_types import BaseRenderableType, Quests, Readables


def _generate_content(
    renderable_type: BaseRenderableType,
    output_dir: pathlib.Path,
    desc: str,
    *,
    data_repo: repo.DataRepo,
    verbose: bool = False,
    errors_file: TextIO | None = None,
) -> tuple[int, int]:
    """Generate content files using renderable type.

    Returns:
        Tuple of (success_count, error_count)
    """
    success_count = 0
    error_count = 0

    output_dir.mkdir(exist_ok=True)

    # Discover files for this type
    file_paths = renderable_type.discover(data_repo)

    # Create progress bar
    with tqdm(file_paths, desc=desc, disable=verbose) as pbar:
        for file_path in pbar:
            try:
                # Process the file
                rendered = renderable_type.process(file_path, data_repo)

                # Write to output file
                output_file = output_dir / rendered.filename
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(rendered.content)

                if verbose:
                    click.echo(f"✓ {file_path} -> {rendered.filename}")

                success_count += 1

            except Exception as e:
                error_msg = f"✗ {file_path} -> ERROR: {e}"
                if errors_file:
                    errors_file.write(error_msg + "\n")
                if verbose:
                    click.echo(error_msg)
                error_count += 1

            # Update progress bar with error count
            pbar.set_postfix({"errors": error_count})

    return success_count, error_count


@click.group()  # type: ignore[misc]
def cli() -> None:
    """AGD tools for processing and rendering game content."""
    pass


@cli.command("generate-all")  # type: ignore[misc]
@click.argument("output_dir", type=click.Path(path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--readable/--no-readable", default=True, help="Generate readable content")  # type: ignore[misc]
@click.option("--quest/--no-quest", default=True, help="Generate quest content")  # type: ignore[misc]
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")  # type: ignore[misc]
def generate_all(
    output_dir: pathlib.Path,
    readable: bool,
    quest: bool,
    verbose: bool,
) -> None:
    """Generate all readable and quest content into RAG-suitable text files.

    OUTPUT_DIR: Directory to write generated .txt files
    """
    try:
        data_repo = repo.DataRepo.from_env()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    total_success = 0
    total_error = 0

    # Open errors file for writing
    errors_file_path = output_dir / "errors.txt"
    with errors_file_path.open("w", encoding="utf-8") as errors_file:
        if readable:
            success, error = _generate_content(
                Readables(),
                output_dir / "readable",
                "Generating readable content",
                data_repo=data_repo,
                verbose=verbose,
                errors_file=errors_file,
            )
            total_success += success
            total_error += error
            if not verbose:
                click.echo(f"Readable: {success} success, {error} errors")

        if quest:
            success, error = _generate_content(
                Quests(),
                output_dir / "quest",
                "Generating quest content",
                data_repo=data_repo,
                verbose=verbose,
                errors_file=errors_file,
            )
            total_success += success
            total_error += error
            if not verbose:
                click.echo(f"Quest: {success} success, {error} errors")

    # Dump unused text map entries
    text_map_tracker = data_repo.load_text_map()
    unused_entries = text_map_tracker.get_unused_entries()
    total_entries = len(text_map_tracker._text_map)
    unused_percentage = (
        (len(unused_entries) / total_entries) * 100 if total_entries > 0 else 0
    )

    unused_file_path = output_dir / "unused_text_map.txt"
    with unused_file_path.open("w", encoding="utf-8") as unused_file:
        for text_id, content in unused_entries.items():
            unused_file.write(f"{text_id}: {content}\n")

    click.echo(f"\nTotal: {total_success} files generated, {total_error} errors")
    click.echo(
        f"Unused text map entries: {len(unused_entries)}/{total_entries} ({unused_percentage:.1f}%) saved to {unused_file_path}"
    )

    if total_error > 0:
        click.echo(f"Detailed errors written to {errors_file_path}")
        if not verbose:
            click.echo("Run with --verbose to see detailed error messages")
    else:
        # Remove empty errors file
        if errors_file_path.exists():
            errors_file_path.unlink()


@cli.group(name="render")  # type: ignore[misc]
def render_group() -> None:
    """Render AGD content into RAG-suitable text format."""
    pass


@render_group.command("readable")  # type: ignore[misc]
@click.argument("readable_path")  # type: ignore[misc]
def render_readable(readable_path: str) -> None:
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


@render_group.command("talk")  # type: ignore[misc]
@click.argument("talk_path")  # type: ignore[misc]
def render_talk(talk_path: str) -> None:
    """Render talk dialog from the given path."""
    try:
        data_repo = repo.DataRepo.from_env()

        # Get talk info
        talk_info = processing.get_talk_info(talk_path, data_repo=data_repo)

        # Render the talk
        rendered = rendering.render_talk(talk_info)

        # Output only the content
        click.echo(rendered.content)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@render_group.command("quest")  # type: ignore[misc]
@click.argument("quest_path")  # type: ignore[misc]
def render_quest(quest_path: str) -> None:
    """Render quest dialog from the given path."""
    try:
        data_repo = repo.DataRepo.from_env()

        # Get quest info
        quest_info = processing.get_quest_info(quest_path, data_repo=data_repo)

        # Render the quest
        rendered = rendering.render_quest(quest_info)

        # Output only the content
        click.echo(rendered.content)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("list-readables")  # type: ignore[misc]
def list_readables() -> None:
    """List readable metadata for all CHS files."""
    try:
        data_repo = repo.DataRepo.from_env()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    readable_dir = data_repo.agd_path / "Readable" / data_repo.language

    if not readable_dir.exists():
        click.echo(f"Error: Directory {readable_dir} does not exist", err=True)
        sys.exit(1)

    click.echo(f"Readable Metadata ({data_repo.language}):")
    click.echo("=" * 50)

    # Find all .txt files in the readable directory
    txt_files = sorted(readable_dir.glob("*.txt"))

    success_count = 0
    error_count = 0

    for txt_file in txt_files:
        relative_path = f"Readable/{data_repo.language}/{txt_file.name}"
        try:
            metadata = processing.get_readable_metadata(
                relative_path, data_repo=data_repo
            )
            click.echo(f"{txt_file.name:<20} -> {metadata.title}")
            success_count += 1
        except Exception as e:
            click.echo(f"{txt_file.name:<20} -> ERROR: {e}")
            error_count += 1

    click.echo("=" * 50)
    click.echo(
        f"Processed {len(txt_files)} files: {success_count} success, {error_count} errors"
    )


if __name__ == "__main__":
    cli()
