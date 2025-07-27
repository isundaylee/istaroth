"""Renderable content type classes for different AGD content."""

from abc import ABC, abstractmethod

from istorath.agd import processing, rendering, repo, types


class BaseRenderableType(ABC):
    """Abstract base class for renderable content types."""

    @abstractmethod
    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find and return list of files for this renderable type."""
        pass

    @abstractmethod
    def process(self, file_path: str, data_repo: repo.DataRepo) -> types.RenderedItem:
        """Process file into rendered content."""
        pass


class Readables(BaseRenderableType):
    """Readable content type (books, weapons, etc.)."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all readable files."""
        readable_dir = data_repo.agd_path / "Readable" / data_repo.language
        if readable_dir.exists():
            return [
                f"Readable/{data_repo.language}/{txt_file.name}"
                for txt_file in readable_dir.glob("*.txt")
            ]
        return []

    def process(self, file_path: str, data_repo: repo.DataRepo) -> types.RenderedItem:
        """Process readable file into rendered content."""
        # Get readable metadata
        metadata = processing.get_readable_metadata(file_path, data_repo=data_repo)

        # Read the actual readable content
        readable_file_path = data_repo.agd_path / file_path
        with open(readable_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Render the content
        return rendering.render_readable(content, metadata)


class Quests(BaseRenderableType):
    """Quest content type (dialog, cutscenes, etc.)."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all quest files."""
        quest_dir = data_repo.agd_path / "BinOutput" / "Quest"
        if quest_dir.exists():
            return [
                f"BinOutput/Quest/{json_file.name}"
                for json_file in quest_dir.glob("*.json")
                if json_file.stem.isdigit()  # Skip non-numeric quest files
            ]
        return []

    def process(self, file_path: str, data_repo: repo.DataRepo) -> types.RenderedItem:
        """Process quest file into rendered content."""
        # Get quest info
        quest_info = processing.get_quest_info(file_path, data_repo=data_repo)

        # Render the quest
        return rendering.render_quest(quest_info)
