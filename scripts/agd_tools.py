#!/usr/bin/env python3
"""AGD tools for processing and rendering game content."""

import functools
import json
import multiprocessing
import multiprocessing.pool
import pathlib
import random
import shutil
import subprocess
import sys
from typing import Any, TextIO

import attrs
import click
from tabulate import tabulate
from tqdm import tqdm

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.agd import localization, processing, rendering, repo, types
from istaroth.agd.renderable_types import (
    ArtifactSets,
    BaseRenderableType,
    Books,
    CharacterStories,
    Costumes,
    MaterialTypes,
    Quests,
    Readables,
    Subtitles,
    TalkGroups,
    Talks,
    Voicelines,
    Weapons,
    Wings,
)
from istaroth.text import manifest
from istaroth.text import types as text_types


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
    data_repo: repo.DataRepo, istaroth_path: pathlib.Path
) -> dict[str, str | bool]:
    """Generate metadata dictionary with Git information."""
    return {
        "language": data_repo.language.value,
        "agd_git_commit": _get_git_commit_hash(data_repo.agd_path),
        "istaroth_git_commit": _get_git_commit_hash(istaroth_path),
        "istaroth_git_dirty": _is_git_repo_dirty(istaroth_path),
    }


class _ErrorLimitError(Exception):
    """Exception raised when error limit is exceeded during generation."""

    def __init__(
        self, content_type: str, error_count: int, error_limit: int, error_msg: str
    ) -> None:
        self.content_type = content_type
        self.error_count = error_count
        self.error_limit = error_limit
        super().__init__(
            f"{content_type} generation exceeded error limit ({error_count} > {error_limit}); {error_msg}"
        )


@functools.cache
def _get_data_repo_from_env() -> repo.DataRepo:
    return repo.DataRepo.from_env()


def _process_single_item(
    args: tuple[str, BaseRenderableType, bool],
) -> _RenderableResult:
    """Worker function to process a single renderable item."""
    renderable_key, renderable_type, strict = args
    data_repo = _get_data_repo_from_env()
    try:
        with (
            data_repo.load_text_map() as text_map_tracker,
            data_repo.load_talk_excel_config_data() as talk_tracker,
            data_repo.get_readables() as readables_tracker,
        ):
            rendered = renderable_type.process(renderable_key, data_repo)
            accessed_text_ids = text_map_tracker.get_accessed_ids()
            accessed_talk_ids = talk_tracker.get_accessed_ids()
            accessed_readable_ids = readables_tracker.get_accessed_ids()
        return _RenderableResult(
            renderable_key,
            rendered,
            None,
            types.TrackerStats(
                accessed_text_ids, accessed_talk_ids, accessed_readable_ids
            ),
        )
    except Exception as e:
        if strict:
            raise RuntimeError(f"Error processing {renderable_key}")
        return _RenderableResult(
            renderable_key, None, repr(e), types.TrackerStats(set(), set(), set())
        )


