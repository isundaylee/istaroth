"""Renderable content type classes for different AGD content."""

from abc import ABC, abstractmethod
from collections import Counter
from typing import Callable, ClassVar, Generic, NamedTuple, TypeVar, assert_never

from istaroth.agd import (
    first_seen,
    id_types,
    localization,
    processed_types,
    repo,
    talk_parsing,
    text_utils,
    tracking,
)
from istaroth.agd.renderables import (
    _talk,
    achievement,
    anecdote,
    artifact,
    book,
    character,
    creature,
    hangout,
    material,
    quest,
    readable,
    subtitle,
    talk_group,
    weapon,
)
from istaroth.text import types as text_types

# Generic type variable for renderable keys
TKey = TypeVar("TKey")


class BaseRenderableType(ABC, Generic[TKey]):
    """Abstract base class for renderable content types."""

    text_category: ClassVar[text_types.TextCategory]
    error_limit: ClassVar[int] = 0  # Default error limit
    error_limit_non_chinese: ClassVar[int] = 0  # Higher limit for non-Chinese languages

    @classmethod
    def error_limit_for(cls, language: localization.Language) -> int:
        """Error limit for the run's language (higher for non-Chinese languages)."""
        return (
            cls.error_limit
            if language is localization.Language.CHS
            else cls.error_limit_non_chinese
        )

    @classmethod
    def create_for_generation(
        cls, accessed_stats: tracking.TrackerStats
    ) -> "BaseRenderableType":
        """Build an instance for one full generate-all pass.

        ``accessed_stats`` carries the ids earlier passes already claimed; only
        the trailing Readables/Talks passes use it (to skip those ids), so the
        default ignores it.
        """
        return cls()

    @abstractmethod
    def discover(self, data_repo: repo.DataRepo) -> list[TKey]:
        """Find and return list of renderable keys for this renderable type."""
        pass

    @abstractmethod
    def process(
        self,
        renderable_key: TKey,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process renderable key into rendered content."""
        pass


def _process_single_readable(
    renderable_key: id_types.ReadableFilename,
    data_repo: repo.DataRepo,
    render: Callable[
        [
            str,
            processed_types.ReadableMetadata,
            id_types.ReadableFilename,
            first_seen.FirstSeenIndex,
        ],
        processed_types.RenderedItem,
    ],
    *,
    first_seen_index: first_seen.FirstSeenIndex,
) -> processed_types.RenderedItem | None:
    """Render a single readable file, or skip empty/placeholder ones."""
    if (loaded := readable.load_readable(renderable_key, data_repo=data_repo)) is None:
        return None
    return render(*loaded, renderable_key, first_seen_index)


def _discover_prefixed_readables(
    data_repo: repo.DataRepo,
    prefix: str,
    *,
    excluded: frozenset[id_types.ReadableFilename] = frozenset(),
) -> list[id_types.ReadableFilename]:
    """Readable filenames starting with ``prefix``, minus ``excluded``."""
    readables_tracker = data_repo.build_readables_tracker()
    return sorted(
        filename
        for filename in readables_tracker.get_all_ids()
        if filename.startswith(prefix) and filename not in excluded
    )


class BaseReadables(BaseRenderableType[id_types.ReadableFilename]):
    """Base renderable for readable content (readables/wings/costumes).

    Rendering is identical across subclasses apart from the ``text_category``, so
    the shared ``_render`` dispatches on it; subclasses only supply ``discover``.
    """

    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    def _render(
        self,
        content: str,
        metadata: processed_types.ReadableMetadata,
        readable_filename: id_types.ReadableFilename,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem:
        """Render readable content into a rendered item."""
        return readable.render_readable_like(
            content,
            metadata,
            readable_filename,
            category=self.text_category,
            first_seen_index=first_seen_index,
        )

    def process(
        self,
        renderable_key: id_types.ReadableFilename,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process readable file into rendered content."""
        return _process_single_readable(
            renderable_key, data_repo, self._render, first_seen_index=first_seen_index
        )


class Readables(BaseReadables):
    """Readable content type (books, weapons, etc.)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_READABLE
    )

    def __init__(self, used_readable_filenames: set[id_types.ReadableFilename]) -> None:
        """Initialize with optional set of used readable filenames to exclude."""
        self.used_readable_filenames = used_readable_filenames

    @classmethod
    def create_for_generation(
        cls, accessed_stats: tracking.TrackerStats
    ) -> "Readables":
        return cls(accessed_stats.accessed[tracking.TrackerKind.READABLES].copy())

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.ReadableFilename]:
        """Find all readable files, excluding those already used."""
        readables_tracker = data_repo.build_readables_tracker()
        return sorted(readables_tracker.get_all_ids() - self.used_readable_filenames)


class _BookSeriesKey(NamedTuple):
    """Renderable key for a multi-volume book series, identified by its suit id."""

    suit_id: id_types.BookSuitId


class _BookStandaloneKey(NamedTuple):
    """Renderable key for a single book not grouped into a series."""

    filename: id_types.ReadableFilename


_BookKey = _BookSeriesKey | _BookStandaloneKey


class Books(BaseRenderableType[_BookKey]):
    """Book content type."""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_BOOK
    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    def discover(self, data_repo: repo.DataRepo) -> list[_BookKey]:
        """Enumerate book series, then standalone book files not in any series."""
        series_mapping = data_repo.build_book_series_mapping()
        grouped_filenames = frozenset(
            filename for filenames in series_mapping.values() for filename in filenames
        )
        return [
            *(_BookSeriesKey(suit_id) for suit_id in sorted(series_mapping)),
            *(
                _BookStandaloneKey(filename)
                for filename in _discover_prefixed_readables(
                    data_repo, "Book", excluded=grouped_filenames
                )
            ),
        ]

    def process(
        self,
        renderable_key: _BookKey,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Render a book series into one file, or a standalone book on its own."""
        match renderable_key:
            case _BookSeriesKey(suit_id=suit_id):
                series_info = book.get_book_series_info(suit_id, data_repo=data_repo)
                if series_info is None:
                    return None
                return book.render_book_series(
                    series_info, data_repo.language, first_seen_index=first_seen_index
                )
            case _BookStandaloneKey(filename=filename):
                return _process_single_readable(
                    filename,
                    data_repo,
                    book.render_book,
                    first_seen_index=first_seen_index,
                )
            case _:
                assert_never(renderable_key)


class Weapons(BaseRenderableType[str]):
    """Weapon story content type."""

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
        self,
        renderable_key: str,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Assemble and render a weapon's story document, or skip if it has none."""
        if (
            weapon_info := weapon.get_weapon_info(renderable_key, data_repo=data_repo)
        ) is None:
            return None
        return weapon.render_weapon(weapon_info, first_seen_index=first_seen_index)


class Wings(BaseReadables):
    """Wings readable content type."""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_WINGS

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.ReadableFilename]:
        """Find all readable files whose filename starts with Wings."""
        return _discover_prefixed_readables(data_repo, "Wings")


