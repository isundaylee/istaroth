#!/usr/bin/env python3
"""AGD tools for processing and rendering game content."""

import json
import multiprocessing
import pathlib
import subprocess
import sys
from typing import TextIO

import click
from tqdm import tqdm

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.agd import processing, rendering, repo, types
from istorath.agd.renderable_types import (
    BaseRenderableType,
    CharacterStories,
    Quests,
    Readables,
    UnusedTexts,
)


def _get_git_commit_hash(repo_path: pathlib.Path) -> str:
    """Get the current Git commit hash for a repository."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _is_git_repo_dirty(repo_path: pathlib.Path) -> bool:
    """Check if a Git repository has uncommitted changes (including untracked files)."""
    # Check for unstaged and staged changes
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def _generate_metadata(
    agd_path: pathlib.Path, istorath_path: pathlib.Path
) -> dict[str, str | bool]:
    """Generate metadata dictionary with Git information."""
    return {
        "agd_git_commit": _get_git_commit_hash(agd_path),
        "istorath_git_commit": _get_git_commit_hash(istorath_path),
        "istorath_git_dirty": _is_git_repo_dirty(istorath_path),
    }


class ErrorLimitExceededException(Exception):
    """Exception raised when error limit is exceeded during generation."""

    def __init__(self, content_type: str, error_count: int, error_limit: int) -> None:
        self.content_type = content_type
        self.error_count = error_count
        self.error_limit = error_limit
        super().__init__(
            f"{content_type} generation exceeded error limit ({error_count} > {error_limit})"
        )


def _process_single_item(
    args: tuple[str, BaseRenderableType, repo.DataRepo],
) -> tuple[str, types.RenderedItem | None, str | None]:
    """Worker function to process a single renderable item.

    Returns:
        Tuple of (renderable_key, rendered_item_or_none, error_message_or_none)
    """
    renderable_key, renderable_type, data_repo = args
    try:
        rendered = renderable_type.process(renderable_key, data_repo)
        return (renderable_key, rendered, None)
    except Exception as e:
        return (renderable_key, None, str(e))


def _generate_content(
    renderable_type: BaseRenderableType,
    output_dir: pathlib.Path,
    desc: str,
    *,
    data_repo: repo.DataRepo,
    errors_file: TextIO | None = None,
    processes: int | None = None,
) -> tuple[int, int]:
    """Generate content files using renderable type.

    Returns:
        Tuple of (success_count, error_count)
    """
    success_count = 0
    error_count = 0

    output_dir.mkdir(exist_ok=True)

    # Discover renderable keys for this type
    renderable_keys = renderable_type.discover(data_repo)

    if not renderable_keys:
        raise RuntimeError(
            f"No renderable keys found for {renderable_type.__class__.__name__}"
        )

    # Prepare arguments for multiprocessing
    process_args = [(key, renderable_type, data_repo) for key in renderable_keys]

    # Use multiprocessing to process items in parallel
    if processes is None:
        processes = multiprocessing.cpu_count()

    # Track used filenames to prevent collisions
    used_filenames: set[str] = set()

    def log_message(message: str) -> None:
        """Helper to log message to errors file."""
        if errors_file:
            errors_file.write(message + "\n")

    def resolve_filename_collision(original_filename: str) -> str:
        """Helper to resolve filename collisions by adding counter suffix."""
        filename = original_filename
        counter = 1

        while filename in used_filenames:
            # Add counter to make filename unique
            name, ext = (
                pathlib.Path(original_filename).stem,
                pathlib.Path(original_filename).suffix,
            )
            filename = f"{name}_{counter}{ext}"
            counter += 1

        return filename

    with multiprocessing.Pool(processes=processes) as pool:
        # Process with progress bar
        with tqdm(total=len(process_args), desc=desc) as pbar:
            for renderable_key, rendered, error in pool.imap(
                _process_single_item, process_args
            ):
                pbar.update(1)

                if error is not None:
                    log_message(f"✗ {renderable_key} -> ERROR: {error}")
                    error_count += 1

                    # Check if error limit exceeded
                    effective_error_limit = (
                        renderable_type.error_limit
                        if data_repo.language == "CHS"
                        else renderable_type.error_limit_non_chinese
                    )
                    if error_count > effective_error_limit:
                        error_msg = f"Error limit exceeded ({error_count} > {effective_error_limit}), stopping generation"
                        log_message(error_msg)
                        raise ErrorLimitExceededException(
                            renderable_type.__class__.__name__,
                            error_count,
                            effective_error_limit,
                        )

                    continue

                assert rendered is not None  # For type checker

                # Handle filename collisions
                original_filename = rendered.filename
                filename = resolve_filename_collision(original_filename)

                # Log warning if there was a collision
                if filename != original_filename:
                    log_message(
                        f"Warning: Filename collision for {renderable_key}, renamed to {filename}"
                    )

                used_filenames.add(filename)

                # Write to output file
                output_file = output_dir / filename
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(rendered.content)

                success_count += 1

                pbar.set_postfix({"errors": error_count})

    return success_count, error_count


@click.group()  # type: ignore[misc]
def cli() -> None:
    """AGD tools for processing and rendering game content."""
    pass


@cli.command("generate-all")  # type: ignore[misc]
@click.argument("output_dir", type=click.Path(path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--only", type=click.Choice(["readable", "quest", "character-stories"]), help="Generate only specific content type")  # type: ignore[misc]
@click.option("--processes", "-j", type=int, help="Number of parallel processes (default: CPU count)")  # type: ignore[misc]
def generate_all(
    output_dir: pathlib.Path,
    only: str | None,
    processes: int | None,
) -> None:
    """Generate content into RAG-suitable text files."""
    try:
        data_repo = repo.DataRepo.from_env()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    total_success = 0
    total_error = 0

    # Determine which content types to generate
    generate_readable = only is None or only == "readable"
    generate_quest = only is None or only == "quest"
    generate_character_stories = only is None or only == "character-stories"

    # Open errors file for writing
    errors_file_path = output_dir / "errors.log"
    with errors_file_path.open("w", encoding="utf-8") as errors_file:
        if generate_readable:
            success, error = _generate_content(
                Readables(),
                output_dir / "readable",
                "Generating readable content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
            )
            total_success += success
            total_error += error
            click.echo(f"Readable: {success} success, {error} errors")

        if generate_quest:
            success, error = _generate_content(
                Quests(),
                output_dir / "quest",
                "Generating quest content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
            )
            total_success += success
            total_error += error
            click.echo(f"Quest: {success} success, {error} errors")

        if generate_character_stories:
            success, error = _generate_content(
                CharacterStories(),
                output_dir / "character_stories",
                "Generating character stories",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
            )
            total_success += success
            total_error += error
            click.echo(f"Character stories: {success} success, {error} errors")

    click.echo(f"\nTotal: {total_success} files generated, {total_error} errors")

    # Generate and write metadata.json
    istorath_path = pathlib.Path(__file__).parent.parent
    metadata = _generate_metadata(data_repo.agd_path, istorath_path)
    metadata_path = output_dir / "metadata.json"
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    click.echo(f"Metadata written to {metadata_path}")

    if total_error > 0:
        click.echo(f"\nDetailed errors written to {errors_file_path}")
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