def _generate_content(
    renderable_type: BaseRenderableType,
    output_dir: pathlib.Path,
    *,
    data_repo: repo.DataRepo,
    pool: multiprocessing.pool.Pool,
    errors_file: TextIO | None = None,
    sample_rate: float = 1.0,
    strict: bool = False,
    manifest_list: list[text_types.TextMetadata],
) -> tuple[int, int, int, types.TrackerStats]:
    """Generate content files using renderable type.

    Returns:
        Tuple of (success_count, error_count, skipped_count, tracker_stats)
    """
    success_count = 0
    error_count = 0
    skipped_count = 0
    tracker_stats = types.TrackerStats(
        accessed_text_map_ids=set(),
        accessed_talk_ids=set(),
        accessed_readable_ids=set(),
    )

    # Discover renderable keys for this type
    renderable_keys = renderable_type.discover(data_repo)

    if not renderable_keys:
        raise RuntimeError(
            f"No renderable keys found for {renderable_type.__class__.__name__}"
        )

    # Apply sampling if sample_rate < 1.0
    if sample_rate < 1.0:
        original_count = len(renderable_keys)
        sample_size = max(1, int(len(renderable_keys) * sample_rate))
        renderable_keys = random.sample(renderable_keys, sample_size)
        click.echo(
            f"Sampling {len(renderable_keys)} of {original_count} items ({sample_rate:.1%})"
        )

    # Prepare arguments for multiprocessing
    process_args = [(key, renderable_type, strict) for key in renderable_keys]

    # Track used paths to detect collisions
    used_paths: set[str] = set()

    def log_message(message: str) -> None:
        """Helper to log message to errors file."""
        if errors_file:
            errors_file.write(message + "\n")

    # Use the provided multiprocessing pool
    # Process with progress bar
    with tqdm(total=len(process_args), desc=type(renderable_type).__name__) as pbar:
        for result in pool.imap(_process_single_item, process_args):
            pbar.update(1)

            # Collect accessed text map IDs regardless of success/failure
            tracker_stats.update(result.tracker_stats)
            renderable_type_name = renderable_type.__class__.__name__

            if result.error_message is not None:
                log_message(
                    f"✗ {renderable_type_name}: {result.renderable_key} -> ERROR: {result.error_message}"
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
                        renderable_type_name,
                        error_count,
                        effective_error_limit,
                        result.error_message,
                    )

                continue

            # Skip if rendered is None (filtered out)
            if result.rendered_item is None:
                log_message(
                    f"⚠ {renderable_type_name}: {result.renderable_key} -> SKIPPED (filtered)"
                )
                skipped_count += 1
                continue

            # Get TextMetadata from RenderedItem
            text_metadata = result.rendered_item.text_metadata

            # Check for path collision
            if text_metadata.relative_path in used_paths:
                error_msg = (
                    f"Path collision detected: '{text_metadata.relative_path}' "
                    f"for {renderable_type_name}: {result.renderable_key}"
                )
                log_message(f"✗ {error_msg}")
                raise ValueError(error_msg)

            used_paths.add(text_metadata.relative_path)

            # Get output path from metadata
            output_file = output_dir / text_metadata.relative_path
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to output file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result.rendered_item.content)

            # Add to manifest
            manifest_list.append(text_metadata)

            success_count += 1

            pbar.set_postfix({"errors": error_count, "skipped": skipped_count})

    return (
        success_count,
        error_count,
        skipped_count,
        tracker_stats,
    )


@click.group()
def cli() -> None:
    """AGD tools for processing and rendering game content."""
    pass


