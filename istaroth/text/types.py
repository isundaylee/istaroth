"""Generic text types."""

from enum import Enum

import attrs


class TextCategory(Enum):
    """Enum for text categories, separate from AGD RenderableType."""

    AGD_READABLE = "agd_readable"
    AGD_QUEST = "agd_quest"
    AGD_CHARACTER_STORY = "agd_character_story"
    AGD_SUBTITLE = "agd_subtitle"
    AGD_MATERIAL_TYPE = "agd_material_type"
    AGD_VOICELINE = "agd_voiceline"
    AGD_TALK_GROUP = "agd_talk_group"
    AGD_TALK = "agd_talk"
    AGD_ARTIFACT_SET = "agd_artifact_set"


@attrs.define
class TextMetadata:
    """Metadata for a text file."""

    category: TextCategory
    title: str
    id: str
    relative_path: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category.value,
            "title": self.title,
            "id": self.id,
            "relative_path": self.relative_path,
        }
