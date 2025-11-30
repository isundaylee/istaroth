"""Generic manifest utilities for text files."""

import json
import pathlib

from istaroth.text import types


def write_manifest(
    output_dir: pathlib.Path, manifest: list[types.TextMetadata]
) -> None:
    """Write manifest to JSON file."""
    manifest_path = output_dir / "manifest.json"
    manifest_data = [item.to_dict() for item in manifest]
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
