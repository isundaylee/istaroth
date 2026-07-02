"""Character story and voiceline processing and rendering."""

from istaroth import utils
from istaroth.agd import (
    agd_types,
    id_types,
    issues,
    localization,
    processed_types,
    repo,
)
from istaroth.text import types as text_types

_ELEMENT_NAMES: dict[str, dict[localization.Language, str]] = {
    "Fire": {localization.Language.CHS: "火", localization.Language.ENG: "Pyro"},
    "Water": {localization.Language.CHS: "水", localization.Language.ENG: "Hydro"},
    "Wind": {localization.Language.CHS: "风", localization.Language.ENG: "Anemo"},
    "Rock": {localization.Language.CHS: "岩", localization.Language.ENG: "Geo"},
    "Electric": {localization.Language.CHS: "雷", localization.Language.ENG: "Electro"},
    "Grass": {localization.Language.CHS: "草", localization.Language.ENG: "Dendro"},
    "Ice": {localization.Language.CHS: "冰", localization.Language.ENG: "Cryo"},
}


def _resolve_constellations(
    depot: agd_types.AvatarSkillDepotExcelConfigDataItem,
    element: str | None,
    *,
    data_repo: repo.DataRepo,
) -> list[processed_types.Constellation]:
    """Resolve the 6 constellations for a single skill depot, in talents-array order.

    Strict: every depot that owns constellations must have exactly 6 talents that
    all resolve to a name and description, else raise.
    """
    text_map = data_repo.build_text_map_tracker()
    talent_map = data_repo.load_avatar_talent_excel_config_data()

    talent_ids = [talent_id for talent_id in depot["talents"] if talent_id]
    if len(talent_ids) != 6:
        raise ValueError(
            f"Expected 6 constellation talents in depot {depot['id']}, "
            f"got {len(talent_ids)}: {depot['talents']}"
        )

    constellations = []
    for talent_id in talent_ids:
        if (talent := talent_map.get(talent_id)) is None:
            raise ValueError(f"Unknown talent {talent_id} in depot {depot['id']}")
        if (name := text_map.get_optional(talent["nameTextMapHash"])) is None:
            raise ValueError(f"Missing constellation name for talent {talent_id}")
        if (description := text_map.get_optional(talent["descTextMapHash"])) is None:
            raise ValueError(
                f"Missing constellation description for talent {talent_id}"
            )
        constellations.append(
            processed_types.Constellation(
                name=name, description=description, element=element
            )
        )
    return constellations


def _get_constellations(
    avatar: agd_types.AvatarExcelConfigDataItem, *, data_repo: repo.DataRepo
) -> list[processed_types.Constellation]:
    """Resolve a character's constellations.

    Regular characters carry all six constellations on their primary
    ``skillDepotId`` and render without an element. Only the Travelers populate
    ``candSkillDepotIds``; their per-element sets live there (skipping empty
    placeholder depots) and are tagged with each depot's element.
    """
    depot_map = data_repo.load_avatar_skill_depot_excel_config_data()
    skill_map = data_repo.load_avatar_skill_excel_config_data()

    per_element = bool(avatar["candSkillDepotIds"])
    depot_ids = avatar["candSkillDepotIds"] or [avatar["skillDepotId"]]

    constellations = []
    for depot_id in depot_ids:
        depot = depot_map[depot_id]
        if not any(depot["talents"]):
            continue
        element = None
        if per_element:
            if (skill := skill_map.get(depot["energySkill"])) is None:
                raise ValueError(
                    f"Unknown energy skill {depot['energySkill']} for {depot_id}"
                )
            element = _ELEMENT_NAMES[skill["costElemType"]][data_repo.language]
        constellations.extend(
            _resolve_constellations(depot, element, data_repo=data_repo)
        )
    return constellations


def get_character_story_info(
    avatar_id: id_types.AvatarId, *, data_repo: repo.DataRepo
) -> processed_types.CharacterStoryInfo:
    """Get all character story information for a specific character."""
    text_map = data_repo.build_text_map_tracker()
    avatar_data = data_repo.load_avatar_excel_config_data()
    fetter_data = data_repo.load_fetter_story_excel_config_data()

    matched_avatar = next(
        (avatar for avatar in avatar_data if avatar["id"] == avatar_id), None
    )
    if (
        matched_avatar is None
        or (character_name := text_map.get_optional(matched_avatar["nameTextMapHash"]))
        is None
    ):
        raise ValueError(f"Unknown character for avatar ID {avatar_id}")

    constellations = _get_constellations(matched_avatar, data_repo=data_repo)

    stories = []
    for story in fetter_data:
        if story["avatarId"] == avatar_id:
            title_hash = story.get("storyTitleTextMapHash")
            if (
                title := text_map.get_optional(title_hash) if title_hash else None
            ) is None:
                raise ValueError(
                    f"Missing story title {title_hash} for avatar ID {avatar_id}"
                )
            context_hash = story.get("storyContextTextMapHash")
            if (
                content := (
                    text_map.get_optional(context_hash) if context_hash else None
                )
            ) is None:
                issues.record(issues.IssueType.MISSING_STORY_CONTENT, str(context_hash))
                content = "Story content not found"
            stories.append(processed_types.CharacterStory(title=title, content=content))

    return processed_types.CharacterStoryInfo(
        character_name=character_name,
        stories=stories,
        avatar_id=avatar_id,
        constellations=constellations,
    )


