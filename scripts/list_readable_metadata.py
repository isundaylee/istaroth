#!/usr/bin/env python3
"""Helper script to list readable metadata for all files under <AGD>/Readable/CHS."""

import os
import pathlib
import sys

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.agd import processing, repo


def main() -> None:
    """List readable metadata for all CHS files."""
    agd_path = os.environ.get("AGD_PATH")
    if not agd_path:
        print("Error: AGD_PATH environment variable not set", file=sys.stderr)
        sys.exit(1)

    data_repo = repo.DataRepo(agd_path)
    readable_dir = pathlib.Path(agd_path) / "Readable" / "CHS"

    if not readable_dir.exists():
        print(f"Error: Directory {readable_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    print("Readable Metadata:")
    print("=" * 50)

    # Find all .txt files in the readable directory
    txt_files = sorted(readable_dir.glob("*.txt"))

    success_count = 0
    error_count = 0

    for txt_file in txt_files:
        relative_path = f"Readable/CHS/{txt_file.name}"
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
