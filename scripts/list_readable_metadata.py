#!/usr/bin/env python3
"""Helper script to list readable metadata for all files under <AGD>/Readable/<LANGUAGE>."""

import os
import pathlib
import sys

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.agd import processing, repo


def main() -> None:
    """List readable metadata for all files in the configured language."""
    try:
        data_repo = repo.DataRepo.from_env()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    readable_dir = data_repo.agd_path / "Readable" / data_repo.language

    if not readable_dir.exists():
        print(f"Error: Directory {readable_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"Readable Metadata ({data_repo.language}):")
    print("=" * 50)

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
            print(f"{txt_file.name:<20} -> {metadata.title}")
            success_count += 1
        except Exception as e:
            print(f"{txt_file.name:<20} -> ERROR: {e}")
            error_count += 1

    print("=" * 50)
    print(
        f"Processed {len(txt_files)} files: {success_count} success, {error_count} errors"
    )


if __name__ == "__main__":
    main()
