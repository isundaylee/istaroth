"""Type definitions for AnimeGameData (AGD) structures."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NotRequired, TypeAlias, TypedDict

if TYPE_CHECKING:
    from istaroth.agd.repo import TextMapTracker, TalkTracker, ReadablesTracker
    from istaroth.text import types as text_types

import attrs

# ============================================================================
# AGD JSON File Types
# ============================================================================
# These types match the structure of JSON files from AnimeGameData

TextMap: TypeAlias = dict[str, str]
"""Dictionary mapping string IDs to localized text content.

Example file: TextMap/TextMapCHS.json
"""


class NpcExcelConfigDataItem(TypedDict):
    """Type definition for individual NPC configuration entries."""

    id: int
    nameTextMapHash: int


NpcExcelConfigData: TypeAlias = list[NpcExcelConfigDataItem]
"""List of NPC configuration items from Excel data.

Example file: ExcelBinOutput/NpcExcelConfigData.json
"""


class DialogTalkRole(TypedDict):
    """Type definition for talk role in dialog entries."""

    type: str
    id: NotRequired[str]
    _id: NotRequired[int]


class DialogExcelConfigDataItem(TypedDict):
    """Type definition for individual dialog configuration entries."""

    GFLDJMJKIKE: int
    talkRole: DialogTalkRole
    talkContentTextMapHash: int
    talkRoleNameTextMapHash: int


DialogExcelConfigData: TypeAlias = list[DialogExcelConfigDataItem]
"""List of dialog configuration items from Excel data.

Example file: ExcelBinOutput/DialogExcelConfigData.json
"""


class LocalizationExcelConfigDataItem(TypedDict):
    """Type definition for localization configuration entries."""

    id: int
    assetType: str
    defaultPath: str
    scPath: str
    tcPath: str
    enPath: str
    krPath: str
    jpPath: str
    esPath: str
    frPath: str
    idPath: str
    ptPath: str
    ruPath: str
    thPath: str
    viPath: str
    dePath: str
    trPath: str
    itPath: str


LocalizationExcelConfigData: TypeAlias = list[LocalizationExcelConfigDataItem]
"""List of localization configuration items.

Example file: ExcelBinOutput/LocalizationExcelConfigData.json
"""


class DocumentExcelConfigDataItem(TypedDict):
    """Type definition for document configuration entries."""

    id: int
    titleTextMapHash: int
    CUSTOM_addlLocalID: NotRequired[list[int]]
    questContentLocalizedId: list[int]
    questIDList: list[int]


DocumentExcelConfigData: TypeAlias = list[DocumentExcelConfigDataItem]
"""List of document configuration items mapping materials to readable content.

Example file: ExcelBinOutput/DocumentExcelConfigData.json
"""


class MaterialExcelConfigDataItem(TypedDict):
    """Type definition for material configuration entries."""

    id: int
    nameTextMapHash: int
    descTextMapHash: int
    materialType: str


MaterialExcelConfigData: TypeAlias = list[MaterialExcelConfigDataItem]
"""List of material configuration items.

Example file: ExcelBinOutput/MaterialExcelConfigData.json
"""


class TalkExcelConfigDataItem(TypedDict):
    """Type definition for talk configuration entries."""

    id: int
    initDialog: NotRequired[int]


TalkExcelConfigData: TypeAlias = list[TalkExcelConfigDataItem]
"""List of talk configuration items.

