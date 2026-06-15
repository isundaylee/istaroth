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


# ============================================================================
# ID type aliases
# ============================================================================
# Documentation-only aliases (transparent to mypy) that name the many distinct
# kinds of AGD id, so signatures say *which* id they want instead of a bare
# ``int``/``str``. Each alias is the single canonical representation that id uses
# after parse; the raw JSON ``int`` is converted to it once, at the parse
# boundary, and never re-converted downstream. ``str``-canonical ids therefore
# leave their JSON ``.id: int`` field bare (that field *is* the boundary).

QuestId: TypeAlias = str
"""Quest id, as a string: quest-mapping / ``BinOutput/Quest/<id>.json`` key.

(The browsable quest *hierarchy* keeps quest ids as ``int``; this alias names
the str representation used by the processing/rendering pipeline.)
"""

TalkId: TypeAlias = str
"""Talk id, as a string (``talk_id_to_path`` key)."""

DialogId: TypeAlias = int
"""Dialog id within a talk's ``dialogList`` and the dialog graph."""

SubQuestId: TypeAlias = int
"""Sub-quest id (``SubQuestItem.subId``)."""

ChapterId: TypeAlias = int
"""Chapter (act) id."""

QuestSeriesId: TypeAlias = int
"""Series (questline) id: a chapter ``groupId`` grouping the acts of one story."""

NpcId: TypeAlias = str
"""NPC id, as a string (``npc_id_to_name`` key; dialog/talk role ``id``)."""

AvatarId: TypeAlias = str
"""Avatar (character) id, as a string (renderable key); ``int()`` for excel filtering."""

MaterialId: TypeAlias = str
"""Material id, as a string (material-tracker key)."""

ReliquaryId: TypeAlias = int
"""Individual artifact (reliquary piece) id."""

ArtifactSetId: TypeAlias = str
"""Artifact set id, as a string (renderable key)."""

AchievementId: TypeAlias = int
"""Achievement id."""

AchievementGoalId: TypeAlias = int
"""Achievement section/goal id (renderable key)."""

EquipAffixId: TypeAlias = int
"""Equip-affix (artifact set bonus) id."""

StoryId: TypeAlias = int
"""Relic story id (``ReliquaryExcelConfigDataItem.storyId``)."""

LocalizationId: TypeAlias = int
"""Localization-config id linking a readable to its document/title."""

DocumentId: TypeAlias = int
"""Document-config id (``DocumentExcelConfigDataItem.id``)."""

TextHash: TypeAlias = int
"""A TextMap hash as stored in JSON (the ``*TextMapHash`` fields).

Stringified to index ``TextMap`` (whose keys are ``str``) at lookup time.
"""


class NpcExcelConfigDataItem(TypedDict):
    """Type definition for individual NPC configuration entries."""

    id: int  # NpcId after str() at the parse boundary
    nameTextMapHash: TextHash


NpcExcelConfigData: TypeAlias = list[NpcExcelConfigDataItem]
"""List of NPC configuration items from Excel data.

Example file: ExcelBinOutput/NpcExcelConfigData.json
"""


class DialogTalkRole(TypedDict):
    """Type definition for talk role in dialog entries."""

    type: str
    id: NpcId


class DialogExcelConfigDataItem(TypedDict):
    """Type definition for individual dialog configuration entries."""

    GFLDJMJKIKE: DialogId
    talkRole: DialogTalkRole
    talkContentTextMapHash: TextHash
    talkRoleNameTextMapHash: TextHash


DialogExcelConfigData: TypeAlias = list[DialogExcelConfigDataItem]
"""List of dialog configuration items from Excel data.

Example file: ExcelBinOutput/DialogExcelConfigData.json
"""


class LocalizationExcelConfigDataItem(TypedDict):
    """Type definition for localization configuration entries."""

    id: LocalizationId
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

    id: DocumentId
    titleTextMapHash: TextHash
    CUSTOM_addlLocalID: NotRequired[list[LocalizationId]]
    questContentLocalizedId: list[LocalizationId]
    questIDList: list[LocalizationId]


DocumentExcelConfigData: TypeAlias = list[DocumentExcelConfigDataItem]
"""List of document configuration items mapping materials to readable content.

Example file: ExcelBinOutput/DocumentExcelConfigData.json
"""