class Costumes(BaseReadables):
    """Costume readable content type."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_COSTUME
    )

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.ReadableFilename]:
        """Find all readable files whose filename starts with Costume."""
        return _discover_prefixed_readables(data_repo, "Costume")


class Quests(BaseRenderableType[id_types.QuestId]):
    """Quest content type (dialog, cutscenes, etc.)"""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_QUEST
    error_limit: ClassVar[int] = 100
    error_limit_non_chinese: ClassVar[int] = 2000

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.QuestId]:
        """Find all quest IDs from MainQuestExcelConfigData."""
        return sorted(data_repo.load_main_quest_excel_config_data(), key=str)

    def process(
        self,
        renderable_key: id_types.QuestId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process quest file into rendered content."""
        if (
            quest_info := quest.get_quest_info(renderable_key, data_repo=data_repo)
        ) is None:
            return None

        if not (
            any(step.talk is not None for step in quest_info.steps)
            or quest_info.non_subquest_talks
        ):
            return None

        return quest.render_quest(
            quest_info, language=data_repo.language, first_seen_index=first_seen_index
        )


class CharacterStories(BaseRenderableType[id_types.AvatarId]):
    """Character story content type."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_CHARACTER_STORY
    )

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.AvatarId]:
        """Find all unique character IDs that have stories."""
        fetter_data = data_repo.load_fetter_story_excel_config_data()
        avatar_ids = set()
        for story in fetter_data:
            avatar_id = story.get("avatarId")
            if avatar_id:
                avatar_ids.add(avatar_id)
        return sorted(avatar_ids)

    def process(
        self,
        renderable_key: id_types.AvatarId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process character story into rendered content."""
        story_info = character.get_character_story_info(
            renderable_key, data_repo=data_repo
        )
        return character.render_character_story(
            story_info, first_seen_index=first_seen_index
        )


