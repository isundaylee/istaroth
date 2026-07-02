"""Achievement processing and rendering."""

from istaroth import utils
from istaroth.agd import (
    id_types,
    issues,
    processed_types,
    repo,
)
from istaroth.text import types as text_types


def get_achievement_section_info(
    section_id: id_types.AchievementGoalId, *, data_repo: repo.DataRepo
) -> processed_types.AchievementSectionInfo:
    """Get one localized achievement section and its active achievements."""
    if (
        section_config := data_repo.build_achievement_section_mapping().get(section_id)
    ) is None:
        raise ValueError(f"Achievement section not found for ID {section_id}")
    section, achievement_configs = section_config

    text_map = data_repo.build_text_map_tracker()
    if (section_name := text_map.get_optional(section["nameTextMapHash"])) is None:
        raise ValueError(f"Missing name for achievement section {section_id}")

    achievements = list[processed_types.AchievementInfo]()
    for achievement in achievement_configs:
        if (name := text_map.get_optional(achievement["titleTextMapHash"])) is None:
            raise ValueError(f"Missing name for achievement {achievement['id']}")
        if (
            description := text_map.get_optional(achievement["descTextMapHash"])
        ) is None:
            raise ValueError(f"Missing description for achievement {achievement['id']}")
        achievements.append(
            processed_types.AchievementInfo(
                achievement_id=achievement["id"],
                name=name,
                description=description,
            )
        )

    return processed_types.AchievementSectionInfo(
        section_id=section_id,
        section_name=section_name,
        achievements=achievements,
    )


def render_achievement_section(
    section_info: processed_types.AchievementSectionInfo,
) -> processed_types.RenderedItem:
    """Render one achievement section into a single text file."""
    filename = (
        f"{section_info.section_id}_"
        f"{utils.make_safe_filename_part(section_info.section_name)}.txt"
    )
    content_lines = [f"# {section_info.section_name}", ""]
    for achievement in section_info.achievements:
        content_lines.extend(
            [f"## {achievement.name}", "", achievement.description, ""]
        )

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ACHIEVEMENT,
            title=section_info.section_name,
            id=section_info.section_id,
            relative_path=(
                f"{text_types.TextCategory.AGD_ACHIEVEMENT.value}/{filename}"
            ),
        ),
        content="\n".join(content_lines).rstrip(),
    )
