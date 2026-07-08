"""Achievement processing and rendering."""

from istaroth import utils
from istaroth.agd import (
    first_seen,
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
    section_name = text_map.get_required(section["nameTextMapHash"])

    achievements = [
        processed_types.AchievementInfo(
            achievement_id=achievement["id"],
            name=text_map.get_required(achievement["titleTextMapHash"]),
            description=text_map.get_required(achievement["descTextMapHash"]),
        )
        for achievement in achievement_configs
    ]

    return processed_types.AchievementSectionInfo(
        section_id=section_id,
        section_name=section_name,
        achievements=achievements,
    )


def render_achievement_section(
    section_info: processed_types.AchievementSectionInfo,
    *,
    first_seen_index: first_seen.FirstSeenIndex,
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

    min_version, max_version = first_seen_index.resolve(
        [
            first_seen.SourceId(
                first_seen.SourceDomain.ACHIEVEMENT, achievement.achievement_id
            )
            for achievement in section_info.achievements
        ]
    )
    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_ACHIEVEMENT,
            title=section_info.section_name,
            id=section_info.section_id,
            relative_path=(
                f"{text_types.TextCategory.AGD_ACHIEVEMENT.value}/{filename}"
            ),
            min_version=min_version,
            max_version=max_version,
        ),
        content="\n".join(content_lines).rstrip(),
    )
