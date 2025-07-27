#!/usr/bin/env python3
"""Helper script to display quest dialog text in a readable format."""

import os
import pathlib
import sys

# Add the parent directory to Python path to find istorath module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istorath.agd import processing, repo


def main() -> None:
    """Display quest dialog text for specified quest file."""
    if len(sys.argv) != 2:
        print("Usage: python list_quest_text.py <quest_path>", file=sys.stderr)
        print(
            "Example: python list_quest_text.py BinOutput/Talk/Quest/7407811.json",
            file=sys.stderr,
        )
        sys.exit(1)

    quest_path = sys.argv[1]

    try:
        data_repo = repo.DataRepo.from_env()
        quest_info = processing.get_quest_info(quest_path, data_repo=data_repo)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Quest Dialog: {quest_path}")
    print("=" * 80)
    print()

    for i, quest_text in enumerate(quest_info.text, 1):
        print(f"{i:3d}. [{quest_text.role}]")
        print(f"     {quest_text.message}")
        print()

    print("=" * 80)
    print(f"Total dialog lines: {len(quest_info.text)}")


if __name__ == "__main__":
    main()
