#!/usr/bin/env python3
"""Verify that text files follow the expected naming pattern.

Expected format: {category}_{name}_{id}.txt or {category}_{name}.txt
Files must be in category subdirectories and start with the category name.
"""

import logging
import pathlib
import sys

import click

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.rag import text_set

logger = logging.getLogger(__name__)


def _verify_filename(filename: str, category: str) -> tuple[bool, str]:
    """Verify a filename follows the expected pattern.

    Returns:
        (is_valid, error_message)
    """
    if not filename.endswith(".txt"):
        return False, f"File does not end with .txt: {filename}"

    expected_prefix = text_set.get_category_prefix(category)
    if not filename.startswith(expected_prefix):
        return (
            False,
            f"File does not start with category prefix '{expected_prefix}': {filename}",
        )

    name_without_ext = filename[:-4]  # Remove .txt
    name_without_category = name_without_ext[len(expected_prefix) :]

    if not name_without_category:
        return False, f"File has no content after category prefix: {filename}"

    # Check if there's an ID (last part after final underscore should be an integer)
    last_underscore = name_without_category.rfind("_")
    if last_underscore != -1:
        potential_id = name_without_category[last_underscore + 1 :]
        if potential_id:
            try:
                int(potential_id)
                # Valid ID found - empty name is allowed when there's an ID
                # (e.g., readable__200571.txt is valid with empty name)
            except ValueError:
                # Not an integer, which is fine - it's just part of the name
                pass

    return True, ""


def verify_text_directory(text_path: pathlib.Path) -> tuple[bool, list[str]]:
    """Verify all text files in a directory follow the naming pattern.

    Args:
        text_path: Path to text directory (should contain category subdirectories)

    Returns:
        (all_valid, list_of_errors)
    """
    errors = []

    if not text_path.exists():
        errors.append(f"Text directory does not exist: {text_path}")
        return False, errors

    if not text_path.is_dir():
        errors.append(f"Text path is not a directory: {text_path}")
        return False, errors

    # Get all category directories
    categories = []
    for item in text_path.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            categories.append(item.name)

    if not categories:
        errors.append(f"No category directories found in {text_path}")
        return False, errors

    # Verify files in each category
    total_files = 0
    invalid_files = 0

    for category in sorted(categories):
        category_dir = text_path / category
        files = list(category_dir.glob("*.txt"))
        total_files += len(files)

        for file_path in files:
            filename = file_path.name
            is_valid, error_msg = _verify_filename(filename, category)
            if not is_valid:
                invalid_files += 1
                errors.append(f"{file_path.relative_to(text_path)}: {error_msg}")

    if invalid_files > 0:
        logger.error(
            f"Found {invalid_files} invalid file(s) out of {total_files} total file(s)"
        )
        return False, errors

    logger.info(f"All {total_files} file(s) follow the expected naming pattern")
    return True, []


@click.command()
@click.argument(
    "text_path",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, path_type=pathlib.Path
    ),
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(text_path: pathlib.Path, verbose: bool) -> None:
    """Verify that text files follow the expected naming pattern.

    TEXT_PATH: Path to text directory containing category subdirectories
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    all_valid, errors = verify_text_directory(text_path)

    if errors:
        click.echo("\nErrors found:", err=True)
        for error in errors:
            click.echo(f"  {error}", err=True)

    if not all_valid:
        sys.exit(1)

    click.echo("✓ All files follow the expected naming pattern")


if __name__ == "__main__":
    main()