Example file: ExcelBinOutput/TalkExcelConfigData.json
"""


class TalkRole(TypedDict):
    """Type definition for talk role."""

    type: str
    _id: NotRequired[str]
    id: NotRequired[str]


class TalkDialogItem(TypedDict):
    """Type definition for individual talk dialog entries."""

    id: int
    talkRole: TalkRole
    talkContentTextMapHash: int
    talkRoleNameTextMapHash: NotRequired[int]
    nextDialogs: NotRequired[list[int]]


class TalkData(TypedDict):
    """Talk data structure containing dialog list and metadata.

    Example file: BinOutput/Talk/Quest/7407811.json
    """

    talkId: int
    dialogList: list[TalkDialogItem]


class BeginCondItem(TypedDict):
    """A quest talk's begin condition.

    Unlike ``FinishCondItem`` (which uses the obfuscation-renamed ``damageRatio``
    / ``param`` keys), begin-condition entries carry the literal ``_type`` /
    ``_param`` keys and are left un-renamed by the deobfuscation pass.
    """

    _type: str
    _param: list[str]


class QuestTalkItem(TypedDict):
    """Type definition for quest talk entries."""

    id: int
    beginCond: NotRequired[list[BeginCondItem]]


class FinishCondItem(TypedDict):
    """A sub-quest finish condition.

    `damageRatio` is a misleading legacy cleartext field name (carried over from
    the 4.8-5.8 AGD dumps that had cleartext keys); the field actually holds the
    generic ``QUEST_CONTENT_*`` condition-type enum, not a damage ratio.
    """

    damageRatio: str
    param: list[int]
    count: NotRequired[int]
    CUSTOM_paramStr: NotRequired[str]


class SubQuestItem(TypedDict):
    """Type definition for sub-quest entries.

    ``descTextMapHash`` is the in-game quest-tracker objective text for the step
    (e.g. "defeat the monsters", "go to the marked location"); ``0`` when the
    step has no player-facing objective.
    """

    subId: int
    order: int
    descTextMapHash: int
    finishCond: NotRequired[list[FinishCondItem]]


class QuestData(TypedDict):
    """Quest data structure containing talks and metadata.

    Example file: BinOutput/Quest/74078.json
    """

    id: int
    descTextMapHash: int
    titleTextMapHash: int
    chapterId: NotRequired[int]
    subQuests: list[SubQuestItem]
    talks: NotRequired[list[QuestTalkItem]]  # Optional field, not always present


class AvatarExcelConfigDataItem(TypedDict):
    """Type definition for avatar configuration entries."""

    id: int
    nameTextMapHash: int


AvatarExcelConfigData: TypeAlias = list[AvatarExcelConfigDataItem]
"""List of avatar configuration items.

Example file: ExcelBinOutput/AvatarExcelConfigData.json
"""


class FetterStoryExcelConfigDataItem(TypedDict):
    """Type definition for fetter story configuration entries."""

    avatarId: int
    storyTitleTextMapHash: int
    storyContextTextMapHash: int


FetterStoryExcelConfigData: TypeAlias = list[FetterStoryExcelConfigDataItem]


class FettersExcelConfigDataItem(TypedDict):
    avatarId: int
    voiceTitleTextMapHash: int
    voiceFileTextTextMapHash: int


FettersExcelConfigData: TypeAlias = list[FettersExcelConfigDataItem]


class MainQuestExcelConfigDataItem(TypedDict):
    id: int
    type: NotRequired[str]  # AQ / LQ / WQ / EQ / IQ
    chapterId: NotRequired[int]


MainQuestExcelConfigData: TypeAlias = list[MainQuestExcelConfigDataItem]


class ChapterExcelConfigDataItem(TypedDict):
    """Type definition for chapter configuration entries."""

    id: int
    chapterTitleTextMapHash: int
    chapterNumTextMapHash: int
    groupId: NotRequired[int]  # series: groups the acts of one questline


ChapterExcelConfigData: TypeAlias = list[ChapterExcelConfigDataItem]


class ReliquarySetExcelConfigDataItem(TypedDict):
    """Type definition for artifact set configuration entries."""

    setId: int
    containsList: list[int]


class ReliquaryExcelConfigDataItem(TypedDict):
    """Type definition for individual artifact configuration entries."""

    id: int
    nameTextMapHash: int
    descTextMapHash: NotRequired[int]


ReliquarySetExcelConfigData: TypeAlias = list[ReliquarySetExcelConfigDataItem]
ReliquaryExcelConfigData: TypeAlias = list[ReliquaryExcelConfigDataItem]

"""List of main quest configuration items.

