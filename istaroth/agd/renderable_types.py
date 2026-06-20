"""Renderable content type classes for different AGD content."""

from abc import ABC, abstractmethod
from collections import Counter
from typing import Callable, ClassVar, Generic, NamedTuple, TypeVar, assert_never

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
        """Find and return list of renderable keys for this renderable type.

        Should be cheap: enumerate keys (e.g. from an index/config) without
        loading or parsing each item. Per-item work — including deciding to skip
        an item — belongs in `process`, which runs across the worker pool.
        """
        pass

    @abstractmethod
    def process(
        self, renderable_key: TKey, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process renderable key into rendered content."""
        pass


def _process_single_readable(
    renderable_key: str,
    data_repo: repo.DataRepo,
    render: Callable[[str, types.ReadableMetadata], types.RenderedItem],
) -> types.RenderedItem | None:
    """Render a single readable file, or skip empty/placeholder ones."""
    if (
        loaded := processing.load_readable(renderable_key, data_repo=data_repo)
    ) is None:
        return None
    return render(*loaded)


class BaseReadables(BaseRenderableType[str]):
    """Base renderable for readable content."""

    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    @abstractmethod
    def _render(
        self, content: str, metadata: types.ReadableMetadata
    ) -> types.RenderedItem:
        """Render readable content into a rendered item."""
        pass

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process readable file into rendered content."""
        return _process_single_readable(renderable_key, data_repo, self._render)


class Readables(BaseReadables):
    """Readable content type (books, weapons, etc.)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_READABLE
    )

    def _render(
        self, content: str, metadata: types.ReadableMetadata
    ) -> types.RenderedItem:
        return rendering.render_readable(content, metadata)

    def __init__(self, used_readable_filenames: set[types.ReadableFilename]) -> None:
        """Initialize with optional set of used readable filenames to exclude."""
        self.used_readable_filenames = used_readable_filenames

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all readable files, excluding those already used."""
        readables_tracker = data_repo.get_readables()
        return [
            f"Readable/{data_repo.language_short}/{filename}"
            for filename in sorted(
                readables_tracker.get_all_ids() - self.used_readable_filenames
            )
        ]


class _BookSeriesKey(NamedTuple):
    """Renderable key for a multi-volume book series, identified by its suit id."""

    suit_id: types.BookSuitId


class _BookStandaloneKey(NamedTuple):
    """Renderable key for a single book not grouped into a series."""

    readable_path: str


_BookKey = _BookSeriesKey | _BookStandaloneKey


class Books(BaseRenderableType[_BookKey]):
    """Book content type.

    Multi-volume series (per BookSuit/BooksCodex) render into a single grouped file
    with a per-volume series annotation; every other ``Book*`` readable renders on
    its own as before. Reading a series volume's content during ``process`` claims
    its file, keeping it out of the standalone catch-all below.
    """

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_BOOK
    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    def discover(self, data_repo: repo.DataRepo) -> list[_BookKey]:
        """Enumerate book series, then standalone book files not in any series."""
        series_mapping = data_repo.build_book_series_mapping()
        grouped_filenames = {
            filename for filenames in series_mapping.values() for filename in filenames
        }
        readables_tracker = data_repo.get_readables()
        return [
            *(_BookSeriesKey(suit_id) for suit_id in sorted(series_mapping)),
            *(
                _BookStandaloneKey(f"Readable/{data_repo.language_short}/{filename}")
                for filename in sorted(
                    filename
                    for filename in readables_tracker.get_all_ids()
                    if filename.startswith("Book") and filename not in grouped_filenames
                )
            ),
        ]

    def process(
        self, renderable_key: _BookKey, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Render a book series into one file, or a standalone book on its own."""
        match renderable_key:
            case _BookSeriesKey(suit_id=suit_id):
                series_info = processing.get_book_series_info(
                    suit_id, data_repo=data_repo
                )
                if series_info is None:
                    return None
                return rendering.render_book_series(series_info, data_repo.language)
            case _BookStandaloneKey(readable_path=readable_path):
                return _process_single_readable(
                    readable_path, data_repo, rendering.render_book
                )
            case _:
                assert_never(renderable_key)


class Weapons(BaseRenderableType[str]):
    """Weapon story content type.

    Discovered from the authoritative WeaponExcelConfigData rather than by globbing
    ``Weapon*`` readable filenames: each weapon's storyId resolves through the
    document and localization configs to its story page files, which are assembled
    into a single document. This treats a multi-page weapon story as one item and
    drops storyId-less placeholder/test weapons for free (issue #71).
    """

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_WEAPON
    )
    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Enumerate all weapon IDs from WeaponExcelConfigData."""
        return sorted(
            str(weapon_id) for weapon_id in data_repo.load_weapon_excel_config_data()
        )

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Assemble and render a weapon's story document, or skip if it has none.

        ``get_weapon_info`` claims the weapon's readable files (base + story pages)
        so its empty/placeholder files stay out of the generic Readables catch-all.
        """
        if (
            weapon_info := processing.get_weapon_info(
                renderable_key, data_repo=data_repo
            )
        ) is None:
            return None
        return rendering.render_weapon(weapon_info)


class Wings(BaseReadables):
    """Wings readable content type."""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_WINGS

    def _render(
        self, content: str, metadata: types.ReadableMetadata
    ) -> types.RenderedItem:
        return rendering.render_wings(content, metadata)

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all readable files whose filename starts with Wings."""
        readables_tracker = data_repo.get_readables()
        return [
            f"Readable/{data_repo.language_short}/{filename}"
            for filename in sorted(
                filename
                for filename in readables_tracker.get_all_ids()
                if filename.startswith("Wings")
            )
        ]


class Costumes(BaseReadables):
    """Costume readable content type."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_COSTUME
    )

    def _render(
        self, content: str, metadata: types.ReadableMetadata
    ) -> types.RenderedItem:
        return rendering.render_costume(content, metadata)

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all readable files whose filename starts with Costume."""
        readables_tracker = data_repo.get_readables()
        return [
            f"Readable/{data_repo.language_short}/{filename}"
            for filename in sorted(
                filename
                for filename in readables_tracker.get_all_ids()
                if filename.startswith("Costume")
            )
        ]


class Quests(BaseRenderableType[types.QuestId]):
    """Quest content type (dialog, cutscenes, etc.)"""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_QUEST
    error_limit: ClassVar[int] = 100
    error_limit_non_chinese: ClassVar[int] = 2000

    def discover(self, data_repo: repo.DataRepo) -> list[types.QuestId]:
        """Find all quest IDs from MainQuestExcelConfigData."""
        # Sort by the string form: quest ids vary in digit width, so this keeps
        # the established (lexicographic) manifest ordering now that ids are int.
        return sorted(data_repo.load_main_quest_excel_config_data(), key=str)

    def process(
        self, renderable_key: types.QuestId, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process quest file into rendered content."""
        # get_quest_info returns None for test/hidden quests, which are excluded.
        if (
            quest_info := processing.get_quest_info(renderable_key, data_repo=data_repo)
        ) is None:
            return None

        if not (
            any(step.talk is not None for step in quest_info.steps)
            or quest_info.non_subquest_talks
        ):
            # Skip quests with no dialogue (objective-only steps don't qualify).
            return None

        # Render the quest
        return rendering.render_quest(quest_info, language=data_repo.language)


class CharacterStories(BaseRenderableType[types.AvatarId]):
    """Character story content type."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_CHARACTER_STORY
    )

    def discover(self, data_repo: repo.DataRepo) -> list[types.AvatarId]:
        """Find all unique character IDs that have stories."""
        fetter_data = data_repo.load_fetter_story_excel_config_data()

        # Collect unique avatar IDs that have stories
        avatar_ids = set()
        for story in fetter_data:
            avatar_id = story.get("avatarId")
            if avatar_id:
                avatar_ids.add(avatar_id)

        return sorted(avatar_ids)

    def process(
        self, renderable_key: types.AvatarId, data_repo: repo.DataRepo
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

            material_id = material["id"]
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


class Achievements(BaseRenderableType[types.AchievementGoalId]):
    """Achievements grouped by their in-game section."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_ACHIEVEMENT
    )

    def discover(self, data_repo: repo.DataRepo) -> list[types.AchievementGoalId]:
        """Discover achievement sections in their configured display order."""
        return [
            section["id"]
            for section in sorted(
                (
                    section
                    for section, _ in data_repo.build_achievement_section_mapping().values()
                ),
                key=lambda section: (section["orderId"], section["id"]),
            )
        ]

    def process(
        self, renderable_key: types.AchievementGoalId, data_repo: repo.DataRepo
    ) -> types.RenderedItem:
        """Process one achievement section into rendered content."""
        return rendering.render_achievement_section(
            processing.get_achievement_section_info(renderable_key, data_repo=data_repo)
        )


class Voicelines(BaseRenderableType[types.AvatarId]):
    """Voiceline content type (character voice lines)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_VOICELINE
    )

    def discover(self, data_repo: repo.DataRepo) -> list[types.AvatarId]:
        """Find all avatar IDs that have voicelines."""
        return sorted(
            {
                fetter["avatarId"]
                for fetter in data_repo.load_fetters_excel_config_data()
            }
        )

    def process(
        self, renderable_key: types.AvatarId, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process voiceline into rendered content."""
        voiceline_info = processing.get_voiceline_info(
            renderable_key, data_repo=data_repo
        )

        # Skip if no voicelines found
        if not voiceline_info.voicelines:
            return None

        return rendering.render_voiceline(voiceline_info)


class ArtifactSets(BaseRenderableType[types.ArtifactSetId]):
    """Artifact set content type (artifact sets with individual piece stories)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_ARTIFACT_SET
    )

    def discover(self, data_repo: repo.DataRepo) -> list[types.ArtifactSetId]:
        """Find all artifact set IDs from ReliquarySetExcelConfigData."""
        # Load artifact set configuration data
        set_data = data_repo.load_reliquary_set_excel_config_data()

        return [set_entry["setId"] for set_entry in set_data]

    def process(
        self, renderable_key: types.ArtifactSetId, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process artifact set into rendered content."""
        # Skip sets with no story content (returns None)
        if (
            artifact_set_info := processing.get_artifact_set_info(
                renderable_key, data_repo=data_repo
            )
        ) is None:
            return None

        # Render the artifact set
        return rendering.render_artifact_set(artifact_set_info)


class Creatures(BaseRenderableType[str]):
    """Living-beings archive content type, one file per codex subType group."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_CREATURE
    )
    error_limit: ClassVar[int] = 0
    error_limit_non_chinese: ClassVar[int] = 2

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """All codex subType groups that have at least one non-disused entry."""
        return sorted(
            {
                entry["subType"]
                for entry in data_repo.load_animal_codex_excel_config_data().values()
                if not entry["isDisuse"]
            }
        )

    def process(
        self, renderable_key: str, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process a codex subType group into a single rendered file."""
        return rendering.render_creature_group(
            processing.get_creature_group_info(renderable_key, data_repo=data_repo)
        )


class TalkGroups(
    BaseRenderableType[tuple[talk_parsing.TalkGroupType, talk_parsing.TalkGroupId]]
):
    """Talk activity groups content type (talks grouped by activity)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_TALK_GROUP
    )
    error_limit: ClassVar[int] = 120
    error_limit_non_chinese: ClassVar[int] = 120

    def discover(
        self, data_repo: repo.DataRepo
    ) -> list[tuple[talk_parsing.TalkGroupType, talk_parsing.TalkGroupId]]:
        """Find all ActivityGroup JSON files and return activity IDs."""
        return sorted(data_repo.build_talk_group_mapping())

    def process(
        self,
        renderable_key: tuple[talk_parsing.TalkGroupType, talk_parsing.TalkGroupId],
        data_repo: repo.DataRepo,
    ) -> types.RenderedItem | None:
        """Process talk activity group into rendered content."""
        talk_group_info = processing.get_talk_group_info(
            renderable_key[0], renderable_key[1], data_repo=data_repo
        )

        # Skip if no talks found for this activity group
        if not talk_group_info.talks:
            return None

        # An NpcGroup's id is itself an NPC id, so resolve it to a readable name.
        group_name: str | None = None
        if renderable_key[0] == "NpcGroup":
            npc_id = renderable_key[1]
            # Dev/test markers live only in CHS, so always decide skip from the
            # source name to keep CHS/ENG corpora consistent.
            source_name = data_repo.get_npc_id_to_source_name_mapping().get(npc_id)
            if source_name is not None:
                if text_utils.should_skip_text(source_name, localization.Language.CHS):
                    return None
                # The id resolves to a real (non-test) NPC in CHS, so it must
                # resolve in the output language too — index strictly.
                group_name = data_repo.get_npc_id_to_name_mapping()[npc_id]

        return rendering.render_talk_group(
            renderable_key[0],
            renderable_key[1],
            talk_group_info,
            data_repo.language,
            group_name=group_name,
        )


class Hangouts(BaseRenderableType[types.QuestId]):
    """Hangout (Coop) content type: one file per hangout quest, in play order."""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_COOP
    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    def discover(self, data_repo: repo.DataRepo) -> list[types.QuestId]:
        """All hangout quest ids that have Coop talk files."""
        return sorted(data_repo.build_hangout_quest_to_stories())

    def process(
        self, renderable_key: types.QuestId, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Render a hangout quest's Coop dialogue, or skip if it has no content."""
        if (
            hangout_info := processing.get_hangout_info(
                renderable_key, data_repo=data_repo
            )
        ) is None:
            return None
        return rendering.render_hangout(hangout_info, language=data_repo.language)


class Talks(BaseRenderableType[types.TalkId]):
    """Standalone talk content type for talks not used by other renderable types."""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_TALK
    error_limit: ClassVar[int] = 1000
    error_limit_non_chinese: ClassVar[int] = 1000

    def __init__(self, used_talk_ids: set[types.TalkId]) -> None:
        """Initialize with set of already used talk IDs."""
        self.used_talk_ids = used_talk_ids

    def discover(self, data_repo: repo.DataRepo) -> list[types.TalkId]:
        """Find all talk IDs that are not already used."""
        talk_tracker = data_repo.build_talk_tracker()

        # Get all talk IDs from configuration
        all_talk_ids = set(talk_tracker._talk_dict.keys())

        # Find unused talk IDs
        unused_talk_ids = all_talk_ids - self.used_talk_ids

        return sorted(unused_talk_ids)

    def process(
        self, renderable_key: types.TalkId, data_repo: repo.DataRepo
    ) -> types.RenderedItem | None:
        """Process talk into rendered content."""
        # Check if talk file exists in mapping first
        talk_tracker = data_repo.build_talk_tracker()
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
