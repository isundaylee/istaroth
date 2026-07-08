#!/usr/bin/env python3
"""AGD tools for processing and rendering game content."""

import functools
import gc
import logging
import multiprocessing
import multiprocessing.pool
import os
import pathlib
import random
import shutil
import subprocess
import sys
from typing import Any, TextIO

import attrs
import click
import orjson
from tabulate import tabulate
from tqdm import tqdm

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.agd import (
    coop_hierarchy,
    first_seen,
    issues,
    localization,
    processed_types,
    quest_hierarchy,
    renderable_types,
    repo,
    tracking,
)
from istaroth.agd.renderables import (
    _talk,
    quest,
    readable,
)
from istaroth.text import manifest
from istaroth.text import types as text_types


@attrs.define
class _GenerationStats:
    """Success/error/skip/issue counts accumulated over one generation pass."""

    success: int
    error: int
    skipped: int
    issues: int

    def update(self, other: "_GenerationStats") -> None:
        """Accumulate another pass's counts into this one."""
        self.success += other.success
        self.error += other.error
        self.skipped += other.skipped
        self.issues += other.issues


@attrs.define
class _RenderableResult:
    """Result of processing a single renderable item."""

    renderable_key: str
    rendered_item: processed_types.RenderedItem | None
    error_message: str | None
    tracker_stats: tracking.TrackerStats
    parsing_issues: list[issues.ParsingIssue]


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


@functools.cache
def _get_first_seen_index() -> first_seen.FirstSeenIndex:
    return first_seen.FirstSeenIndex.load()


def _process_single_item(
    args: tuple[str, renderable_types.BaseRenderableType, bool],
) -> _RenderableResult:
    """Worker function to process a single renderable item."""
    renderable_key, renderable_type, strict = args
    data_repo = _get_data_repo_from_env()
    try:
        with data_repo.tracking_scope(
            item_type=type(renderable_type).__name__, item_key=str(renderable_key)
        ) as scope:
            rendered = renderable_type.process(
                renderable_key, data_repo, first_seen_index=_get_first_seen_index()
            )
        return _RenderableResult(
            renderable_key,
            rendered,
            None,
            tracking.TrackerStats(scope.accessed_ids),
            scope.issues,
        )
    except Exception as e:
        if strict:
            raise RuntimeError(f"Error processing {renderable_key}")
        return _RenderableResult(
            renderable_key,
            None,
            repr(e),
            tracking.TrackerStats.empty(),
            [],
        )