Example file: ExcelBinOutput/MainQuestExcelConfigData.json
"""


# ============================================================================
# Istaroth Internal Types
# ============================================================================
# These types are defined and used within our codebase for processed data


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

    localization_id: int
    title: str


@attrs.define
class TalkText:
    """Individual talk dialog text."""

    role: str
    message: str
    next_dialog_ids: list[int]
    dialog_id: int


@attrs.define
class TalkInfo:
    """Talk information with dialog text."""

    text: list[TalkText]


@attrs.define
class TalkGroupInfo:
    talks: list[tuple[TalkInfo, list[TalkInfo]]]
    """List of (talk, next_talks)."""


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

    quest_id: str
    title: str
    chapter_title: str | None
    description: str | None
    steps: list[QuestStep]
    """Talk and objective steps interleaved by subQuest ``order``."""
    non_subquest_talks: list[TalkInfo]


@attrs.define
class QuestHierarchyQuest:
    """A single quest leaf in the browsable quest hierarchy."""

    id: int
    title: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title}


@attrs.define
class QuestHierarchyChapter:
    """One chapter (act) grouping a set of quests."""

    chapter_id: int
    chapter_title: str
    quests: list[QuestHierarchyQuest]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "chapter_title": self.chapter_title,
            "quests": [q.to_dict() for q in self.quests],
        }


@attrs.define
class QuestHierarchySeries:
    """A series (questline) grouping the chapters that share a chapter ``groupId``."""

    series_id: int
    series_title: str
    chapters: list[QuestHierarchyChapter]

    def to_dict(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "series_title": self.series_title,
            "chapters": [c.to_dict() for c in self.chapters],
        }


@attrs.define
class QuestHierarchyType:
    """A top-level quest type (AQ/LQ/WQ/EQ/IQ) and the quests under it.

    ``chapters`` holds chapters that have no series; ``standalone_quests`` holds
    quests with no chapter at all.
    """

    quest_type: str
    series: list[QuestHierarchySeries]
    chapters: list[QuestHierarchyChapter]
    standalone_quests: list[QuestHierarchyQuest]

    def to_dict(self) -> dict[str, Any]:
        return {
            "quest_type": self.quest_type,
            "series": [s.to_dict() for s in self.series],
            "chapters": [c.to_dict() for c in self.chapters],
            "standalone_quests": [q.to_dict() for q in self.standalone_quests],
        }


@attrs.define
class QuestHierarchy:
    """The full browsable quest hierarchy: type -> series -> chapter -> quest."""

    types: list[QuestHierarchyType]

    def to_dict(self) -> dict[str, Any]:
        return {"types": [t.to_dict() for t in self.types]}


@attrs.define
class CharacterStory:
    """Individual character story with title and content."""

    title: str
    content: str


@attrs.define
class CharacterStoryInfo:
    """Character story information containing all stories for a character."""

    character_name: str
    stories: list[CharacterStory]
    avatar_id: str


@attrs.define
class SubtitleInfo:
    """Subtitle information containing all subtitle text."""

    text_lines: list[str]


@attrs.define
class MaterialInfo:
    """Material information with name and description."""

    material_id: str
    name: str
    description: str


@attrs.define
class VoicelineInfo:
    """Voiceline information for a character."""

    character_name: str
    voicelines: dict[str, str]  # title -> content mapping
    avatar_id: str


@attrs.define
class TrackerStats:
    """Statistics for text map, talk ID, and readable access tracking."""

    accessed_text_map_ids: set[str]
    accessed_talk_ids: set[str]
    accessed_readable_ids: set[str]

    def update(self, other: "TrackerStats") -> None:
        """Update this TrackerStats with IDs from another TrackerStats."""
        self.accessed_text_map_ids.update(other.accessed_text_map_ids)
        self.accessed_talk_ids.update(other.accessed_talk_ids)
        self.accessed_readable_ids.update(other.accessed_readable_ids)

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
    set_id: str
    artifacts: list[ArtifactInfo]


@attrs.define
class RenderedItem:
    """Rendered content suitable for RAG training."""

    text_metadata: text_types.TextMetadata
    content: str
