"""Renderable content type classes for different AGD content."""

from abc import ABC, abstractmethod
from typing import ClassVar

from istaroth.agd import processing, rendering, repo, types


def _should_skip(title: str, language: str) -> bool:
    """Skip test items only for CHS language."""
    if language != "CHS":
        return False
    lower_title = title.lower()
    return (
        lower_title.startswith(("test", "(test", "（test"))
        or "$hidden" in lower_title
        or "$unreleased" in lower_title
    )


class BaseRenderableType(ABC):
    """Abstract base class for renderable content types."""

    error_limit: ClassVar[int] = 0  # Default error limit
    error_limit_non_chinese: ClassVar[int] = 0  # Higher limit for non-Chinese languages

    @abstractmethod
    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find and return list of renderable keys for this renderable type."""
        pass

    @abstractmethod
    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process renderable key into rendered content."""
        pass


class Readables(BaseRenderableType):
    """Readable content type (books, weapons, etc.)."""

    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all readable files."""
        readable_dir = data_repo.agd_path / "Readable" / data_repo.language_short
        if readable_dir.exists():
            return [
                f"Readable/{data_repo.language_short}/{txt_file.name}"
                for txt_file in readable_dir.glob("*.txt")
            ]
        return []

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process readable file into rendered content."""
        # Get readable metadata
        metadata = processing.get_readable_metadata(renderable_key, data_repo=data_repo)

        # Skip if title starts with "test" (case-insensitive) and language is CHS
        if _should_skip(metadata.title, data_repo.language):
            return None

        # Read the actual readable content
        readable_file_path = data_repo.agd_path / renderable_key
        with open(readable_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Render the content
        return rendering.render_readable(content, metadata)


class Quests(BaseRenderableType):
    """Quest content type (dialog, cutscenes, etc.)."""

    error_limit: ClassVar[int] = 100
    error_limit_non_chinese: ClassVar[int] = 2000

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all quest IDs from MainQuestExcelConfigData."""
        main_quest_data = data_repo.load_main_quest_excel_config_data()

        # Get all quest IDs from the Excel data
        quest_ids = [str(quest_entry["id"]) for quest_entry in main_quest_data]

        return sorted(quest_ids)

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process quest file into rendered content."""
        # Convert quest ID to path
        quest_path = f"BinOutput/Quest/{renderable_key}.json"

        # Check if quest file exists
        file_path = data_repo.agd_path / quest_path
        if not file_path.exists():
            return None

        # Get quest info
        quest_info = processing.get_quest_info(quest_path, data_repo=data_repo)

        # Skip if title starts with "test" (case-insensitive) and language is CHS
        if _should_skip(quest_info.title, data_repo.language):
            return None

        if not (quest_info.talks or quest_info.non_subquest_talks):
            # If no talks, skip rendering
            return None

        # Render the quest
        return rendering.render_quest(quest_info)


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
    ) -> types.RenderedItem | None:
        """Process character story into rendered content."""
        # Get character story info
        story_info = processing.get_character_story_info(
            renderable_key, data_repo=data_repo
        )

        # Render the character story
        return rendering.render_character_story(story_info)


class Subtitles(BaseRenderableType):
    """Subtitle content type (.srt files)."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all subtitle files."""
        subtitle_dir = data_repo.agd_path / "Subtitle" / data_repo.language_short
        if subtitle_dir.exists():
            return [
                f"Subtitle/{data_repo.language_short}/{srt_file.name}"
                for srt_file in subtitle_dir.glob("*.srt")
            ]
        return []

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process subtitle file into rendered content."""
        # Get subtitle info
        subtitle_info = processing.get_subtitle_info(
            renderable_key, data_repo=data_repo
        )

        # Render the subtitle
        return rendering.render_subtitle(subtitle_info, renderable_key)


class Materials(BaseRenderableType):
    """Material content type (item names and descriptions)."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        return [
            str(m["id"]) for m in data_repo.load_material_excel_config_data().get_all()
        ]

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process material into rendered content."""
        material_info = processing.get_material_info(
            renderable_key, data_repo=data_repo
        )

        if _should_skip(material_info.name, data_repo.language):
            return None

        return rendering.render_material(material_info)


class Voicelines(BaseRenderableType):
    """Voiceline content type (character voice lines)."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all avatar IDs that have voicelines."""
        return sorted(
            {
                str(fetter["avatarId"])
                for fetter in data_repo.load_fetters_excel_config_data()
            }
        )

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process voiceline into rendered content."""
        voiceline_info = processing.get_voiceline_info(
            renderable_key, data_repo=data_repo
        )

        # Skip if no voicelines found
        if not voiceline_info.voicelines:
            return None

        return rendering.render_voiceline(voiceline_info)
