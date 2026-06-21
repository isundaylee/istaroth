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
# kinds of AGD id, so a signature says *which* id it carries instead of a bare
# ``int``. Each alias is the id's on-disk JSON wire type -- every AGD id ships as
# ``int`` -- and the pipeline carries it as ``int`` end-to-end. ``str`` appears
# only at genuine boundaries: output filenames, ``TextMap`` lookups, and the few
# spots that compare an id to a file-path stem.

QuestId: TypeAlias = int
"""Quest id (``QuestData.id``); carried as ``int``, stringified only for filenames."""

TalkId: TypeAlias = int
"""Talk id (``TalkData.talkId``); carried as ``int``.

Stringified only where a talk file is resolved by comparing the id to a file-path
stem (the talkId-collision resolution in ``talk_parsing``).
"""

DialogId: TypeAlias = int
"""Dialog id within a talk's ``dialogList`` and the dialog graph."""

SubQuestId: TypeAlias = int
"""Sub-quest id (``SubQuestItem.subId``)."""

ChapterId: TypeAlias = int
"""Chapter (act) id."""

QuestSeriesId: TypeAlias = int
"""Series (questline) id: a chapter ``groupId`` grouping the acts of one story."""

CoopStoryId: TypeAlias = int
"""Coop (hangout) story id (``CoopInteractionExcelConfigDataItem.id``, e.g.
``1900102``); the ``<coopStoryId>`` prefix of a ``Talk/Coop/<id>_<localTalkId>.json``
file. Equals ``mainQuestId * 100 + sequence``."""

CoopNodeId: TypeAlias = int
"""Coop story-graph node id (a ``coopMap`` key). For a ``COOP_NODE_TALK`` node it
equals the local talk id (the ``_<localTalkId>`` suffix of the talk filename)."""

NpcId: TypeAlias = int
"""NPC id, as it ships in the master table (``NpcExcelConfigDataItem.id``).

Dialog/talk role *references* (``talkRole.id`` / ``_id``) and the
``npc_id_to_name`` map key carry the id as a plain ``str``, not this alias.
"""

GadgetConfigId: TypeAlias = int
"""Gadget config id (``GadgetGroup.configId``); the first half of a GadgetGroup's
composite ``(configId, groupId)`` key. Multiple GadgetGroup files can share a
``configId`` (e.g. ``1003`` has Tubby, Opéra notices, and an activity variant),
so ``configId`` alone is not a unique file key."""

GadgetGroupId: TypeAlias = int
"""GadgetGroup group id (``GadgetGroup.groupId``); the second half of the
composite key. Always ships as a 9-digit int (min ``111101079``), so the
``configId * 10**9 + groupId`` composite int is collision-free and fits
``TextMetadata.id`` (and JS ``Number.MAX_SAFE_INTEGER``)."""

AvatarId: TypeAlias = int
"""Avatar (character) id (``AvatarExcelConfigDataItem.id``); carried as ``int``."""

MaterialId: TypeAlias = int
"""Material id (``MaterialExcelConfigDataItem.id``); carried as ``int``."""

BookSuitId: TypeAlias = int
"""Book-series (suit) id (``BookSuitExcelConfigDataItem.id``;
``MaterialExcelConfigDataItem.setID`` for a book volume's series, 0 when none)."""

BooksCodexId: TypeAlias = int
"""Book-archive codex entry id (``BooksCodexExcelConfigDataItem.id``)."""

ReliquaryId: TypeAlias = int
"""Individual artifact (reliquary piece) id."""

ArtifactSetId: TypeAlias = int
"""Artifact set id (``ReliquarySetExcelConfigDataItem.setId``); carried as ``int``."""

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

SkillDepotId: TypeAlias = int
"""Skill-depot id (``AvatarSkillDepotExcelConfigDataItem.id``;
``AvatarExcelConfigDataItem.skillDepotId`` and ``candSkillDepotIds`` entries)."""

