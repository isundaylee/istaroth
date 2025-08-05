"""Renderable content type classes for different AGD content."""

from abc import ABC, abstractmethod
from typing import ClassVar

from istaroth import text_cleanup
from istaroth.agd import localization, processing, rendering, repo, text_utils, types


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

    def __init__(self, used_readable_ids: set[str]) -> None:
        """Initialize with optional set of used readable IDs to exclude."""
        self.used_readable_ids = used_readable_ids

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all readable files, excluding those already used."""
        readables_tracker = data_repo.get_readables()
        return [
            f"Readable/{data_repo.language_short}/{filename}"
            for filename in readables_tracker.get_all_ids() - self.used_readable_ids
        ]

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process readable file into rendered content."""
        # Get readable metadata
        metadata = processing.get_readable_metadata(renderable_key, data_repo=data_repo)

        # Skip if title starts with "test" (case-insensitive) and language is CHS
        if text_utils.should_skip_text(metadata.title, data_repo.language):
            return None

        # Read the actual readable content
        readable_file_path = data_repo.agd_path / renderable_key
        with open(readable_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Clean text markers in readable content
        content = text_cleanup.clean_text_markers(content, data_repo.language)

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
        if text_utils.should_skip_text(quest_info.title, data_repo.language):
            return None

        if not (quest_info.talks or quest_info.non_subquest_talks):
            # If no talks, skip rendering
            return None

        # Render the quest
        return rendering.render_quest(quest_info, language=data_repo.language)


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

        if text_utils.should_skip_text(material_info.name, data_repo.language):
            return None

        return rendering.render_material(material_info, material_id=renderable_key)


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


class ArtifactSets(BaseRenderableType):
    """Artifact set content type (artifact sets with individual piece stories)."""

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all artifact set IDs from ReliquarySetExcelConfigData."""
        # Load artifact set configuration data
        set_data = data_repo.load_reliquary_set_excel_config_data()

        # Return all set IDs as strings for processing
        return [str(set_entry["setId"]) for set_entry in set_data]

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process artifact set into rendered content."""
        # Get artifact set info
        artifact_set_info = processing.get_artifact_set_info(
            renderable_key, data_repo=data_repo
        )

        # Skip if no artifacts in set
        if not artifact_set_info.artifacts:
            return None

        # Render the artifact set
        return rendering.render_artifact_set(artifact_set_info)


class Talks(BaseRenderableType):
    """Standalone talk content type for talks not used by other renderable types."""

    error_limit: ClassVar[int] = 500
    error_limit_non_chinese: ClassVar[int] = 500

    def __init__(self, used_talk_ids: set[str]) -> None:
        """Initialize with set of already used talk IDs."""
        self.used_talk_ids = used_talk_ids

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all talk IDs that are not already used."""
        talk_tracker = data_repo.load_talk_excel_config_data()

        # Get all talk IDs from configuration
        all_talk_ids = set(talk_tracker._talk_dict.keys())

        # Find unused talk IDs
        unused_talk_ids = all_talk_ids - self.used_talk_ids

        return sorted(unused_talk_ids)

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process talk into rendered content."""
        # Check if talk file exists in mapping first
        talk_tracker = data_repo.load_talk_excel_config_data()
        talk_file_path = talk_tracker.get_talk_file_path(renderable_key)

        # Skip if no file found in mapping
        if talk_file_path is None:
            return None

        # Get talk info by ID
        talk_info = processing.get_talk_info_by_id(renderable_key, data_repo=data_repo)

        # Skip if no dialog content
        if not talk_info.text:
            return None

        # Render the talk
        return rendering.render_talk(
            talk_info, talk_id=renderable_key, language=data_repo.language
        )
