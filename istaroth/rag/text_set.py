"""Text set for accessing text files organized by category."""

import pathlib

import attrs

from istaroth.agd import localization


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