TalentId: TypeAlias = int
"""Constellation talent id (``AvatarTalentExcelConfigDataItem.talentId``;
``AvatarSkillDepotExcelConfigDataItem.talents`` entries)."""

SkillId: TypeAlias = int
"""Avatar skill id (``AvatarSkillExcelConfigDataItem.id``;
``AvatarSkillDepotExcelConfigDataItem.energySkill``)."""

AnimalCodexId: TypeAlias = int
"""Living-beings archive entry id (``AnimalCodexExcelConfigDataItem.id``); the
creature renderable key. Covers both monsters and wildlife."""

CreatureDescribeId: TypeAlias = int
"""Creature describe id (``AnimalCodexExcelConfigDataItem.describeId``). Keys
``MonsterDescribeExcelConfigData`` for ``CODEX_MONSTER`` entries and
``AnimalDescribeExcelConfigData`` for ``CODEX_ANIMAL`` entries (disjoint ranges)."""

MonsterTitleId: TypeAlias = int
"""Monster title id (``MonsterDescribeExcelConfigDataItem.titleID``;
``MonsterTitleExcelConfigDataItem.titleID``)."""

MonsterSpecialNameId: TypeAlias = int
"""Individual monster special-name id
(``MonsterSpecialNameExcelConfigDataItem.specialNameID``)."""

MonsterSpecialNameLabId: TypeAlias = int
"""Monster special-name lab/group id
(``MonsterDescribeExcelConfigDataItem.specialNameLabID``;
``MonsterSpecialNameExcelConfigDataItem.specialNameLabID``)."""

WeaponId: TypeAlias = int
"""Weapon id (``WeaponExcelConfigDataItem.id``)."""

TextMapHash: TypeAlias = int
"""A TextMap hash (the ``*TextMapHash`` fields); carried as ``int`` end-to-end.

``TextMap`` ships with ``str`` keys (JSON object keys are always strings), but
``TextMapTracker`` int-keys the map at load so lookups take a ``TextMapHash``
directly.
"""

ReadableFilename: TypeAlias = str
"""A readable file's name relative to ``Readable/<lang>/`` (e.g. ``Foo_EN.txt``).

``ReadablesTracker`` keys on this; distinct from the readable *stem* (no
``.txt``) and from a renderable's full ``Readable/<lang>/<name>.txt`` key.
"""


class NpcExcelConfigDataItem(TypedDict):
    """Type definition for individual NPC configuration entries."""

    id: NpcId
    nameTextMapHash: TextMapHash


NpcExcelConfigData: TypeAlias = list[NpcExcelConfigDataItem]
"""List of NPC configuration items from Excel data.

Example file: ExcelBinOutput/NpcExcelConfigData.json
"""


class AnimalCodexExcelConfigDataItem(TypedDict):
    """A living-beings archive entry (monster or wildlife).

    Example file: ExcelBinOutput/AnimalCodexExcelConfigData.json
    """

    id: AnimalCodexId
    type: str  # CODEX_MONSTER | CODEX_ANIMAL
    subType: str  # CODEX_SUBTYPE_*
    describeId: CreatureDescribeId
    descTextMapHash: TextMapHash
    sortOrder: int  # in-archive display order within the subType group
    isDisuse: bool


AnimalCodexExcelConfigData: TypeAlias = list[AnimalCodexExcelConfigDataItem]


class MonsterDescribeExcelConfigDataItem(TypedDict):
    """A monster's archive name/title metadata.

    Example file: ExcelBinOutput/MonsterDescribeExcelConfigData.json
    """

    id: CreatureDescribeId
    nameTextMapHash: TextMapHash
    titleID: MonsterTitleId
    specialNameLabID: MonsterSpecialNameLabId


MonsterDescribeExcelConfigData: TypeAlias = list[MonsterDescribeExcelConfigDataItem]


class MonsterTitleExcelConfigDataItem(TypedDict):
    """A monster title (e.g. ``火之咏者``) referenced by its describe entry.

    Example file: ExcelBinOutput/MonsterTitleExcelConfigData.json
    """

    titleID: MonsterTitleId
    titleNameTextMapHash: TextMapHash


