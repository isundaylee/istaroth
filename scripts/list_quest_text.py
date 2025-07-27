#!/usr/bin/env python3
"""Helper script to display talk dialog text in a readable format."""

import os
import pathlib
import sys

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.agd import processing, repo


def main() -> None:
    """Display talk dialog text for specified talk file."""
    if len(sys.argv) != 2:
        print("Usage: python list_quest_text.py <talk_path>", file=sys.stderr)
        print(
            "Example: python list_quest_text.py BinOutput/Talk/Quest/7407811.json",
            file=sys.stderr,
        )
        sys.exit(1)

    talk_path = sys.argv[1]

    try:
        data_repo = repo.DataRepo.from_env()
        talk_info = processing.get_talk_info(talk_path, data_repo=data_repo)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Talk Dialog: {talk_path}")
    print("=" * 80)
    print()

    for i, talk_text in enumerate(talk_info.text, 1):
        print(f"{i:3d}. [{talk_text.role}]")
        print(f"     {talk_text.message}")
        print()

    print("=" * 80)
    print(f"Total dialog lines: {len(talk_info.text)}")


if __name__ == "__main__":
    main()