@cli.command("generate-all")
@click.argument("output_dir", type=click.Path(path_type=pathlib.Path))
@click.option("-f", "--force", is_flag=True, help="Delete output dir if it exists")
@click.option(
    "--only",
    type=click.Choice([tc.value for tc in text_types.TextCategory]),
    help="Generate only specific content type",
)
@click.option(
    "--processes",
    "-j",
    type=int,
    help="Number of parallel processes (default: CPU count)",
)
@click.option(
    "--sample-rate",
    type=float,
    default=1.0,
    help="Percentage of each type to process (0.0-1.0, default: 1.0)",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Throw exceptions instead of catching them when processing fails",
)
def generate_all(
    output_dir: pathlib.Path,
    force: bool,
    only: str | None,
    processes: int | None,
    sample_rate: float,
    strict: bool,
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

    # Create output directory, deleting only AGD-owned content on --force
    # to avoid wiping unrelated folders (e.g. tps_shishu).
    if force and output_dir.exists():
        for tc in text_types.TextCategory:
            if not tc.is_agd:
                continue
            if (agd_dir := output_dir / tc.value).exists():
                shutil.rmtree(agd_dir)
        if (agd_stats := output_dir / "stats" / "agd").exists():
            shutil.rmtree(agd_stats)
        if (agd_manifest := output_dir / "manifest" / "agd.json").exists():
            agd_manifest.unlink()
        if (metadata_path := output_dir / "metadata.json").exists():
            metadata_path.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate and write metadata.json
    istaroth_path = pathlib.Path(__file__).parent.parent
    metadata = _generate_metadata(data_repo, istaroth_path)
    metadata_path = output_dir / "metadata.json"
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    click.echo(f"Metadata written to {metadata_path}")

    total_success = 0
    total_error = 0
    total_skipped = 0
    all_tracker_stats = types.TrackerStats(set(), set(), set())

    # Collect stats for summary table
    summary_stats = []

    # Manifest list to collect all text metadata
    manifest_list: list[text_types.TextMetadata] = []

    # Helper function to process a content type conditionally
    def process_content_type(
        should_generate: bool, renderable: BaseRenderableType
    ) -> None:
        """Process a single content type if condition is met and update global stats."""
        if not should_generate:
            return

        nonlocal total_success, total_error, total_skipped
        success, error, skipped, tracker_stats = _generate_content(
            renderable,
            output_dir,
            data_repo=data_repo,
            pool=pool,
            errors_file=errors_file,
            sample_rate=sample_rate,
            strict=strict,
            manifest_list=manifest_list,
        )
        total_success += success
        total_error += error
        total_skipped += skipped
        all_tracker_stats.update(tracker_stats)
        summary_stats.append([renderable.text_category.value, success, error, skipped])

    # Determine which content types to generate
    only_category = text_types.TextCategory(only) if only else None
    generate_readable = (
        only_category is None or only_category == text_types.TextCategory.AGD_READABLE
    )
    generate_books = (
        only_category is None or only_category == text_types.TextCategory.AGD_BOOK
    )
    generate_weapons = (
        only_category is None or only_category == text_types.TextCategory.AGD_WEAPON
    )
    generate_wings = (
        only_category is None or only_category == text_types.TextCategory.AGD_WINGS
    )
    generate_costumes = (
        only_category is None or only_category == text_types.TextCategory.AGD_COSTUME
    )
    generate_quest = (
        only_category is None or only_category == text_types.TextCategory.AGD_QUEST
    )
    generate_character_stories = (
        only_category is None
        or only_category == text_types.TextCategory.AGD_CHARACTER_STORY
    )
    generate_subtitles = (
        only_category is None or only_category == text_types.TextCategory.AGD_SUBTITLE
    )
    generate_material_types = (
        only_category is None
        or only_category == text_types.TextCategory.AGD_MATERIAL_TYPE
    )
    generate_voicelines = (
        only_category is None or only_category == text_types.TextCategory.AGD_VOICELINE
    )
    generate_talk_groups = (
        only_category is None or only_category == text_types.TextCategory.AGD_TALK_GROUP
    )
    generate_talks = (
        only_category is None or only_category == text_types.TextCategory.AGD_TALK
    )
    generate_artifact_sets = (
        only_category is None
        or only_category == text_types.TextCategory.AGD_ARTIFACT_SET
    )

    # Set up multiprocessing pool to reuse across all content generation
    if processes is None:
        processes = multiprocessing.cpu_count()

    # Pre-compute expensive mappings in parent process for inheritance via fork
    data_repo.precompute_for_fork()

    # Explicitly set start method to 'fork' to ensure child processes inherit
    # the pre-computed mapping from parent memory
    multiprocessing.set_start_method("fork", force=True)

    # Create stats directory for AGD-specific output files
    stats_dir = output_dir / "stats" / "agd"
    stats_dir.mkdir(parents=True, exist_ok=True)

    # Open errors file for writing
    errors_file_path = stats_dir / "errors.info"
    with (
        errors_file_path.open("w", encoding="utf-8") as errors_file,
        multiprocessing.Pool(processes=processes) as pool,
    ):
        process_content_type(generate_artifact_sets, ArtifactSets())
        process_content_type(generate_quest, Quests())
        process_content_type(generate_character_stories, CharacterStories())
        process_content_type(generate_subtitles, Subtitles())
        process_content_type(generate_material_types, MaterialTypes())
        process_content_type(generate_voicelines, Voicelines())
        process_content_type(generate_talk_groups, TalkGroups())

        process_content_type(generate_books, Books())
        process_content_type(generate_weapons, Weapons())
        process_content_type(generate_wings, Wings())
        process_content_type(generate_costumes, Costumes())

        # Generating remaining unused readables/talks
        process_content_type(
            generate_readable,
            Readables(all_tracker_stats.accessed_readable_ids.copy()),
        )
        process_content_type(
            generate_talks, Talks(all_tracker_stats.accessed_talk_ids.copy())
        )

    # Create summary table
    headers = ["Content Type", "Success", "Errors", "Skipped"]
    summary_stats.append(["TOTAL", total_success, total_error, total_skipped])
    summary_table = tabulate(summary_stats, headers=headers, tablefmt="pretty")

    # Print summary table to console
    click.echo("\n" + summary_table)

    # Write summary table to file
    summary_table_path = stats_dir / "summary_table.txt"
    with summary_table_path.open("w", encoding="utf-8") as f:
        f.write(summary_table)
    click.echo(f"Summary table written to {summary_table_path}")

    # Calculate and print unused text map and talk ID entries count
    text_map_tracker = data_repo.load_text_map()
    text_map_tracker._accessed_ids.update(all_tracker_stats.accessed_text_map_ids)
    click.echo(f"Text map: {text_map_tracker.format_unused_stats()} unused")

    talk_tracker = data_repo.load_talk_excel_config_data()
    talk_tracker._accessed_ids.update(all_tracker_stats.accessed_talk_ids)
    click.echo(f"Talk IDs: {talk_tracker.format_unused_stats()} unused")

    readables_tracker = data_repo.get_readables()
    readables_tracker._accessed_ids.update(all_tracker_stats.accessed_readable_ids)
    click.echo(f"Readables: {readables_tracker.format_unused_stats()} unused")

    # Write unused stats to JSON file
    unused_stats_data = all_tracker_stats.to_dict(
        text_map_tracker, talk_tracker, readables_tracker
    )
    unused_stats_path = stats_dir / "unused_stats.json"
    with unused_stats_path.open("w", encoding="utf-8") as f:
        json.dump(unused_stats_data, f, indent=2, ensure_ascii=False)
    click.echo(f"Text map usage stats written to {unused_stats_path}")

    # Write manifest
    manifest_path = manifest.write_manifest(output_dir, manifest_list, name="agd")
    click.echo(f"Manifest written to {manifest_path}")

    if total_error > 0:
        click.echo(f"\nDetailed errors written to {errors_file_path}")
    else:
        # Remove empty errors file
        if errors_file_path.exists():
            errors_file_path.unlink()


@cli.group(name="render")
def render_group() -> None:
    """Render AGD content into RAG-suitable text format."""
    pass


@render_group.command("readable")
@click.argument("readable_path")
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


@render_group.command("talk")
@click.argument("talk_path")
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
            talk_info,
            talk_id=talk_id,
            talk_file_path=talk_path,
            language=localization.Language.CHS,
        )

        # Output only the content
        click.echo(rendered.content)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@render_group.command("quest")
@click.argument("quest_path")
def render_quest(quest_path: str) -> None:
    """Render quest dialog from the given path."""
    try:
        data_repo = repo.DataRepo.from_env()

        # Extract quest ID from path
        quest_id = pathlib.Path(quest_path).stem
        # Get quest info
        quest_info = processing.get_quest_info(quest_id, data_repo=data_repo)

        # Render the quest
        rendered = rendering.render_quest(
            quest_info, language=localization.Language.CHS
        )

        # Output only the content
        click.echo(rendered.content)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("list-readables")
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
