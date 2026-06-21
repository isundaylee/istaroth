"""Processed/rendered Istaroth domain types.

``attrs`` classes produced by the processing/rendering pipeline (the ``*Info``
classes, ``RenderedItem``, hierarchy and tracker types). These are our own
internal representations, not raw AGD wire data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import attrs

from istaroth.agd import id_types

if TYPE_CHECKING:
    from istaroth.agd.repo import ReadablesTracker, TalkTracker, TextMapTracker
    from istaroth.text import types as text_types


@attrs.define
class LocalizedRoleNames:
    """Localized names for various talk roles."""

    player: str
    mate_avatar: str
    black_screen: str
    unknown_npc: str
    unknown_role: str


@attrs.define
class ReadableMetadata:
    """Metadata for a readable item."""

    localization_id: id_types.LocalizationId
    title: str


@attrs.define
class BookVolumeInfo:
    """A single volume's title and cleaned body within a book series."""

    title: str
    content: str


@attrs.define
class BookSeriesInfo:
    """A multi-volume book series with its volumes in reading order."""

    suit_id: id_types.BookSuitId
    series_name: str
    volumes: list[BookVolumeInfo]


@attrs.define
class TalkText:
    """Individual talk dialog text."""

    role: str | None
    message: str
    next_dialog_ids: list[id_types.DialogId]
    dialog_id: id_types.DialogId


@attrs.define
class TalkInfo:
    """Talk information with dialog text."""

    text: list[TalkText]


@attrs.define
class TalkGroupInfo:
    talks: list[tuple[TalkInfo, list[TalkInfo]]]
    """List of (talk, next_talks)."""


@attrs.define
class CoopChoiceOption:
    """One branch of a hangout player choice: its prompt and the steps it leads to."""

    prompt: str | None
    steps: list[CoopStep]


@attrs.define
class CoopChoice:
    """A hangout player-choice point fanning into one branch per option."""

    options: list[CoopChoiceOption]


@attrs.define
class CoopStep:
    """One play-ordered step of a hangout story: a talk OR a player choice."""

    talk: TalkInfo | None
    choice: CoopChoice | None


@attrs.define
class CoopStoryInfo:
    """One hangout (Coop) story branch, its talks in play order."""

    coop_story_id: id_types.CoopStoryId
    steps: list[CoopStep]


@attrs.define
class HangoutInfo:
    """A hangout quest: its primary character and play-ordered story branches."""

    quest_id: id_types.QuestId
    quest_title: str
    primary_character: str | None
    stories: list[CoopStoryInfo]


@attrs.define
class QuestStep:
    """A single quest-progression step at a subQuest ``order``.

    A step is either a dialogue step (``talk`` set) or a non-dialogue objective
    (``talk`` is None, e.g. "defeat the monsters"). ``description`` is the
    subQuest's in-game objective text (from its ``descTextMapHash``), shown for
    both kinds when present. ``is_lead_in`` marks a talk placed by its own
    beginCond (a lead-in that plays during the step but doesn't complete it)
    rather than by a finish condition.
    """

    order: int
    is_lead_in: bool
    description: str | None
    talk: TalkInfo | None


@attrs.define
class QuestInfo:
    """Quest information with associated talk dialogs."""

    quest_id: id_types.QuestId
    title: str
    chapter_title: str | None
    description: str | None
    steps: list[QuestStep]
    """Talk and objective steps interleaved by subQuest ``order``."""
    non_subquest_talks: list[TalkInfo]
    associated_free_talks: list[TalkInfo]
    """FreeGroup "free talks" attached to this quest by talkId numbering."""


