"""Generic manifest utilities for text files."""

import pathlib

import orjson

from istaroth.text import types

_MANIFEST_DIR_NAME = "manifest"


def write_manifest(
    output_dir: pathlib.Path, manifest: list[types.TextMetadata], *, name: str
) -> pathlib.Path:
    """Write manifest to a named JSON file inside the manifest directory."""
    manifest_dir = output_dir / _MANIFEST_DIR_NAME
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{name}.json"
    manifest_data = [item.to_dict() for item in manifest]
    manifest_path.write_bytes(orjson.dumps(manifest_data, option=orjson.OPT_INDENT_2))
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
        data = orjson.loads(path.read_bytes())
        items.extend(types.TextMetadata.from_dict(entry) for entry in data)
    return tuple(items)
