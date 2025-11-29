"""Text set for accessing text files organized by category."""

import pathlib

import attrs

from istaroth.agd import localization


def get_category_prefix(category: str) -> str:
    """Get the expected filename prefix for a category.

    Maps category names to their expected file prefix. This handles cases where
    the category name (plural) differs from the file prefix (often singular).

    Raises:
        ValueError: If the category is not in the known mapping.
    """
    category_prefix_map = {
        "artifact_sets": "artifact_set_",
        "character_stories": "character_story_",
        "material_types": "material_type_",
        "quest": "quest_",
        "readable": "readable_",
        "subtitles": "subtitle_",
        "talk_groups": "talk_group_",
        "talks": "talk_",
        "voicelines": "voiceline_",
    }
    if category not in category_prefix_map:
        raise ValueError(f"Unknown category: {category}")
    return category_prefix_map[category]


def get_category_from_filename(filename: str) -> str:
    """Get the category from a filename by matching its prefix.

    Returns the category name if the filename starts with a known category prefix,
    otherwise raises ValueError.
    """
    category_prefix_map = {
        "artifact_sets": "artifact_set_",
        "character_stories": "character_story_",
        "material_types": "material_type_",
        "quest": "quest_",
        "readable": "readable_",
        "subtitles": "subtitle_",
        "talk_groups": "talk_group_",
        "talks": "talk_",
        "voicelines": "voiceline_",
    }

    name_without_ext = filename[:-4] if filename.endswith(".txt") else filename

    for category, prefix in category_prefix_map.items():
        if name_without_ext.startswith(prefix):
            return category

    raise ValueError(f"Unknown category prefix in filename: {filename}")


@attrs.define
class TextSet:
    """Set of text files organized by category for a language."""

    checkpoint_path: pathlib.Path
    language: localization.Language

    @property
    def _text_directory(self) -> pathlib.Path:
        """Get text directory path."""
        return self.checkpoint_path / "text" / "agd"

    def get_categories(self) -> list[str]:
        """Get list of all category names."""
        text_dir = self._text_directory
        categories = []
        for item in text_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                categories.append(item.name)
        categories.sort()
        return categories

    def get_files(self, category: str) -> list[str]:
        """Get list of all .txt files in a category."""
        text_dir = self._text_directory
        category_dir = text_dir / category
        if not category_dir.exists() or not category_dir.is_dir():
            raise ValueError(f"Category not found: {category}")

        files = []
        for item in category_dir.glob("*.txt"):
            files.append(item.name)
        files.sort()
        return files

    def get_file_content(self, category: str, filename: str) -> str:
        """Get full text content of a file."""
        return (self._text_directory / category / filename).read_text(encoding="utf-8")