class MaterialExcelConfigDataItem(TypedDict):
    """Type definition for material configuration entries."""

    id: int  # MaterialId after str() at the parse boundary
    nameTextMapHash: TextHash
    descTextMapHash: TextHash
    materialType: str


MaterialExcelConfigData: TypeAlias = list[MaterialExcelConfigDataItem]
"""List of material configuration items.

Example file: ExcelBinOutput/MaterialExcelConfigData.json
"""


class TalkExcelConfigDataItem(TypedDict):
    """Type definition for talk configuration entries."""

    id: int  # TalkId after str() at the parse boundary
    initDialog: DialogId


TalkExcelConfigData: TypeAlias = list[TalkExcelConfigDataItem]
"""List of talk configuration items.

Example file: ExcelBinOutput/TalkExcelConfigData.json
"""


class TalkRole(TypedDict):
    """Type definition for talk role."""

    type: str
    _id: NotRequired[NpcId]
    id: NotRequired[NpcId]


class TalkDialogItem(TypedDict):
    """Type definition for individual talk dialog entries."""

    id: DialogId
    talkRole: TalkRole
    talkContentTextMapHash: TextHash
    talkRoleNameTextMapHash: NotRequired[TextHash]
    nextDialogs: NotRequired[list[DialogId]]


class TalkData(TypedDict):
    """Talk data structure containing dialog list and metadata.

    Example file: BinOutput/Talk/Quest/7407811.json
    """

    talkId: int  # TalkId after str() at the parse boundary
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

    id: int  # TalkId after str() at the parse boundary
    beginCond: list[BeginCondItem]


class FinishCondItem(TypedDict):
    """A sub-quest finish condition.

    `damageRatio` is a misleading legacy cleartext field name (carried over from
    the 4.8-5.8 AGD dumps that had cleartext keys); the field actually holds the
    generic ``QUEST_CONTENT_*`` condition-type enum, not a damage ratio.
    """

    damageRatio: str
    param: list[int]
    count: int
    CUSTOM_paramStr: NotRequired[str]


class SubQuestItem(TypedDict):
    """Type definition for sub-quest entries.

    ``descTextMapHash`` is the in-game quest-tracker objective text for the step
    (e.g. "defeat the monsters", "go to the marked location"); ``0`` when the
    step has no player-facing objective.
    """

    subId: SubQuestId
    order: int
    descTextMapHash: TextHash
    finishCond: list[FinishCondItem]


class QuestData(TypedDict):
    """Quest data structure containing talks and metadata.

    Example file: BinOutput/Quest/74078.json
    """

    id: int  # QuestId after str() at the parse boundary
    descTextMapHash: TextHash
    titleTextMapHash: TextHash
    chapterId: ChapterId  # 0 when the quest belongs to no chapter
    subQuests: list[SubQuestItem]
    talks: list[QuestTalkItem]


class AvatarExcelConfigDataItem(TypedDict):
    """Type definition for avatar configuration entries."""

    id: int  # AvatarId after str() at the parse boundary
    nameTextMapHash: TextHash


AvatarExcelConfigData: TypeAlias = list[AvatarExcelConfigDataItem]
"""List of avatar configuration items.

Example file: ExcelBinOutput/AvatarExcelConfigData.json
"""


class FetterStoryExcelConfigDataItem(TypedDict):
    """Type definition for fetter story configuration entries."""

    avatarId: int  # AvatarId; compared as int after int(avatar_id)
    storyTitleTextMapHash: TextHash
    storyContextTextMapHash: TextHash


FetterStoryExcelConfigData: TypeAlias = list[FetterStoryExcelConfigDataItem]


class FettersExcelConfigDataItem(TypedDict):
    avatarId: int  # AvatarId; compared as int after int(avatar_id)
    voiceTitleTextMapHash: TextHash
    voiceFileTextTextMapHash: TextHash


FettersExcelConfigData: TypeAlias = list[FettersExcelConfigDataItem]


class MainQuestExcelConfigDataItem(TypedDict):
    id: int  # quest id; kept int (the quest hierarchy keys on int quest ids)
    type: str  # AQ / LQ / WQ / EQ / IQ
    chapterId: ChapterId  # 0 when the quest belongs to no chapter
    suggestTrackMainQuestList: list[int]  # "next quest(s)" pointers (int quest ids)


MainQuestExcelConfigData: TypeAlias = list[MainQuestExcelConfigDataItem]


