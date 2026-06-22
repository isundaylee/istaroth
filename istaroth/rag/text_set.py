"""Catalog of complete, unchunked text files organized by category.

Unlike DocumentStore which chunks and indexes files for similarity search,
TextSet provides direct access to whole source files via a manifest of
TextMetadata entries (category, title, id, relative_path). Both operate on
the same underlying text files; a DocumentStoreSet exposes both views.
"""

import functools
import json
import pathlib
from typing import Any

import attrs

from istaroth.agd import localization
from istaroth.text import manifest as text_manifest
from istaroth.text import types as text_types


@attrs.define
class TextSet:
    """Manifest-indexed collection of complete text files for one language.

    Provides lookup and content access by category/id or relative path, backed
    by JSON manifest files on disk. No search capability — for retrieval, use
    the companion DocumentStore which chunks and embeds the same source files.
    """

    text_path: pathlib.Path
    language: localization.Language

    @functools.cached_property
    def _manifest(self) -> tuple[text_types.TextMetadata, ...]:
        """Load and merge all manifest files from the manifest directory."""
        return text_manifest.load_manifest_dir(self.text_path)

    @functools.cached_property
    def _manifest_by_relative_path(self) -> dict[str, text_types.TextMetadata]:
        """Dictionary mapping relative_path to TextMetadata for fast lookup."""
        return {item.relative_path: item for item in self._manifest}

    def get_manifest(self) -> list[text_types.TextMetadata]:
        """Get all manifest items."""
        return list(self._manifest)

    def get_manifest_item(
        self, category: text_types.TextCategory, id: int
    ) -> text_types.TextMetadata | None:
        """Get a specific manifest item by category and id."""
        for item in self._manifest:
            if item.category == category and item.id == id:
                return item
        return None

    def get_manifest_item_by_relative_path(
        self, relative_path: str
    ) -> text_types.TextMetadata | None:
        """Get a specific manifest item by relative_path."""
        return self._manifest_by_relative_path.get(relative_path)

    def get_content(self, relative_path: str) -> str | None:
        """Get file content by relative_path.

        Returns:
            File content as string, or None if the file does not exist.
        """
        file_path = self.text_path / relative_path
        if not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    def load_hierarchy(self) -> dict[str, Any]:
        """Load all pre-baked document hierarchies, keyed by category value."""
        path = self.text_path / "metadata" / "agd" / "hierarchy.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def get_hierarchy_for_category(self, category: str) -> dict[str, Any] | None:
        """Return the pre-baked document hierarchy for a category, or None.

        Only categories with a dedicated builder (quests, hangouts) are pre-baked;
        flat categories return None and are synthesized from the manifest by the
        caller.
        """
        return self.load_hierarchy().get(category)
