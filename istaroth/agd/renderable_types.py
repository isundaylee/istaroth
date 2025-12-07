"""Renderable content type classes for different AGD content."""

from abc import ABC, abstractmethod
from collections import Counter
from typing import ClassVar, Generic, TypeVar

from istaroth import text_cleanup
from istaroth.agd import (
    localization,
    processing,
    rendering,
    repo,
    talk_parsing,
    text_utils,
    types,
)
from istaroth.text import types as text_types

# Generic type variable for renderable keys
TKey = TypeVar("TKey")


class BaseRenderableType(ABC, Generic[TKey]):
    """Abstract base class for renderable content types."""

    text_category: ClassVar[text_types.TextCategory]
    error_limit: ClassVar[int] = 0  # Default error limit
    error_limit_non_chinese: ClassVar[int] = 0  # Higher limit for non-Chinese languages

    @abstractmethod
    def discover(self, data_repo: repo.DataRepo) -> list[TKey]:
        """Find and return list of renderable keys for this renderable type."""
        pass

    @abstractmethod
    def process(
        self, renderable_key: TKey, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process renderable key into rendered content."""
        pass


class Readables(BaseRenderableType[str]):
    """Readable content type (books, weapons, etc.)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_READABLE
    )
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
            for filename in sorted(
                readables_tracker.get_all_ids() - self.used_readable_ids
            )
        ]

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process readable file into rendered content."""
        # Read the actual readable content
        readable_file_path = data_repo.agd_path / renderable_key
        with open(readable_file_path, "r", encoding="utf-8") as f:
            content = text_cleanup.clean_text_markers(f.read(), data_repo.language)

        if text_utils.should_skip_text(content, data_repo.language):
            return None

        # Get readable metadata
        metadata = processing.get_readable_metadata(renderable_key, data_repo=data_repo)

        # Skip if title starts with "test" (case-insensitive) and language is CHS
        if text_utils.should_skip_text(metadata.title, data_repo.language):
            return None

        # Render the content
        return rendering.render_readable(content, metadata)


class Quests(BaseRenderableType[str]):
    """Quest content type (dialog, cutscenes, etc.)"""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_QUEST
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
        # Get quest info using quest ID directly
        quest_info = processing.get_quest_info(renderable_key, data_repo=data_repo)

        # Skip if title starts with "test" (case-insensitive) and language is CHS
        if text_utils.should_skip_text(quest_info.title, data_repo.language):
            return None

        if not (quest_info.talks or quest_info.non_subquest_talks):
            # If no talks, skip rendering
            return None

        # Render the quest
        return rendering.render_quest(quest_info, language=data_repo.language)


class CharacterStories(BaseRenderableType[str]):
    """Character story content type."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_CHARACTER_STORY
    )

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


class Subtitles(BaseRenderableType[str]):
    """Subtitle content type (.srt files)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_SUBTITLE
    )

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


class MaterialTypes(BaseRenderableType[str]):
    """Material types content type (materials grouped by type)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_MATERIAL_TYPE
    )

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Discover all unique material types."""
        materials_data = data_repo.load_material_excel_config_data().get_all()
        return sorted(
            Counter(material["materialType"] for material in materials_data).keys()
        )

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process all materials of a given type into rendered content."""
        # Load all materials and filter by the given material type
        materials_data = data_repo.load_material_excel_config_data().get_all()
        materials_of_type = []

        for material in materials_data:
            if material["materialType"] != renderable_key:
                continue

            material_id = str(material["id"])
            material_info = processing.get_material_info(
                material_id, data_repo=data_repo
            )

            # Skip materials with test names or descriptions
            if text_utils.should_skip_text(
                material_info.name, data_repo.language
            ) or text_utils.should_skip_text(
                material_info.description, data_repo.language
            ):
                continue

            materials_of_type.append(material_info)

        # Skip if no materials found for this type
        if not materials_of_type:
            return None

        return rendering.render_materials_by_type(renderable_key, materials_of_type)


class Voicelines(BaseRenderableType[str]):
    """Voiceline content type (character voice lines)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_VOICELINE
    )

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


class ArtifactSets(BaseRenderableType[str]):
    """Artifact set content type (artifact sets with individual piece stories)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_ARTIFACT_SET
    )

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


class TalkGroups(BaseRenderableType[tuple[talk_parsing.TalkGroupType, str]]):
    """Talk activity groups content type (talks grouped by activity)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_TALK_GROUP
    )
    error_limit: ClassVar[int] = 120
    error_limit_non_chinese: ClassVar[int] = 120

    def discover(
        self, data_repo: repo.DataRepo
    ) -> list[tuple[talk_parsing.TalkGroupType, str]]:
        """Find all ActivityGroup JSON files and return activity IDs."""
        return sorted(data_repo.build_talk_group_mapping())

    def process(
        self,
        renderable_key: tuple[talk_parsing.TalkGroupType, str],
        data_repo: repo.DataRepo,
    ) -> types.RenderedItem | None:
        """Process talk activity group into rendered content."""
        talk_group_info = processing.get_talk_group_info(
            renderable_key[0], renderable_key[1], data_repo=data_repo
        )

        # Skip if no talks found for this activity group
        if not talk_group_info.talks:
            return None

        return rendering.render_talk_group(
            renderable_key[0], renderable_key[1], talk_group_info, data_repo.language
        )


class Talks(BaseRenderableType[str]):
    """Standalone talk content type for talks not used by other renderable types."""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_TALK
    error_limit: ClassVar[int] = 1000
    error_limit_non_chinese: ClassVar[int] = 1000

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
            talk_info,
            talk_id=renderable_key,
            language=data_repo.language,
            talk_file_path=talk_file_path,
        )
