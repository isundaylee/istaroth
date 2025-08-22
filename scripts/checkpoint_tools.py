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


def download_checkpoint(
    language: localization.Language,
    target_dir: pathlib.Path,
    release: str = "latest",
) -> None:
    """Download and extract checkpoint for a specific language."""
    # Create URL for the checkpoint
    base_url = f"https://github.com/isundaylee/istaroth/releases/{release}/download"
    checkpoint_url = f"{base_url}/{language.value.lower()}.tar.gz"

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
def download(language: str, target_path: pathlib.Path):
    """Download checkpoint for a specific language."""
    if target_path.exists():
        logger.info("Target path %s already exists, skipping download.", target_path)
        return

    download_checkpoint(localization.Language(language.upper()), target_path, "latest")


if __name__ == "__main__":
    cli()
