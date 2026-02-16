"""Generic manifest utilities for text files."""

import json
import pathlib

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
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
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
        data = json.loads(path.read_text(encoding="utf-8"))
        items.extend(types.TextMetadata.from_dict(entry) for entry in data)
    return tuple(items)