class ChapterExcelConfigDataItem(TypedDict):
    """Type definition for chapter configuration entries."""

    id: ChapterId
    chapterTitleTextMapHash: TextHash
    chapterNumTextMapHash: TextHash
    groupId: QuestSeriesId  # series: groups the acts of one questline; 0 when none
    beginQuestId: (
        int  # first subquest id; // 100 is its (int) main quest id (0 if none)
    )


ChapterExcelConfigData: TypeAlias = list[ChapterExcelConfigDataItem]


class AchievementExcelConfigDataItem(TypedDict):
    """Type definition for an achievement configuration entry."""

    id: AchievementId
    goalId: AchievementGoalId
    orderId: int
    titleTextMapHash: TextHash
    descTextMapHash: TextHash
    isDisuse: bool
    isShow: str


AchievementExcelConfigData: TypeAlias = list[AchievementExcelConfigDataItem]


class AchievementGoalExcelConfigDataItem(TypedDict):
    """Type definition for an achievement section configuration entry."""

    id: AchievementGoalId
    orderId: int
    nameTextMapHash: TextHash


AchievementGoalExcelConfigData: TypeAlias = list[AchievementGoalExcelConfigDataItem]


class ReliquarySetExcelConfigDataItem(TypedDict):
    """Type definition for artifact set configuration entries."""

    setId: int  # ArtifactSetId after str() at the parse boundary
    containsList: list[ReliquaryId]
    equipAffixId: EquipAffixId


class ReliquaryExcelConfigDataItem(TypedDict):
    """Type definition for individual artifact configuration entries."""

    id: ReliquaryId
    nameTextMapHash: TextHash
    descTextMapHash: TextHash
    storyId: StoryId


class EquipAffixExcelConfigDataItem(TypedDict):
    """Type definition for equipment affix (artifact set bonus) entries."""

    id: EquipAffixId
    nameTextMapHash: TextHash


class WeaponExcelConfigDataItem(TypedDict):
    """Type definition for weapon configuration entries.

    ``storyId`` points at the weapon's DocumentExcelConfigData entry (0 when the
    weapon has no story document).
    """

    id: int
    nameTextMapHash: int
    descTextMapHash: int
    storyId: int


ReliquarySetExcelConfigData: TypeAlias = list[ReliquarySetExcelConfigDataItem]
ReliquaryExcelConfigData: TypeAlias = list[ReliquaryExcelConfigDataItem]
EquipAffixExcelConfigData: TypeAlias = list[EquipAffixExcelConfigDataItem]
WeaponExcelConfigData: TypeAlias = list[WeaponExcelConfigDataItem]

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

    localization_id: LocalizationId
    title: str


@attrs.define
class TalkText:
    """Individual talk dialog text."""

    role: str | None
    message: str
    next_dialog_ids: list[DialogId]
    dialog_id: DialogId


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

    quest_id: QuestId
    title: str
    chapter_title: str | None
    description: str | None
    steps: list[QuestStep]
    """Talk and objective steps interleaved by subQuest ``order``."""
    non_subquest_talks: list[TalkInfo]
    associated_free_talks: list[TalkInfo]
    """FreeGroup "free talks" attached to this quest by talkId numbering."""


@attrs.define
class QuestHierarchyQuest:
    """A single quest leaf in the browsable quest hierarchy."""

    id: int  # quest id, kept int here (the hierarchy keys on int quest ids)
    title: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title}


@attrs.define
class QuestHierarchyChapter:
    """One chapter (act) grouping a set of quests."""

    chapter_id: ChapterId
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

    series_id: QuestSeriesId
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
    avatar_id: AvatarId


@attrs.define
class SubtitleInfo:
    """Subtitle information containing all subtitle text."""

    text_lines: list[str]


@attrs.define
class MaterialInfo:
    """Material information with name and description."""

    material_id: MaterialId
    name: str
    description: str


@attrs.define
class AchievementInfo:
    """Localized achievement text."""

    achievement_id: AchievementId
    name: str
    description: str


@attrs.define
class AchievementSectionInfo:
    """Localized achievements grouped by their in-game section."""

    section_id: AchievementGoalId
    section_name: str
    achievements: list[AchievementInfo]


@attrs.define
class VoicelineInfo:
    """Voiceline information for a character."""

    character_name: str
    voicelines: dict[str, str]  # title -> content mapping
    avatar_id: AvatarId


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
    set_id: ArtifactSetId
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