def _generate_content(
    renderable_type: renderable_types.BaseRenderableType,
    output_dir: pathlib.Path,
    *,
    data_repo: repo.DataRepo,
    pool: multiprocessing.pool.Pool,
    errors_file: TextIO | None = None,
    sample_rate: float = 1.0,
    strict: bool = False,
    manifest_list: list[text_types.TextMetadata],
    parsing_issues: list[issues.ParsingIssue],
) -> tuple[_GenerationStats, tracking.TrackerStats]:
    """Generate content files using renderable type."""
    stats = _GenerationStats(success=0, error=0, skipped=0, issues=0)
    tracker_stats = tracking.TrackerStats.empty()

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
            parsing_issues.extend(result.parsing_issues)
            stats.issues += len(result.parsing_issues)
            renderable_type_name = renderable_type.__class__.__name__

            if result.error_message is not None:
                log_message(
                    f"✗ {renderable_type_name}: {result.renderable_key} -> ERROR: {result.error_message}"
                )
                stats.error += 1

                # Check if error limit exceeded
                effective_error_limit = renderable_type.error_limit_for(
                    data_repo.language
                )
                if stats.error > effective_error_limit:
                    error_msg = f"Error limit exceeded ({stats.error} > {effective_error_limit}), stopping generation"
                    log_message(error_msg)
                    raise _ErrorLimitError(
                        renderable_type_name,
                        stats.error,
                        effective_error_limit,
                        result.error_message,
                    )

                continue

            # Skip if rendered is None (filtered out)
            if result.rendered_item is None:
                log_message(
                    f"⚠ {renderable_type_name}: {result.renderable_key} -> SKIPPED (filtered)"
                )
                stats.skipped += 1
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

            stats.success += 1

            if (
                renderable_type.success_limit is not None
                and stats.success >= renderable_type.success_limit
            ):
                error_msg = (
                    f"{renderable_type_name} rendered {stats.success} items, "
                    f"expected fewer than {renderable_type.success_limit}; "
                    "group the new loose content into a dedicated renderable "
                    "(see issue #105)"
                )
                log_message(f"✗ {error_msg}")
                raise RuntimeError(error_msg)

            pbar.set_postfix({"errors": stats.error, "skipped": stats.skipped})

    return stats, tracker_stats


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
@click.option(
    "--allow-errors",
    is_flag=True,
    help="Exit 0 even when some items failed to generate (default: exit 1 on any error)",
)
def generate_all(
    output_dir: pathlib.Path,
    force: bool,
    only: str | None,
    processes: int | None,
    sample_rate: float,
    strict: bool,
    allow_errors: bool,
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

    # Load the first-seen index before the pool forks so workers inherit it.
    _get_first_seen_index()

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
        if (agd_metadata := output_dir / "metadata" / "agd").exists():
            shutil.rmtree(agd_metadata)
        if (agd_manifest := output_dir / "manifest" / "agd.json").exists():
            agd_manifest.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create stats directory for AGD-specific output files
    stats_dir = output_dir / "stats" / "agd"
    stats_dir.mkdir(parents=True, exist_ok=True)

    # Generate and write metadata.json
    istaroth_path = pathlib.Path(__file__).parent.parent
    metadata = _generate_metadata(data_repo, istaroth_path)
    metadata_path = stats_dir / "metadata.json"
    metadata_path.write_bytes(orjson.dumps(metadata, option=orjson.OPT_INDENT_2))
    click.echo(f"Metadata written to {metadata_path}")

    total_stats = _GenerationStats(success=0, error=0, skipped=0, issues=0)
    all_tracker_stats = tracking.TrackerStats.empty()

    # Collect stats for summary table
    summary_stats = []

    # Manifest list to collect all text metadata
    manifest_list: list[text_types.TextMetadata] = []

    # Non-fatal parsing issues: per-category counts (for the JSON sidecar) and the
    # full list (for the detail file).
    issue_counts: dict[str, int] = {}
    all_parsing_issues: list[issues.ParsingIssue] = []

    # Helper function to process a content type and fold its counts into totals
    def process_content_type(renderable: renderable_types.BaseRenderableType) -> None:
        """Run one content type's generation and update global stats."""
        stats, tracker_stats = _generate_content(
            renderable,
            output_dir,
            data_repo=data_repo,
            pool=pool,
            errors_file=errors_file,
            sample_rate=sample_rate,
            strict=strict,
            manifest_list=manifest_list,
            parsing_issues=all_parsing_issues,
        )
        total_stats.update(stats)
        issue_counts[renderable.text_category.value] = stats.issues
        all_tracker_stats.update(tracker_stats)
        summary_stats.append(
            [
                renderable.text_category.value,
                stats.success,
                stats.error,
                stats.skipped,
                stats.issues,
            ]
        )

    only_category = text_types.TextCategory(only) if only else None

    def should_generate(category: text_types.TextCategory) -> bool:
        return only_category is None or only_category == category

    # Set up multiprocessing pool to reuse across all content generation
    if processes is None:
        processes = multiprocessing.cpu_count()

    # Pre-compute expensive mappings in parent process for inheritance via fork
    data_repo.precompute_for_fork()

    # Disable gc before forking: the setting is inherited by workers, so no worker
    # pays gc-pause overhead, and gc never traverses the huge inherited caches —
    # which would otherwise dirty copy-on-write pages and inflate memory. This is a
    # short-lived batch process, so leaked cycles are reclaimed at exit anyway.
    gc.disable()

    # Explicitly set start method to 'fork' to ensure child processes inherit
    # the pre-computed mapping from parent memory
    multiprocessing.set_start_method("fork", force=True)

    # Open errors file for writing
    errors_file_path = stats_dir / "errors.info"
    with (
        errors_file_path.open("w", encoding="utf-8") as errors_file,
        multiprocessing.Pool(processes=processes) as pool,
    ):
        # Each renderable knows its own category and how to build itself; the
        # trailing Readables/Talks passes read the tracker stats accumulated so
        # far to skip ids the earlier passes already claimed.
        for renderable_type in renderable_types.ALL_RENDERABLE_TYPES:
            if not should_generate(renderable_type.text_category):
                continue
            process_content_type(
                renderable_type.create_for_generation(all_tracker_stats)
            )

    # Create summary table
    headers = ["Content Type", "Success", "Errors", "Skipped", "Issues"]
    summary_stats.append(
        [
            "TOTAL",
            total_stats.success,
            total_stats.error,
            total_stats.skipped,
            total_stats.issues,
        ]
    )
    summary_table = tabulate(summary_stats, headers=headers, tablefmt="pretty")

    # Print summary table to console
    click.echo("\n" + summary_table)

    # Write summary table to file
    summary_table_path = stats_dir / "summary_table.txt"
    with summary_table_path.open("w", encoding="utf-8") as f:
        f.write(summary_table)
    click.echo(f"Summary table written to {summary_table_path}")

    # Merge this run's accessed ids into each tracked resource, then report the
    # unused counts. Keyed by tracker kind so adding a resource needs no changes here.
    scope_trackers = data_repo.build_scope_trackers()
    for kind, tracker in scope_trackers.items():
        tracker.merge_accessed(all_tracker_stats.accessed[kind])
        click.echo(f"{kind.label}: {tracker.format_unused_stats()} unused")

    # Write unused stats to JSON file
    unused_stats_data = all_tracker_stats.to_dict(scope_trackers)
    unused_stats_path = stats_dir / "unused_stats.json"
    unused_stats_path.write_bytes(
        orjson.dumps(unused_stats_data, option=orjson.OPT_INDENT_2)
    )
    click.echo(f"Text map usage stats written to {unused_stats_path}")

    # Write non-fatal parsing issue counts (by content type) and the full detail
    # list. Counts mirror the summary table's "Issues" column; the detail file
    # mirrors errors.info with one line per issue.
    parsing_issues_path = stats_dir / "parsing_issues.json"
    parsing_issues_path.write_bytes(
        orjson.dumps(issue_counts, option=orjson.OPT_INDENT_2)
    )
    click.echo(f"Parsing issue counts written to {parsing_issues_path}")

    if all_parsing_issues:
        parsing_issues_info_path = stats_dir / "parsing_issues.info"
        with parsing_issues_info_path.open("w", encoding="utf-8") as f:
            for issue in all_parsing_issues:
                f.write(
                    f"⚠ {issue.item_type}: {issue.item_key} -> "
                    f"{issue.issue_type.name}: {issue.detail}\n"
                )
        click.echo(f"Detailed parsing issues written to {parsing_issues_info_path}")

    # Write manifest
    manifest_path = manifest.write_manifest(output_dir, manifest_list, name="agd")
    click.echo(f"Manifest written to {manifest_path}")

    # Write the browsable document hierarchies, keyed by category, into one file.
    # Only categories with a dedicated builder are pre-baked here; flat categories
    # synthesize their (depth-1) tree from the manifest at request time. Each
    # builder runs only when its category was generated, and must then find items
    # in the manifest, so an empty bucket is a regression rather than a no-op.
    hierarchies: dict[str, dict[str, object]] = {}
    if should_generate(text_types.TextCategory.AGD_QUEST):
        quest_items = [
            (item.id, item.title)
            for item in manifest_list
            if item.category == text_types.TextCategory.AGD_QUEST
        ]
        assert quest_items, "quest generation produced no quest manifest items"
        hierarchies[text_types.TextCategory.AGD_QUEST.value] = (
            quest_hierarchy.build_quest_hierarchy(
                quest_items, data_repo=data_repo
            ).to_dict()
        )
    if should_generate(text_types.TextCategory.AGD_HANGOUT):
        coop_items = [
            (item.id, item.title)
            for item in manifest_list
            if item.category == text_types.TextCategory.AGD_HANGOUT
        ]
        assert coop_items, "hangout generation produced no coop manifest items"
        hierarchies[text_types.TextCategory.AGD_HANGOUT.value] = (
            coop_hierarchy.build_coop_hierarchy(
                coop_items, data_repo=data_repo
            ).to_dict()
        )
    if should_generate(text_types.TextCategory.AGD_QUEST) or should_generate(
        text_types.TextCategory.AGD_HANGOUT
    ):
        assert hierarchies, "expected at least one document hierarchy to write"
        metadata_dir = output_dir / "metadata" / "agd"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        hierarchy_path = metadata_dir / "hierarchy.json"
        hierarchy_path.write_bytes(
            orjson.dumps(hierarchies, option=orjson.OPT_INDENT_2)
        )
        click.echo(f"Document hierarchy written to {hierarchy_path}")

    if total_stats.error > 0:
        click.echo(f"\nDetailed errors written to {errors_file_path}")
    else:
        # Remove empty errors file
        if errors_file_path.exists():
            errors_file_path.unlink()

    # Fail loudly on any per-item error unless explicitly allowed, so regen
    # pipelines don't silently ship a corpus with missing items.
    exit_code = 1 if total_stats.error > 0 and not allow_errors else 0
    if exit_code:
        click.echo(
            f"\n{total_stats.error} item(s) failed to generate; "
            "pass --allow-errors to exit 0 anyway.",
            err=True,
        )

    # Skip interpreter teardown: with gc disabled and the large forked caches still
    # alive, normal shutdown wastes seconds finalizing objects we're about to
    # discard. Flush first since os._exit bypasses atexit and buffer flushing.
    sys.stdout.flush()
    sys.stderr.flush()
    logging.shutdown()
    os._exit(exit_code)


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
        metadata = readable.get_readable_metadata(
            pathlib.Path(readable_path).name, data_repo=data_repo
        )

        # Read the actual readable content
        readable_file_path = data_repo.agd_path / readable_path
        with open(readable_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Render the content
        rendered = readable.render_readable_like(
            content,
            metadata,
            pathlib.Path(readable_path).name,
            category=text_types.TextCategory.AGD_READABLE,
            first_seen_index=_get_first_seen_index(),
        )

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
        talk_info = _talk.get_talk_info(talk_path, data_repo=data_repo)

        # Extract talk ID from path (e.g., "BinOutput/Talk/NPC/100001.json" -> 100001)
        talk_id = int(pathlib.Path(talk_path).stem)

        # Render the talk
        rendered = _talk.render_talk(
            talk_info,
            talk_id=talk_id,
            talk_file_path=talk_path,
            language=localization.Language.CHS,
            first_seen_index=_get_first_seen_index(),
        )

        # Output only the content
        if rendered is None:
            click.echo("(no dialog line survives rendering)", err=True)
        else:
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
        quest_id = int(pathlib.Path(quest_path).stem)
        # Get quest info
        if (quest_info := quest.get_quest_info(quest_id, data_repo=data_repo)) is None:
            raise click.ClickException(f"Quest {quest_id} is a test/hidden quest")

        # Render the quest
        rendered = quest.render_quest(
            quest_info,
            language=localization.Language.CHS,
            first_seen_index=_get_first_seen_index(),
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
        try:
            metadata = readable.get_readable_metadata(
                txt_file.name, data_repo=data_repo
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
