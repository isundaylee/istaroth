"""Catalog of complete, unchunked text files organized by category.

Unlike DocumentStore which chunks and indexes files for similarity search,
TextSet provides direct access to whole source files via a manifest of
TextMetadata entries (category, title, id, relative_path). Both operate on
the same underlying text files; a DocumentStoreSet exposes both views.
"""

import functools
import hashlib
import json
import pathlib
from typing import Any

import attrs

from istaroth import json_utils
from istaroth.agd import localization
from istaroth.text import manifest as text_manifest
from istaroth.text import types as text_types

# Frequently browsed categories lead the library display order; anything not
# listed follows, sorted by category value.
_CATEGORY_DISPLAY_ORDER = (
    text_types.TextCategory.AGD_BOOK,
    text_types.TextCategory.AGD_QUEST,
    text_types.TextCategory.AGD_HANGOUT,
    text_types.TextCategory.AGD_ANECDOTE,
    text_types.TextCategory.AGD_ARTIFACT_SET,
    text_types.TextCategory.AGD_WEAPON,
    text_types.TextCategory.AGD_WINGS,
    text_types.TextCategory.AGD_COSTUME,
    text_types.TextCategory.AGD_CHARACTER_STORY,
    text_types.TextCategory.AGD_VOICELINE,
    text_types.TextCategory.AGD_READABLE,
)


def _version_sort_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _category_display_order(category: text_types.TextCategory) -> tuple[int, str]:
    try:
        index = _CATEGORY_DISPLAY_ORDER.index(category)
    except ValueError:
        index = len(_CATEGORY_DISPLAY_ORDER)
    return (index, category.value)


def _sort_nodes_by_version(
    nodes: list[dict[str, Any]], max_versions: dict[int, str | None]
) -> tuple[list[dict[str, Any]], str | None]:
    """Sort sibling nodes newest subtree max_version first, recursively.

    Group nodes order by the newest version among their descendant leaves, so
    recently updated content bubbles to the top at every level. The sort is
    stable: ties and versionless nodes (which trail) keep their original
    relative order. Each node copy is annotated with its subtree max_version;
    returns sorted copies plus the subtree's newest version.
    """
    keyed = []
    for node in nodes:
        if (children := node["children"]) is not None:
            children, version = _sort_nodes_by_version(children, max_versions)
            node = node | {"children": children, "max_version": version}
        else:
            version = max_versions[node["file_id"]]
            node = node | {"max_version": version}
        key = _version_sort_key(version) if version is not None else None
        keyed.append((key, version, node))
    keyed.sort(
        key=lambda kvn: (1, ()) if kvn[0] is None else (0, tuple(-p for p in kvn[0]))
    )
    # Versioned entries sort first (newest first), so the head holds the max.
    return [node for *_, node in keyed], (
        keyed[0][1] if keyed and keyed[0][0] is not None else None
    )


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

    @functools.cached_property
    def _prebaked_hierarchies(self) -> dict[str, Any]:
        """All pre-baked document hierarchies, keyed by category value."""
        path = self.text_path / "metadata" / "agd" / "hierarchy.json"
        if not path.exists():
            return {}
        return json.loads(path.read_bytes())

    def get_hierarchy_for_category(self, category: str) -> dict[str, Any] | None:
        """Return the pre-baked document hierarchy for a category, or None.

        Only categories with a dedicated builder (quests, hangouts) are pre-baked;
        flat categories return None and are synthesized from the manifest by the
        caller.
        """
        return self._prebaked_hierarchies.get(category)

    @functools.cached_property
    def _library_hierarchies(self) -> dict[str, Any]:
        """Every category's document tree, keyed by category value in display order.

        Pre-baked trees (quests, hangouts) are used for structure; every other
        category gets a flat, depth-1 tree of file leaves synthesized from the
        manifest. Either way, sibling nodes at every level are ordered newest
        subtree max_version first.
        """
        combined: dict[str, Any] = {}
        for category in sorted(
            {item.category for item in self._manifest}, key=_category_display_order
        ):
            if (prebaked := self._prebaked_hierarchies.get(category.value)) is not None:
                nodes = prebaked["nodes"]
            else:
                nodes = [
                    {
                        "key": f"q{item.id}",
                        "title": item.title,
                        "children": None,
                        "file_id": item.id,
                        "toc_eligible": False,
                    }
                    for item in sorted(
                        (i for i in self._manifest if i.category == category),
                        key=lambda i: i.id,
                    )
                ]
            combined[category.value] = {
                "nodes": _sort_nodes_by_version(
                    nodes,
                    {
                        i.id: i.max_version
                        for i in self._manifest
                        if i.category == category
                    },
                )[0]
            }
        return combined

    def get_library_hierarchies(self) -> dict[str, Any]:
        """Get every category's document tree, keyed by category value."""
        return self._library_hierarchies

    @functools.cached_property
    def latest_version(self) -> str | None:
        """Newest first-seen game version across the manifest; None if all versionless."""
        return max(
            (v for item in self._manifest if (v := item.max_version) is not None),
            key=_version_sort_key,
            default=None,
        )

    @functools.cached_property
    def library_hierarchies_content_hash(self) -> str:
        """Hash of the library hierarchies, usable as an HTTP ETag ingredient."""
        return hashlib.sha256(json_utils.dumps(self._library_hierarchies)).hexdigest()