def render_character_story(
    story_info: processed_types.CharacterStoryInfo,
) -> processed_types.RenderedItem:
    """Render all character stories into RAG-suitable format."""
    # Generate filename based on character name with collision safeguards
    safe_name = utils.make_safe_filename_part(story_info.character_name)
    filename = f"{story_info.avatar_id}_{safe_name}.txt"

    # Format content with character name header and all stories
    story_count = len(story_info.stories)
    content_lines = [f"# {story_info.character_name} - Character Stories\n"]
    content_lines.append(f"*{story_count} stories for this character*\n")

    for i, story in enumerate(story_info.stories, 1):
        content_lines.append(f"## {i}. {story.title}\n")
        content_lines.append(story.content)
        content_lines.append("")

    # Constellations as a flat list. No Cn prefix: the source data does not give a
    # reliable constellation index (the talents array order and openConfig disagree),
    # so we list them in talents-array order without asserting a number. The
    # Travelers' per-element sets are grouped under ### element subsections.
    if story_info.constellations:
        content_lines.append("## Constellations\n")
        current_element: object = object()
        first_group = True
        for constellation in story_info.constellations:
            if constellation.element != current_element:
                current_element = constellation.element
                if constellation.element is not None:
                    if not first_group:
                        content_lines.append("")
                    content_lines.append(f"### {constellation.element}\n")
                first_group = False
            description = " ".join(constellation.description.split())
            content_lines.append(f"{constellation.name}: {description}")
        content_lines.append("")

    rendered_content = "\n".join(content_lines)

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_CHARACTER_STORY,
            title=story_info.character_name,
            id=story_info.avatar_id,
            relative_path=f"{text_types.TextCategory.AGD_CHARACTER_STORY.value}/{filename}",
        ),
        content=rendered_content,
    )


def get_voiceline_info(
    avatar_id: id_types.AvatarId, *, data_repo: repo.DataRepo
) -> processed_types.VoicelineInfo:
    """Get all voiceline information for a specific character."""
    text_map = data_repo.build_text_map_tracker()
    avatar_data = data_repo.load_avatar_excel_config_data()
    fetters_data = data_repo.load_fetters_excel_config_data()

    character_name = None
    for avatar in avatar_data:
        if avatar["id"] == avatar_id:
            character_name = text_map.get_optional(avatar["nameTextMapHash"])
            break
    if character_name is None:
        raise ValueError(f"Unknown character for avatar ID {avatar_id}")

    voicelines = {}
    for fetter in fetters_data:
        if fetter["avatarId"] == avatar_id:
            title_hash = fetter["voiceTitleTextMapHash"]
            if (title := text_map.get_optional(title_hash)) is None:
                raise ValueError(
                    f"Missing voiceline title {title_hash} for avatar ID {avatar_id}"
                )
            content = text_map.get(fetter["voiceFileTextTextMapHash"], "")
            if content:
                voicelines[title] = content

    return processed_types.VoicelineInfo(
        character_name=character_name, voicelines=voicelines, avatar_id=avatar_id
    )


def render_voiceline(
    voiceline_info: processed_types.VoicelineInfo,
) -> processed_types.RenderedItem:
    """Render voiceline content into RAG-suitable format."""
    safe_name = utils.make_safe_filename_part(voiceline_info.character_name)
    filename = f"{voiceline_info.avatar_id}_{safe_name}.txt"

    content_lines = [f"# {voiceline_info.character_name} Voicelines\n"]

    for title, content in voiceline_info.voicelines.items():
        content_lines.append(f"## {title}")
        content_lines.append(content)
        content_lines.append("")

    rendered_content = "\n".join(content_lines).rstrip()

    return processed_types.RenderedItem(
        text_metadata=text_types.TextMetadata(
            category=text_types.TextCategory.AGD_VOICELINE,
            title=voiceline_info.character_name,
            id=voiceline_info.avatar_id,
            relative_path=f"{text_types.TextCategory.AGD_VOICELINE.value}/{filename}",
        ),
        content=rendered_content,
    )
