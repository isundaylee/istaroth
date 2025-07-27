"""Renderable content type classes for different AGD content."""

from abc import ABC, abstractmethod
from typing import ClassVar

from istorath.agd import processing, rendering, repo, types


class BaseRenderableType(ABC):
    """Abstract base class for renderable content types."""

    error_limit: ClassVar[int] = 0  # Default error limit

    @abstractmethod
    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find and return list of renderable keys for this renderable type."""
        pass

    @abstractmethod
    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem:
        """Process renderable key into rendered content."""
        pass


class Readables(BaseRenderableType):
    """Readable content type (books, weapons, etc.)."""

    error_limit: ClassVar[int] = 50

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all readable files."""
        readable_dir = data_repo.agd_path / "Readable" / data_repo.language
        if readable_dir.exists():
            return [
                f"Readable/{data_repo.language}/{txt_file.name}"
                for txt_file in readable_dir.glob("*.txt")
            ]
        return []

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem:
        """Process readable file into rendered content."""
        # Get readable metadata
        metadata = processing.get_readable_metadata(renderable_key, data_repo=data_repo)

        # Read the actual readable content
        readable_file_path = data_repo.agd_path / renderable_key
        with open(readable_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Render the content
        return rendering.render_readable(content, metadata)


class Quests(BaseRenderableType):
    """Quest content type (dialog, cutscenes, etc.)."""

    error_limit: ClassVar[int] = 100

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

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem:
        """Process quest file into rendered content."""
        # Get quest info
        quest_info = processing.get_quest_info(renderable_key, data_repo=data_repo)

        # Render the quest
        return rendering.render_quest(quest_info)


class UnusedTexts(BaseRenderableType):
    """Unused text map entries content type."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Return a single placeholder file since unused texts are generated dynamically."""
        return ["unused_text_map"]

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem:
        """Process unused text map entries into rendered content."""
        # Get unused text map info
        unused_info = processing.get_unused_text_map_info(data_repo=data_repo)

        # Render the unused texts
        return rendering.render_unused_text_map(unused_info)


class CharacterStories(BaseRenderableType):
    """Character story content type."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all unique character IDs that have stories."""
        fetter_data = data_repo.load_fetter_story_excel_config_data()

        # Collect unique avatar IDs that have stories
        avatar_ids = set()
        for story in fetter_data:
            avatar_id = story.get("avatarId")
            if avatar_id:
                avatar_ids.add(avatar_id)

        # Return avatar IDs as strings for processing
        return [str(avatar_id) for avatar_id in sorted(avatar_ids)]

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem:
        """Process character story into rendered content."""
        # Get character story info
        story_info = processing.get_character_story_info(
            renderable_key, data_repo=data_repo
        )

        # Render the character story
        return rendering.render_character_story(story_info)
