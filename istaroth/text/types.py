"""Generic text types."""

from __future__ import annotations

from enum import Enum
from typing import Any

import attrs


class TextCategory(Enum):
    """Enum for text categories.

    When adding a new value, also add a display name in the frontend i18n files:
    frontend/src/i18n/chs.ts and frontend/src/i18n/eng.ts (library.categories).
    """

    AGD_READABLE = "agd_readable"
    AGD_BOOK = "agd_book"
    AGD_WEAPON = "agd_weapon"
    AGD_WINGS = "agd_wings"
    AGD_COSTUME = "agd_costume"
    AGD_QUEST = "agd_quest"
    AGD_CHARACTER_STORY = "agd_character_story"
    AGD_SUBTITLE = "agd_subtitle"
    AGD_MATERIAL_TYPE = "agd_material_type"
    AGD_VOICELINE = "agd_voiceline"
    AGD_TALK_GROUP = "agd_talk_group"
    AGD_TALK = "agd_talk"
    AGD_ARTIFACT_SET = "agd_artifact_set"

    TPS_SHISHU = "tps_shishu"

    def get_note(self) -> str | None:
        """Return an optional caveat note for this category."""
        return {
            TextCategory.TPS_SHISHU: "以下内容来自第三方非官方资料（诗漱原神世界观手册），并非游戏内官方文本。在引用这些内容时，你必须在回答中明确告知用户该信息来源于非官方资料，仅供参考",
        }.get(self)


def _validate_relative_path(
    instance: TextMetadata, attribute: attrs.Attribute, value: str
) -> None:
    """Validate that relative_path starts with the expected category prefix."""
    expected_prefix = f"{instance.category.value}/"
    if not value.startswith(expected_prefix):
        raise ValueError(
            f"relative_path '{value}' must start with '{expected_prefix}' "
            f"for category {instance.category.name}"
        )


@attrs.define
class TextMetadata:
    """Metadata for a text file."""

    category: TextCategory
    title: str
    id: int
    relative_path: str = attrs.field(validator=_validate_relative_path)

    def to_dict(self) -> dict[str, str | int]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category.value,
            "title": self.title,
            "id": self.id,
            "relative_path": self.relative_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextMetadata:
        """Create TextMetadata from dictionary."""
        category_enum = TextCategory(data["category"])
        id_value = data["id"]
        # Convert id to int if it's a string
        if isinstance(id_value, str):
            id_int = int(id_value)
        else:
            id_int = id_value
        return cls(
            category=category_enum,
            title=str(data["title"]),
            id=id_int,
            relative_path=str(data["relative_path"]),
        )