MonsterTitleExcelConfigData: TypeAlias = list[MonsterTitleExcelConfigDataItem]


class MonsterSpecialNameExcelConfigDataItem(TypedDict):
    """A monster's special/instance name (e.g. ``风魔龙·特瓦林``).

    Example file: ExcelBinOutput/MonsterSpecialNameExcelConfigData.json
    """

    isInRandomList: bool
    specialNameID: MonsterSpecialNameId
    specialNameLabID: MonsterSpecialNameLabId
    specialNameTextMapHash: TextMapHash


MonsterSpecialNameExcelConfigData: TypeAlias = list[
    MonsterSpecialNameExcelConfigDataItem
]


class AnimalDescribeExcelConfigDataItem(TypedDict):
    """A wildlife animal's archive name metadata.

    Example file: ExcelBinOutput/AnimalDescribeExcelConfigData.json
    """

    id: CreatureDescribeId
    nameTextMapHash: TextMapHash


AnimalDescribeExcelConfigData: TypeAlias = list[AnimalDescribeExcelConfigDataItem]


class DialogTalkRole(TypedDict):
    """Type definition for talk role in dialog entries."""

    type: str
    id: str  # NPC id reference; ships as a str on disk, unlike the int NpcId master id


class DialogExcelConfigDataItem(TypedDict):
    """Type definition for individual dialog configuration entries."""

    id: DialogId  # de-obfuscated from the rotating dialog-id key
    talkRole: DialogTalkRole
    talkContentTextMapHash: TextMapHash
    talkRoleNameTextMapHash: TextMapHash


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
    titleTextMapHash: TextMapHash
    CUSTOM_addlLocalID: NotRequired[list[LocalizationId]]
    questContentLocalizedId: list[LocalizationId]
    questIDList: list[LocalizationId]


DocumentExcelConfigData: TypeAlias = list[DocumentExcelConfigDataItem]
"""List of document configuration items mapping materials to readable content.

Example file: ExcelBinOutput/DocumentExcelConfigData.json
"""


class MaterialExcelConfigDataItem(TypedDict):
    """Type definition for material configuration entries."""

    id: MaterialId
    nameTextMapHash: TextMapHash
    descTextMapHash: TextMapHash
    materialType: str
    setID: BookSuitId


MaterialExcelConfigData: TypeAlias = list[MaterialExcelConfigDataItem]
"""List of material configuration items.

Example file: ExcelBinOutput/MaterialExcelConfigData.json
"""


class BookSuitExcelConfigDataItem(TypedDict):
    """A book series (suit): its id and the hash of its localized series name."""

    id: BookSuitId
    suitNameTextMapHash: TextMapHash


BookSuitExcelConfigData: TypeAlias = list[BookSuitExcelConfigDataItem]
"""List of book series (suits).

Example file: ExcelBinOutput/BookSuitExcelConfigData.json
"""


class BooksCodexExcelConfigDataItem(TypedDict):
    """A book-archive codex entry tying a book material to its display order."""

    id: BooksCodexId
    materialId: MaterialId
    sortOrder: int
    isDisuse: bool


BooksCodexExcelConfigData: TypeAlias = list[BooksCodexExcelConfigDataItem]
"""List of book-archive codex entries.

Example file: ExcelBinOutput/BooksCodexExcelConfigData.json
"""


class TalkExcelConfigDataItem(TypedDict):
    """Type definition for talk configuration entries."""

    id: TalkId
    initDialog: DialogId


TalkExcelConfigData: TypeAlias = list[TalkExcelConfigDataItem]
"""List of talk configuration items.

Example file: ExcelBinOutput/TalkExcelConfigData.json
"""


class TalkRole(TypedDict):
    """Type definition for talk role."""

    type: str
    _id: NotRequired[str]  # NPC id reference; ships as a str on disk (see NpcId)
    id: NotRequired[str]  # NPC id reference; ships as a str on disk (see NpcId)