class Subtitles(BaseRenderableType[str]):
    """Subtitle content type (.srt files)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_SUBTITLE
    )

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Find all subtitle files."""
        return [
            f"Subtitle/{data_repo.language_short}/{name}"
            for name in data_repo.list_subtitle_names()
            if name.endswith(".srt")
        ]

    def process(
        self,
        renderable_key: str,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process subtitle file into rendered content."""
        subtitle_info = subtitle.get_subtitle_info(renderable_key, data_repo=data_repo)
        if not subtitle.has_meaningful_content(subtitle_info):
            return None
        return subtitle.render_subtitle(
            subtitle_info,
            renderable_key,
            subtitle.build_subtitle_title(renderable_key, data_repo=data_repo),
            first_seen_index=first_seen_index,
        )


class MaterialTypes(BaseRenderableType[str]):
    """Material types content type (materials grouped by type)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_MATERIAL_TYPE
    )

    def discover(self, data_repo: repo.DataRepo) -> list[str]:
        """Discover all unique material types."""
        materials_data = data_repo.build_material_tracker().get_all()
        return sorted(
            Counter(material["materialType"] for material in materials_data).keys()
        )

    def process(
        self,
        renderable_key: str,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process all materials of a given type into rendered content."""
        materials_data = data_repo.build_material_tracker().get_all()
        materials_of_type = []

        for material_data in materials_data:
            if material_data["materialType"] != renderable_key:
                continue

            material_id = material_data["id"]
            material_info = material.get_material_info(material_id, data_repo=data_repo)

            if text_utils.should_skip_text(
                material_info.name, data_repo.language
            ) or text_utils.should_skip_text(
                material_info.description, data_repo.language
            ):
                continue

            materials_of_type.append(material_info)

        if not materials_of_type:
            return None

        return material.render_materials_by_type(
            renderable_key, materials_of_type, first_seen_index=first_seen_index
        )


class Achievements(BaseRenderableType[id_types.AchievementGoalId]):
    """Achievements grouped by their in-game section."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_ACHIEVEMENT
    )

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.AchievementGoalId]:
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
        self,
        renderable_key: id_types.AchievementGoalId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem:
        """Process one achievement section into rendered content."""
        return achievement.render_achievement_section(
            achievement.get_achievement_section_info(
                renderable_key, data_repo=data_repo
            ),
            first_seen_index=first_seen_index,
        )


class Voicelines(BaseRenderableType[id_types.AvatarId]):
    """Voiceline content type (character voice lines)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_VOICELINE
    )

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.AvatarId]:
        """Find all avatar IDs that have voicelines."""
        return sorted(
            {
                fetter["avatarId"]
                for fetter in data_repo.load_fetters_excel_config_data()
            }
        )

    def process(
        self,
        renderable_key: id_types.AvatarId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process voiceline into rendered content."""
        voiceline_info = character.get_voiceline_info(
            renderable_key, data_repo=data_repo
        )

        if not voiceline_info.voicelines:
            return None

        return character.render_voiceline(
            voiceline_info, first_seen_index=first_seen_index
        )


class ArtifactSets(BaseRenderableType[id_types.ArtifactSetId]):
    """Artifact set content type (artifact sets with individual piece stories)."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_ARTIFACT_SET
    )

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.ArtifactSetId]:
        """Find all artifact set IDs from ReliquarySetExcelConfigData."""
        set_data = data_repo.load_reliquary_set_excel_config_data()
        return [set_entry["setId"] for set_entry in set_data]

    def process(
        self,
        renderable_key: id_types.ArtifactSetId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process artifact set into rendered content."""
        if (
            artifact_set_info := artifact.get_artifact_set_info(
                renderable_key, data_repo=data_repo
            )
        ) is None:
            return None

        return artifact.render_artifact_set(
            artifact_set_info, first_seen_index=first_seen_index
        )


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
        self,
        renderable_key: str,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process a codex subType group into a single rendered file."""
        return creature.render_creature_group(
            creature.get_creature_group_info(renderable_key, data_repo=data_repo),
            first_seen_index=first_seen_index,
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
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process talk activity group into rendered content."""
        talk_group_type, talk_group_id = renderable_key
        talk_group_info = talk_group.get_talk_group_info(
            talk_group_type, talk_group_id, data_repo=data_repo
        )

        if not talk_group_info.talks:
            return None

        group_name: str | None = None
        match talk_group_type:
            case "NpcGroup":
                # An NpcGroup's TalkGroupId is the file's own npcId field (see
                # TalkParser._handle_talk_group_file), so it is a genuine NpcId.
                npc_id = int(talk_group_id)
                source_name = data_repo.build_npc_id_to_source_name_mapping().get(
                    npc_id
                )
                if source_name is not None:
                    if text_utils.should_skip_text(
                        source_name, localization.Language.CHS
                    ):
                        return None
                    group_name = data_repo.build_npc_id_to_name_mapping()[npc_id]
                    if (
                        mode := data_repo.build_npc_id_to_game_mode_mapping().get(
                            npc_id
                        )
                    ) is not None:
                        group_name = f"{group_name} - {localization.get_game_mode_label(mode, language=data_repo.language)}"
            case "ActivityGroup":
                group_name = data_repo.build_activity_id_to_name_mapping().get(
                    int(talk_group_id)
                )
            case "GadgetGroup":
                group_name = talk_group.derive_speaker_group_name(
                    talk_group_info, data_repo.language
                )
            case _:
                assert_never(talk_group_type)

        return talk_group.render_talk_group(
            talk_group_type,
            talk_group_id,
            talk_group_info,
            data_repo.language,
            group_name=group_name,
            first_seen_index=first_seen_index,
        )


