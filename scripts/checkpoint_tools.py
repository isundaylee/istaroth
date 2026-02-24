#!/usr/bin/env python3
"""Checkpoint management tools for Istaroth."""

import logging
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

import click

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.agd import localization

logger = logging.getLogger(__name__)


def _get_release_tag_file(target_dir: pathlib.Path) -> pathlib.Path:
    """Get the path to the release tag file for a checkpoint directory."""
    return target_dir.parent / f"{target_dir.name}.release"


def _read_release_tag(target_dir: pathlib.Path) -> str | None:
    """Read the release version from the tag file, if it exists."""
    tag_file = _get_release_tag_file(target_dir)
    if tag_file.exists():
        return tag_file.read_text().strip()
    return None


def _write_release_tag(target_dir: pathlib.Path, release: str) -> None:
    """Write the release version to the tag file."""
    tag_file = _get_release_tag_file(target_dir)
    tag_file.write_text(release)
    logger.info("Recorded release version '%s' in tag file %s", release, tag_file)


def download_checkpoint(
    language: localization.Language,
    target_dir: pathlib.Path,
    release: str = "latest",
) -> None:
    """Download and extract checkpoint for a specific language."""
    # Check if checkpoint exists and if release version differs
    if target_dir.exists():
        existing_release = _read_release_tag(target_dir)
        if (
            existing_release is not None
            and existing_release != release
            and release != "latest"
        ):
            logger.info(
                "Checkpoint exists with release '%s', but requested release is '%s'. "
                "Deleting existing checkpoint to force re-download.",
                existing_release,
                release,
            )
            shutil.rmtree(target_dir)
            tag_file = _get_release_tag_file(target_dir)
            if tag_file.exists():
                tag_file.unlink()
        else:
            logger.info(
                "Checkpoint already exists with release '%s', skipping download.",
                release,
            )
            return

    # Create URL for the checkpoint
    if release == "latest":
        checkpoint_url = (
            f"https://github.com/isundaylee/istaroth/releases/latest/download/"
            f"{language.value.lower()}.tar.gz"
        )
    else:
        checkpoint_url = (
            f"https://github.com/isundaylee/istaroth/releases/download/"
            f"{release}/{language.value.lower()}.tar.gz"
        )

    logger.info(
        "Downloading checkpoint for language '%s' from %s",
        language.name,
        checkpoint_url,
    )

    # Create tmp directory if it doesn't exist
    tmp_dir = target_dir.parent / f"{target_dir.name}.tmp{time.time()}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Download to temporary file
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_path = pathlib.Path(temp_file.name)
        try:
            with urlopen(checkpoint_url) as response:
                # Show progress for large downloads
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    temp_file.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(
                            f"\rDownloading: {progress:.1f}% ({downloaded}/{total_size} bytes)",
                            end="",
                            flush=True,
                        )

            print()  # New line after progress
            logger.info("Downloaded checkpoint to temporary file: %s", temp_path)
        except:
            temp_path.unlink(missing_ok=True)
            raise

    # Extract tar.gz to temporary directory using command line tar
    logger.info("Extracting checkpoint...")
    try:
        subprocess.run(["tar", "-xzf", str(temp_path), "-C", str(tmp_dir)], check=True)
    finally:
        # Clean up temporary file
        temp_path.unlink(missing_ok=True)

    # Atomically move to target directory
    if target_dir.exists():
        logger.warning(
            "Target directory %s already exists, backing up to %s.backup",
            target_dir,
            target_dir,
        )
        backup_dir = target_dir.parent / f"{target_dir.name}.backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        target_dir.rename(backup_dir)

    tmp_dir.rename(target_dir)
    _write_release_tag(target_dir, release)
    logger.info("Successfully extracted checkpoint to %s", target_dir)


@click.group()
def cli():
    """Checkpoint management tools for Istaroth."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


@cli.command()
@click.argument(
    "language",
    type=click.Choice(
        [lang.value.lower() for lang in localization.Language], case_sensitive=False
    ),
)
@click.argument("target_path", type=pathlib.Path)
@click.option(
    "--release",
    default="latest",
    help="Release version or tag to download (default: latest)",
)
def download(language: str, target_path: pathlib.Path, release: str):
    """Download checkpoint for a specific language."""
    download_checkpoint(localization.Language(language.upper()), target_path, release)


@cli.command()
@click.argument("checkpoints_dir", type=pathlib.Path)
@click.option("--keep", required=True, help="Release directory name to keep")
def cleanup(checkpoints_dir: pathlib.Path, keep: str):
    """Remove old checkpoint versions, keeping only the specified release."""
    if not checkpoints_dir.is_dir():
        logger.warning(
            "Checkpoints directory %s does not exist, nothing to clean", checkpoints_dir
        )
        return

    keep_dir = checkpoints_dir / keep
    if not keep_dir.is_dir():
        raise click.ClickException(
            f"Checkpoint to keep does not exist: {keep_dir}. "
            "Refusing to clean up to avoid deleting all checkpoints."
        )

    for entry in sorted(checkpoints_dir.iterdir()):
        if entry.name == keep:
            continue
        if entry.is_dir():
            logger.info("Removing old checkpoint directory: %s", entry)
            shutil.rmtree(entry)
        else:
            logger.info("Removing stale file: %s", entry)
            entry.unlink()


if __name__ == "__main__":
    cli()
