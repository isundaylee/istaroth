"""Generic manifest utilities for text files."""

import collections
import json
import pathlib

from istaroth import json_utils
from istaroth.text import types

_MANIFEST_DIR_NAME = "manifest"


def write_manifest(
    output_dir: pathlib.Path, manifest: list[types.TextMetadata], *, name: str
) -> pathlib.Path:
    """Write manifest to a named JSON file inside the manifest directory."""
    # (category, id) is the lookup key for every id-keyed surface (library file
    # endpoint, TOC, citations); a duplicate silently shadows a file (issue
    # #294), so fail generation loudly instead.
    if duplicates := [
        key
        for key, count in collections.Counter(
            (item.category, item.id) for item in manifest
        ).items()
        if count > 1
    ]:
        raise ValueError(f"Duplicate manifest (category, id) keys: {duplicates}")
    manifest_dir = output_dir / _MANIFEST_DIR_NAME
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{name}.json"
    manifest_data = [item.to_dict() for item in manifest]
    manifest_path.write_bytes(json_utils.dumps_indented(manifest_data))
    return manifest_path


def load_manifest_dir(
    base_dir: pathlib.Path,
) -> tuple[types.TextMetadata, ...]:
    """Load and merge all manifest JSON files from the manifest directory."""
    manifest_dir = base_dir / _MANIFEST_DIR_NAME
    if not manifest_dir.is_dir():
        raise FileNotFoundError(f"Manifest directory not found: {manifest_dir}")
    items: list[types.TextMetadata] = []
    for path in sorted(manifest_dir.glob("*.json")):
        data = json.loads(path.read_bytes())
        items.extend(types.TextMetadata.from_dict(entry) for entry in data)
    return tuple(items)