class Hangouts(BaseRenderableType[id_types.QuestId]):
    """Hangout (Coop) content type: one file per hangout quest, in play order."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_HANGOUT
    )
    error_limit: ClassVar[int] = 50
    error_limit_non_chinese: ClassVar[int] = 200

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.QuestId]:
        """All hangout quest ids that have Coop talk files."""
        return sorted(data_repo.build_hangout_quest_to_stories_mapping())

    def process(
        self,
        renderable_key: id_types.QuestId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Render a hangout quest's Coop dialogue, or skip if it has no content."""
        if (
            hangout_info := hangout.get_hangout_info(
                renderable_key, data_repo=data_repo
            )
        ) is None:
            return None
        return hangout.render_hangout(
            hangout_info,
            language=data_repo.language,
            first_seen_index=first_seen_index,
        )


class Anecdotes(BaseRenderableType[id_types.AnecdoteId]):
    """Anecdote (Odd Encounter) content type: one file per world vignette."""

    text_category: ClassVar[text_types.TextCategory] = (
        text_types.TextCategory.AGD_ANECDOTE
    )
    error_limit: ClassVar[int] = 10
    error_limit_non_chinese: ClassVar[int] = 20

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.AnecdoteId]:
        """All anecdote ids from the anecdote excel config."""
        return sorted(data_repo.load_anecdote_excel_config_data())

    def process(
        self,
        renderable_key: id_types.AnecdoteId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Render an anecdote, or skip when none of its talks have content."""
        if (
            anecdote_info := anecdote.get_anecdote_info(
                renderable_key, data_repo=data_repo
            )
        ) is None:
            return None
        return anecdote.render_anecdote(
            anecdote_info,
            language=data_repo.language,
            first_seen_index=first_seen_index,
        )


class Talks(BaseRenderableType[id_types.TalkId]):
    """Standalone talk content type for talks not used by other renderable types."""

    text_category: ClassVar[text_types.TextCategory] = text_types.TextCategory.AGD_TALK
    error_limit: ClassVar[int] = 1000
    error_limit_non_chinese: ClassVar[int] = 1000

    def __init__(self, used_talk_ids: set[id_types.TalkId]) -> None:
        """Initialize with set of already used talk IDs."""
        self.used_talk_ids = used_talk_ids

    @classmethod
    def create_for_generation(cls, accessed_stats: tracking.TrackerStats) -> "Talks":
        return cls(accessed_stats.accessed[tracking.TrackerKind.TALK].copy())

    def discover(self, data_repo: repo.DataRepo) -> list[id_types.TalkId]:
        """Find all talk IDs that are not already used."""
        talk_tracker = data_repo.build_talk_tracker()
        return sorted(talk_tracker.get_all_ids() - self.used_talk_ids)

    def process(
        self,
        renderable_key: id_types.TalkId,
        data_repo: repo.DataRepo,
        *,
        first_seen_index: first_seen.FirstSeenIndex,
    ) -> processed_types.RenderedItem | None:
        """Process talk into rendered content."""
        talk_tracker = data_repo.build_talk_tracker()
        talk_file_path = talk_tracker.get_talk_file_path(renderable_key)

        if talk_file_path is None:
            return None

        talk_info = _talk.get_talk_info_by_id(renderable_key, data_repo=data_repo)

        if not talk_info.text:
            return None

        return _talk.render_talk(
            talk_info,
            talk_id=renderable_key,
            language=data_repo.language,
            talk_file_path=talk_file_path,
            first_seen_index=first_seen_index,
        )


# Ordered list of every AGD renderable type, in the order generate-all runs
# them. Readables and Talks come last: each emits only the ids no earlier pass
# already claimed, so they must run after everything else.
ALL_RENDERABLE_TYPES: list[type[BaseRenderableType]] = [
    ArtifactSets,
    Creatures,
    Quests,
    CharacterStories,
    Subtitles,
    MaterialTypes,
    Achievements,
    Voicelines,
    TalkGroups,
    Hangouts,
    Anecdotes,
    Books,
    Weapons,
    Wings,
    Costumes,
    Readables,
    Talks,
]

# Every AGD category must be produced by exactly one renderable type here, so a
# newly added TextCategory can't be silently dropped from the pipeline.
assert {renderable_type.text_category for renderable_type in ALL_RENDERABLE_TYPES} == {
    category for category in text_types.TextCategory if category.is_agd
}, "ALL_RENDERABLE_TYPES is out of sync with the AGD TextCategory enum"