class TalkDialogItem(TypedDict):
    """Type definition for individual talk dialog entries."""

    id: DialogId
    talkRole: TalkRole
    talkContentTextMapHash: TextMapHash
    talkRoleNameTextMapHash: NotRequired[TextMapHash]
    nextDialogs: NotRequired[list[DialogId]]


class TalkData(TypedDict):
    """Talk data structure containing dialog list and metadata.

    Example file: BinOutput/Talk/Quest/7407811.json
    """

    talkId: TalkId
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

    id: TalkId
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
    descTextMapHash: TextMapHash
    finishCond: list[FinishCondItem]


class QuestData(TypedDict):
    """Quest data structure containing talks and metadata.

    Example file: BinOutput/Quest/74078.json
    """

    id: QuestId
    descTextMapHash: TextMapHash
    titleTextMapHash: TextMapHash
    chapterId: ChapterId  # 0 when the quest belongs to no chapter
    subQuests: list[SubQuestItem]
    talks: list[QuestTalkItem]


class AvatarExcelConfigDataItem(TypedDict):
    """Type definition for avatar configuration entries."""

    id: AvatarId
    nameTextMapHash: TextMapHash
    skillDepotId: SkillDepotId
    candSkillDepotIds: list[SkillDepotId]  # per-element depots for the Travelers


AvatarExcelConfigData: TypeAlias = list[AvatarExcelConfigDataItem]
"""List of avatar configuration items.

Example file: ExcelBinOutput/AvatarExcelConfigData.json
"""


class AvatarSkillDepotExcelConfigDataItem(TypedDict):
    """Type definition for avatar skill-depot entries."""

    id: SkillDepotId
    talents: list[TalentId]  # constellation talent ids (6 per element); 0 = empty slot
    energySkill: SkillId  # elemental burst skill (used to derive the depot's element)


AvatarSkillDepotExcelConfigData: TypeAlias = list[AvatarSkillDepotExcelConfigDataItem]
"""List of avatar skill-depot items.

Example file: ExcelBinOutput/AvatarSkillDepotExcelConfigData.json
"""


class AvatarTalentExcelConfigDataItem(TypedDict):
    """Type definition for constellation (talent) entries."""

    talentId: TalentId
    nameTextMapHash: TextMapHash
    descTextMapHash: TextMapHash


AvatarTalentExcelConfigData: TypeAlias = list[AvatarTalentExcelConfigDataItem]
"""List of constellation (talent) items.

Example file: ExcelBinOutput/AvatarTalentExcelConfigData.json
"""


class AvatarSkillExcelConfigDataItem(TypedDict):
    """Type definition for avatar skill entries (only fields we use)."""

    id: SkillId
    costElemType: str  # e.g. Fire / Water / Wind / Rock / Electric / Grass / Ice


AvatarSkillExcelConfigData: TypeAlias = list[AvatarSkillExcelConfigDataItem]
"""List of avatar skill items.

Example file: ExcelBinOutput/AvatarSkillExcelConfigData.json
"""


class FetterStoryExcelConfigDataItem(TypedDict):
    """Type definition for fetter story configuration entries."""

    avatarId: AvatarId
    storyTitleTextMapHash: TextMapHash
    storyContextTextMapHash: TextMapHash


FetterStoryExcelConfigData: TypeAlias = list[FetterStoryExcelConfigDataItem]


class FettersExcelConfigDataItem(TypedDict):
    avatarId: AvatarId
    voiceTitleTextMapHash: TextMapHash
    voiceFileTextTextMapHash: TextMapHash


FettersExcelConfigData: TypeAlias = list[FettersExcelConfigDataItem]


class MainQuestExcelConfigDataItem(TypedDict):
    id: QuestId
    type: str  # AQ / LQ / WQ / EQ / IQ
    titleTextMapHash: TextMapHash  # the quest (act) title
    chapterId: ChapterId  # 0 when the quest belongs to no chapter
    suggestTrackMainQuestList: list[QuestId]  # "next quest(s)" pointers