@attrs.define
class HierarchyNode:
    """One node in a browsable document hierarchy.

    A node is either a group (``children`` set) or a leaf (``file_id`` set, a
    viewable file). Data-derived labels use ``title``; labels that are translated
    on the frontend (the library root, a category, a quest type, "standalone")
    carry an i18n ``title_key`` instead. ``title`` and ``title_key`` are mutually
    exclusive.
    """

    key: str
    """URL-safe identifier, unique among siblings."""
    title: str | None
    title_key: str | None
    children: list[HierarchyNode] | None
    file_id: int | None
    toc_eligible: bool
    """Whether, when this group is a viewed file's section root, its children form
    a coherent table of contents. False for leaves and for synthetic buckets that
    merely collect unrelated files (e.g. the "standalone" group)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "title_key": self.title_key,
            "children": (
                None
                if self.children is None
                else [child.to_dict() for child in self.children]
            ),
            "file_id": self.file_id,
            "toc_eligible": self.toc_eligible,
        }


@attrs.define
class Hierarchy:
    """The browsable document hierarchy of a single category."""

    nodes: list[HierarchyNode]

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [node.to_dict() for node in self.nodes]}


@attrs.define
class CharacterStory:
    """Individual character story with title and content."""

    title: str
    content: str


@attrs.define
class Constellation:
    """A single constellation (命之座) name and description.

    ``element`` is set only for the Travelers, whose constellations are
    per-element; it is ``None`` for regular characters.
    """

    name: str
    description: str
    element: str | None


@attrs.define
class CharacterStoryInfo:
    """Character story information containing all stories for a character."""

    character_name: str
    stories: list[CharacterStory]
    avatar_id: id_types.AvatarId
    constellations: list[Constellation]


@attrs.define
class SubtitleInfo:
    """Subtitle information containing all subtitle text."""

    text_lines: list[str]


@attrs.define
class MaterialInfo:
    """Material information with name and description."""

    material_id: id_types.MaterialId
    name: str
    description: str


@attrs.define
class AchievementInfo:
    """Localized achievement text."""

    achievement_id: id_types.AchievementId
    name: str
    description: str


@attrs.define
class AchievementSectionInfo:
    """Localized achievements grouped by their in-game section."""

    section_id: id_types.AchievementGoalId
    section_name: str
    achievements: list[AchievementInfo]


@attrs.define
class CreatureInfo:
    """A single living-beings archive entry: names and archive description.

    ``special_name``/``title`` are populated for monsters when they differ from
    ``name`` (wildlife carry only ``name``).
    """

    codex_id: id_types.AnimalCodexId
    name: str
    special_name: str | None
    title: str | None
    description: str


@attrs.define
class CreatureGroupInfo:
    """All creatures in one codex ``subType`` group, in archive order.

    ``subtype`` is the raw enum (filename/id); ``type_label``/``subtype_label``
    are the localized codex group names.
    """

    subtype: str
    type_label: str
    subtype_label: str
    creatures: list[CreatureInfo]


@attrs.define
class VoicelineInfo:
    """Voiceline information for a character."""

    character_name: str
    voicelines: dict[str, str]  # title -> content mapping
    avatar_id: id_types.AvatarId


@attrs.define
class TrackerStats:
    """Statistics for text map, talk ID, and readable access tracking."""

    accessed_text_map_ids: set[id_types.TextMapHash]
    accessed_talk_ids: set[id_types.TalkId]
    accessed_readable_filenames: set[id_types.ReadableFilename]

    def update(self, other: "TrackerStats") -> None:
        """Update this TrackerStats with IDs from another TrackerStats."""
        self.accessed_text_map_ids.update(other.accessed_text_map_ids)
        self.accessed_talk_ids.update(other.accessed_talk_ids)
        self.accessed_readable_filenames.update(other.accessed_readable_filenames)

    def to_dict(
        self,
        text_map_tracker: "TextMapTracker",
        talk_tracker: "TalkTracker",
        readables_tracker: "ReadablesTracker",
    ) -> dict[str, Any]:
        """Convert TrackerStats to dictionary format for JSON serialization."""
        result = {
            "stats": {
                "text_map": {
                    "unused": len(text_map_tracker.get_unused_ids()),
                    "total": text_map_tracker.get_total_count(),
                },
                "talk_ids": {
                    "unused": len(talk_tracker.get_unused_ids()),
                    "total": talk_tracker.get_total_count(),
                },
                "readables": {
                    "unused": len(readables_tracker.get_unused_ids()),
                    "total": readables_tracker.get_total_count(),
                },
            },
            "unused_ids": {
                "text_map": sorted(text_map_tracker.get_unused_ids()),
                "talk_ids": sorted(talk_tracker.get_unused_ids()),
                "readables": sorted(readables_tracker.get_unused_ids()),
            },
        }
        return result


@attrs.define
class ArtifactInfo:
    """Individual artifact information with name, description, and story."""

    name: str
    description: str
    story: str


@attrs.define
class ArtifactSetInfo:
    """Artifact set information containing all pieces in the set."""

    set_name: str
    set_id: id_types.ArtifactSetId
    artifacts: list[ArtifactInfo]


@attrs.define
class WeaponInfo:
    """A weapon's assembled story document: name, flavor description, and pages.

    ``story_pages`` holds the weapon's story document pages in reading order,
    joined into one rendered document (a multi-page weapon story is a single item).
    """

    weapon_id: str
    name: str
    description: str
    story_pages: list[str]


@attrs.define
class RenderedItem:
    """Rendered content suitable for RAG training."""

    text_metadata: text_types.TextMetadata
    content: str
