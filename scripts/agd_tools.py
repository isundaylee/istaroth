#!/usr/bin/env python3
"""AGD tools for processing and rendering game content."""

import json
import multiprocessing
import pathlib
import random
import subprocess
import sys
from typing import TextIO

import attrs
import click
from tqdm import tqdm

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.agd import localization, processing, rendering, repo, types
from istaroth.agd.renderable_types import (
    BaseRenderableType,
    CharacterStories,
    Materials,
    Quests,
    Readables,
    Subtitles,
    Talks,
    Voicelines,
)


@attrs.define
class _RenderableResult:
    """Result of processing a single renderable item."""

    renderable_key: str
    rendered_item: types.RenderedItem | None
    error_message: str | None
    tracker_stats: types.TrackerStats


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
    """Check if a Git repository has uncommitted changes (excluding submodule changes)."""
    # Check for unstaged and staged changes
    result = subprocess.run(
        ["git", "status", "--porcelain", "--ignore-submodules"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def _generate_metadata(
    agd_path: pathlib.Path, istaroth_path: pathlib.Path
) -> dict[str, str | bool]:
    """Generate metadata dictionary with Git information."""
    return {
        "agd_git_commit": _get_git_commit_hash(agd_path),
        "istaroth_git_commit": _get_git_commit_hash(istaroth_path),
        "istaroth_git_dirty": _is_git_repo_dirty(istaroth_path),
    }


class _ErrorLimitError(Exception):
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
) -> _RenderableResult:
    """Worker function to process a single renderable item."""
    renderable_key, renderable_type, data_repo = args
    try:
        with (
            data_repo.load_text_map() as text_map_tracker,
            data_repo.load_talk_excel_config_data() as talk_tracker,
        ):
            rendered = renderable_type.process(renderable_key, data_repo)
            accessed_text_ids = text_map_tracker.get_accessed_ids()
            accessed_talk_ids = talk_tracker.get_accessed_ids()
        return _RenderableResult(
            renderable_key,
            rendered,
            None,
            types.TrackerStats(accessed_text_ids, accessed_talk_ids),
        )
    except Exception as e:
        return _RenderableResult(
            renderable_key, None, str(e), types.TrackerStats(set(), set())
        )


def _generate_content(
    renderable_type: BaseRenderableType,
    output_dir: pathlib.Path,
    desc: str,
    *,
    data_repo: repo.DataRepo,
    errors_file: TextIO | None = None,
    processes: int | None = None,
    sample_rate: float = 1.0,
) -> tuple[int, int, int, types.TrackerStats]:
    """Generate content files using renderable type.

    Returns:
        Tuple of (success_count, error_count, skipped_count, tracker_stats)
    """
    success_count = 0
    error_count = 0
    skipped_count = 0
    tracker_stats = types.TrackerStats(
        accessed_text_map_ids=set(), accessed_talk_ids=set()
    )

    output_dir.mkdir(exist_ok=True)

    # Discover renderable keys for this type
    renderable_keys = renderable_type.discover(data_repo)

    if not renderable_keys:
        raise RuntimeError(
            f"No renderable keys found for {renderable_type.__class__.__name__}"
        )

    # Apply sampling if sample_rate < 1.0
    if sample_rate < 1.0:
        original_count = len(renderable_keys)
        sample_size = int(len(renderable_keys) * sample_rate)
        renderable_keys = random.sample(renderable_keys, sample_size)
        click.echo(
            f"Sampling {len(renderable_keys)} of {original_count} items ({sample_rate:.1%})"
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
            for result in pool.imap(_process_single_item, process_args):
                pbar.update(1)

                # Collect accessed text map IDs regardless of success/failure
                tracker_stats.update(result.tracker_stats)

                if result.error_message is not None:
                    log_message(
                        f"✗ {result.renderable_key} -> ERROR: {result.error_message}"
                    )
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
                        raise _ErrorLimitError(
                            renderable_type.__class__.__name__,
                            error_count,
                            effective_error_limit,
                        )

                    continue

                # Skip if rendered is None (filtered out)
                if result.rendered_item is None:
                    log_message(f"⚠ {result.renderable_key} -> SKIPPED (filtered)")
                    skipped_count += 1
                    continue

                # Handle filename collisions
                original_filename = result.rendered_item.filename
                filename = resolve_filename_collision(original_filename)

                # Log warning if there was a collision
                if filename != original_filename:
                    log_message(
                        f"Warning: Filename collision for {result.renderable_key}, renamed to {filename}"
                    )

                used_filenames.add(filename)

                # Write to output file
                output_file = output_dir / filename
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(result.rendered_item.content)

                success_count += 1

                pbar.set_postfix({"errors": error_count, "skipped": skipped_count})

    return (
        success_count,
        error_count,
        skipped_count,
        tracker_stats,
    )


@click.group()  # type: ignore[misc]
def cli() -> None:
    """AGD tools for processing and rendering game content."""
    pass


@cli.command("generate-all")  # type: ignore[misc]
@click.argument("output_dir", type=click.Path(path_type=pathlib.Path))  # type: ignore[misc]
@click.option("--only", type=click.Choice(["readable", "quest", "character-stories", "subtitles", "materials", "voicelines", "talks"]), help="Generate only specific content type")  # type: ignore[misc]
@click.option("--processes", "-j", type=int, help="Number of parallel processes (default: CPU count)")  # type: ignore[misc]
@click.option("--sample-rate", type=float, default=1.0, help="Percentage of each type to process (0.0-1.0, default: 1.0)")  # type: ignore[misc]
def generate_all(
    output_dir: pathlib.Path,
    only: str | None,
    processes: int | None,
    sample_rate: float,
) -> None:
    """Generate content into RAG-suitable text files."""
    # Validate sample_rate parameter
    if not 0.0 <= sample_rate <= 1.0:
        click.echo("Error: sample-rate must be between 0.0 and 1.0", err=True)
        sys.exit(1)

    try:
        data_repo = repo.DataRepo.from_env()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate and write metadata.json
    istaroth_path = pathlib.Path(__file__).parent.parent
    metadata = _generate_metadata(data_repo.agd_path, istaroth_path)
    metadata_path = output_dir / "metadata.json"
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    click.echo(f"Metadata written to {metadata_path}")

    total_success = 0
    total_error = 0
    total_skipped = 0
    all_tracker_stats = types.TrackerStats(set(), set())

    # Determine which content types to generate
    generate_readable = only is None or only == "readable"
    generate_quest = only is None or only == "quest"
    generate_character_stories = only is None or only == "character-stories"
    generate_subtitles = only is None or only == "subtitles"
    generate_materials = only is None or only == "materials"
    generate_talks = only is None or only == "talks"

    # Open errors file for writing
    errors_file_path = output_dir / "errors.info"
    with errors_file_path.open("w", encoding="utf-8") as errors_file:
        if generate_readable:
            success, error, skipped, tracker_stats = _generate_content(
                Readables(),
                output_dir / "readable",
                "Generating readable content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
                sample_rate=sample_rate,
            )
            total_success += success
            total_error += error
            total_skipped += skipped
            all_tracker_stats.update(tracker_stats)
            click.echo(
                f"Readable: {success} success, {error} errors, {skipped} skipped"
            )

        if generate_quest:
            success, error, skipped, tracker_stats = _generate_content(
                Quests(),
                output_dir / "quest",
                "Generating quest content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
                sample_rate=sample_rate,
            )
            total_success += success
            total_error += error
            total_skipped += skipped
            all_tracker_stats.update(tracker_stats)
            click.echo(f"Quest: {success} success, {error} errors, {skipped} skipped")

        if generate_character_stories:
            success, error, skipped, tracker_stats = _generate_content(
                CharacterStories(),
                output_dir / "character_stories",
                "Generating character stories",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
                sample_rate=sample_rate,
            )
            total_success += success
            total_error += error
            total_skipped += skipped
            all_tracker_stats.update(tracker_stats)
            click.echo(
                f"Character stories: {success} success, {error} errors, {skipped} skipped"
            )

        if generate_subtitles:
            success, error, skipped, tracker_stats = _generate_content(
                Subtitles(),
                output_dir / "subtitles",
                "Generating subtitle content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
                sample_rate=sample_rate,
            )
            total_success += success
            total_error += error
            total_skipped += skipped
            all_tracker_stats.update(tracker_stats)
            click.echo(
                f"Subtitles: {success} success, {error} errors, {skipped} skipped"
            )

        if generate_materials:
            success, error, skipped, tracker_stats = _generate_content(
                Materials(),
                output_dir / "materials",
                "Generating material content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
                sample_rate=sample_rate,
            )
            total_success += success
            total_error += error
            total_skipped += skipped
            all_tracker_stats.update(tracker_stats)
            click.echo(
                f"Materials: {success} success, {error} errors, {skipped} skipped"
            )

        if not only or only == "voicelines":
            success, error, skipped, tracker_stats = _generate_content(
                Voicelines(),
                output_dir / "voicelines",
                "Generating voiceline content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
                sample_rate=sample_rate,
            )
            total_success += success
            total_error += error
            total_skipped += skipped
            all_tracker_stats.update(tracker_stats)
            click.echo(
                f"Voicelines: {success} success, {error} errors, {skipped} skipped"
            )

        if generate_talks:
            # Create Talks renderable with all previously used talk IDs
            used_talk_ids = all_tracker_stats.accessed_talk_ids.copy()

            success, error, skipped, tracker_stats = _generate_content(
                Talks(used_talk_ids),
                output_dir / "talks",
                "Generating standalone talk content",
                data_repo=data_repo,
                errors_file=errors_file,
                processes=processes,
                sample_rate=sample_rate,
            )
            total_success += success
            total_error += error
            total_skipped += skipped
            all_tracker_stats.update(tracker_stats)
            click.echo(f"Talks: {success} success, {error} errors, {skipped} skipped")

    click.echo(
        f"\nTotal: {total_success} files generated, {total_error} errors, {total_skipped} skipped"
    )

    # Calculate and print unused text map and talk ID entries count
    text_map_tracker = data_repo.load_text_map()
    text_map_tracker._accessed_ids.update(all_tracker_stats.accessed_text_map_ids)
    click.echo(f"Text map: {text_map_tracker.format_unused_stats()} unused")

    talk_tracker = data_repo.load_talk_excel_config_data()
    talk_tracker._accessed_ids.update(all_tracker_stats.accessed_talk_ids)
    click.echo(f"Talk IDs: {talk_tracker.format_unused_stats()} unused")

    # Write unused stats to JSON file
    unused_stats_data = all_tracker_stats.to_dict(text_map_tracker, talk_tracker)
    unused_stats_path = output_dir / "unused_stats.json"
    with unused_stats_path.open("w", encoding="utf-8") as f:
        json.dump(unused_stats_data, f, indent=2, ensure_ascii=False)
    click.echo(f"Text map usage stats written to {unused_stats_path}")

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

        # Extract talk ID from path (e.g., "BinOutput/Talk/NPC/100001.json" -> "100001")
        talk_id = pathlib.Path(talk_path).stem

        # Render the talk
        rendered = rendering.render_talk(
            talk_info, talk_id=talk_id, language=localization.Language.CHS
        )

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
        rendered = rendering.render_quest(
            quest_info, language=localization.Language.CHS
        )

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

    readable_dir = data_repo.agd_path / "Readable" / data_repo.language.value

    if not readable_dir.exists():
        click.echo(f"Error: Directory {readable_dir} does not exist", err=True)
        sys.exit(1)

    click.echo(f"Readable Metadata ({data_repo.language.value}):")
    click.echo("=" * 50)

    # Find all .txt files in the readable directory
    txt_files = sorted(readable_dir.glob("*.txt"))

    success_count = 0
    error_count = 0

    for txt_file in txt_files:
        relative_path = f"Readable/{data_repo.language.value}/{txt_file.name}"
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