MainQuestExcelConfigData: TypeAlias = list[MainQuestExcelConfigDataItem]


class CoopInteractionExcelConfigDataItem(TypedDict):
    """A hangout (Coop) story's link to its owning quest (only fields we use)."""

    id: CoopStoryId
    mainQuestId: QuestId  # the hangout quest this story belongs to


CoopInteractionExcelConfigData: TypeAlias = list[CoopInteractionExcelConfigDataItem]
"""Example file: ExcelBinOutput/CoopInteractionExcelConfigData.json"""


class CoopChapterExcelConfigDataItem(TypedDict):
    """A hangout (Coop) chapter: one character's hangout act (only fields we use)."""

    id: ChapterId
    avatarId: AvatarId  # the chapter's primary character
    chapterNameTextMapHash: TextMapHash


CoopChapterExcelConfigData: TypeAlias = list[CoopChapterExcelConfigDataItem]
"""Example file: ExcelBinOutput/CoopChapterExcelConfigData.json"""


class ChapterExcelConfigDataItem(TypedDict):
    """Type definition for chapter configuration entries."""

    id: ChapterId
    chapterTitleTextMapHash: TextMapHash
    chapterNumTextMapHash: TextMapHash
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
    titleTextMapHash: TextMapHash
    descTextMapHash: TextMapHash
    isDisuse: bool
    isShow: str


AchievementExcelConfigData: TypeAlias = list[AchievementExcelConfigDataItem]


class AchievementGoalExcelConfigDataItem(TypedDict):
    """Type definition for an achievement section configuration entry."""

    id: AchievementGoalId
    orderId: int
    nameTextMapHash: TextMapHash


AchievementGoalExcelConfigData: TypeAlias = list[AchievementGoalExcelConfigDataItem]


class ReliquarySetExcelConfigDataItem(TypedDict):
    """Type definition for artifact set configuration entries."""

    setId: ArtifactSetId
    containsList: list[ReliquaryId]
    equipAffixId: EquipAffixId


class ReliquaryExcelConfigDataItem(TypedDict):
    """Type definition for individual artifact configuration entries."""

    id: ReliquaryId
    nameTextMapHash: TextMapHash
    descTextMapHash: TextMapHash
    storyId: StoryId


class EquipAffixExcelConfigDataItem(TypedDict):
    """Type definition for equipment affix (artifact set bonus) entries."""

    id: EquipAffixId
    nameTextMapHash: TextMapHash


class WeaponExcelConfigDataItem(TypedDict):
    """Type definition for weapon configuration entries.

    ``storyId`` points at the weapon's DocumentExcelConfigData entry (0 when the
    weapon has no story document).
    """

    id: WeaponId
    nameTextMapHash: TextMapHash
    descTextMapHash: TextMapHash
    storyId: DocumentId


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
class BookVolumeInfo:
    """A single volume's title and cleaned body within a book series."""

    title: str
    content: str


@attrs.define
class BookSeriesInfo:
    """A multi-volume book series with its volumes in reading order."""

    suit_id: BookSuitId
    series_name: str
    volumes: list[BookVolumeInfo]


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

    coop_story_id: CoopStoryId
    steps: list[CoopStep]


@attrs.define
class HangoutInfo:
    """A hangout quest: its primary character and play-ordered story branches."""

    quest_id: QuestId
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
    avatar_id: AvatarId
    constellations: list[Constellation]


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
class CreatureInfo:
    """A single living-beings archive entry: names and archive description.

    ``special_name``/``title`` are populated for monsters when they differ from
    ``name`` (wildlife carry only ``name``).
    """

    codex_id: AnimalCodexId
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
    avatar_id: AvatarId


@attrs.define
class TrackerStats:
    """Statistics for text map, talk ID, and readable access tracking."""

    accessed_text_map_ids: set[TextMapHash]
    accessed_talk_ids: set[TalkId]
    accessed_readable_filenames: set[ReadableFilename]

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
