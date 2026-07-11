"""Raw AnimeGameData (AGD) wire types.

TypedDicts matching the structure of AGD JSON files, plus the ``TextMap`` alias.
Field annotations reference id aliases from :mod:`istaroth.agd.id_types`.
"""

from __future__ import annotations

from typing import NotRequired, TypeAlias, TypedDict

import msgspec

from istaroth.agd import deobfuscation, id_types

TextMap: TypeAlias = dict[str, str]
"""Dictionary mapping string IDs to localized text content.

Example file: TextMap/TextMapCHS.json
"""


class NpcExcelConfigDataItem(TypedDict):
    """Type definition for individual NPC configuration entries."""

    id: id_types.NpcId
    nameTextMapHash: id_types.TextMapHash


NpcExcelConfigData: TypeAlias = list[NpcExcelConfigDataItem]
"""List of NPC configuration items from Excel data.

Example file: ExcelBinOutput/NpcExcelConfigData.json
"""


class AnimalCodexExcelConfigDataItem(TypedDict):
    """A living-beings archive entry (monster or wildlife).

    Example file: ExcelBinOutput/AnimalCodexExcelConfigData.json
    """

    id: id_types.AnimalCodexId
    type: str  # CODEX_MONSTER | CODEX_ANIMAL
    subType: str  # CODEX_SUBTYPE_*
    describeId: id_types.CreatureDescribeId
    descTextMapHash: id_types.TextMapHash
    sortOrder: int  # in-archive display order within the subType group
    isDisuse: bool


AnimalCodexExcelConfigData: TypeAlias = list[AnimalCodexExcelConfigDataItem]


class MonsterDescribeExcelConfigDataItem(TypedDict):
    """A monster's archive name/title metadata.

    Example file: ExcelBinOutput/MonsterDescribeExcelConfigData.json
    """

    id: id_types.CreatureDescribeId
    nameTextMapHash: id_types.TextMapHash
    titleID: id_types.MonsterTitleId
    specialNameLabID: id_types.MonsterSpecialNameLabId


MonsterDescribeExcelConfigData: TypeAlias = list[MonsterDescribeExcelConfigDataItem]


class MonsterTitleExcelConfigDataItem(TypedDict):
    """A monster title (e.g. ``火之咏者``) referenced by its describe entry.

    Example file: ExcelBinOutput/MonsterTitleExcelConfigData.json
    """

    titleID: id_types.MonsterTitleId
    titleNameTextMapHash: id_types.TextMapHash


MonsterTitleExcelConfigData: TypeAlias = list[MonsterTitleExcelConfigDataItem]


class MonsterSpecialNameExcelConfigDataItem(TypedDict):
    """A monster's special/instance name (e.g. ``风魔龙·特瓦林``).

    Example file: ExcelBinOutput/MonsterSpecialNameExcelConfigData.json
    """

    isInRandomList: bool
    specialNameID: id_types.MonsterSpecialNameId
    specialNameLabID: id_types.MonsterSpecialNameLabId
    specialNameTextMapHash: id_types.TextMapHash


MonsterSpecialNameExcelConfigData: TypeAlias = list[
    MonsterSpecialNameExcelConfigDataItem
]


class AnimalDescribeExcelConfigDataItem(TypedDict):
    """A wildlife animal's archive name metadata.

    Example file: ExcelBinOutput/AnimalDescribeExcelConfigData.json
    """

    id: id_types.CreatureDescribeId
    nameTextMapHash: id_types.TextMapHash


AnimalDescribeExcelConfigData: TypeAlias = list[AnimalDescribeExcelConfigDataItem]


class DialogExcelConfigDataItem(
    msgspec.Struct, rename={"id": deobfuscation.DIALOG_EXCEL_ID_KEY}
):
    """Individual dialog configuration entry, partially decoded.

    Only the consumed fields; decoding into this Struct skips the rest of the
    ~90MB file, ~10x faster than a full decode + deobfuscation pass.
    """

    id: id_types.DialogId  # de-obfuscated from the rotating dialog-id key
    talkContentTextMapHash: id_types.TextMapHash
    talkRoleNameTextMapHash: id_types.TextMapHash


DialogExcelConfigData: TypeAlias = list[DialogExcelConfigDataItem]
"""List of dialog configuration items from Excel data.

Example file: ExcelBinOutput/DialogExcelConfigData.json
"""


class LocalizationExcelConfigDataItem(TypedDict):
    """Type definition for localization configuration entries."""

    id: id_types.LocalizationId
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

    id: id_types.DocumentId
    titleTextMapHash: id_types.TextMapHash
    CUSTOM_addlLocalID: NotRequired[list[id_types.LocalizationId]]
    questContentLocalizedId: list[id_types.LocalizationId]
    questIDList: list[id_types.LocalizationId]


DocumentExcelConfigData: TypeAlias = list[DocumentExcelConfigDataItem]
"""List of document configuration items mapping materials to readable content.

Example file: ExcelBinOutput/DocumentExcelConfigData.json
"""


class MaterialExcelConfigDataItem(TypedDict):
    """Type definition for material configuration entries."""

    id: id_types.MaterialId
    nameTextMapHash: id_types.TextMapHash
    descTextMapHash: id_types.TextMapHash
    materialType: str
    setID: id_types.BookSuitId


MaterialExcelConfigData: TypeAlias = list[MaterialExcelConfigDataItem]
"""List of material configuration items.

Example file: ExcelBinOutput/MaterialExcelConfigData.json
"""


class BookSuitExcelConfigDataItem(TypedDict):
    """A book series (suit): its id and the hash of its localized series name."""

    id: id_types.BookSuitId
    suitNameTextMapHash: id_types.TextMapHash


BookSuitExcelConfigData: TypeAlias = list[BookSuitExcelConfigDataItem]
"""List of book series (suits).

Example file: ExcelBinOutput/BookSuitExcelConfigData.json
"""


class BooksCodexExcelConfigDataItem(TypedDict):
    """A book-archive codex entry tying a book material to its display order."""

    id: id_types.BooksCodexId
    materialId: id_types.MaterialId
    sortOrder: int
    isDisuse: bool


BooksCodexExcelConfigData: TypeAlias = list[BooksCodexExcelConfigDataItem]
"""List of book-archive codex entries.

Example file: ExcelBinOutput/BooksCodexExcelConfigData.json
"""


class TalkExcelConfigDataItem(TypedDict):
    """Type definition for talk configuration entries."""

    id: id_types.TalkId
    initDialog: id_types.DialogId
    loadType: str
    questId: id_types.QuestId  # 0 when the talk belongs to no quest


TalkExcelConfigData: TypeAlias = list[TalkExcelConfigDataItem]
"""List of talk configuration items.

Example file: ExcelBinOutput/TalkExcelConfigData.json
"""


class AnecdoteExcelConfigDataItem(TypedDict):
    """An anecdote (Odd Encounter, 奇遇) world-vignette entry.

    Field names are invented, not lineage-recovered (see
    ``deobfuscation._ANECDOTE_FIELD_MAPPINGS``). ``questIds`` holds the
    anecdote's quest, whose id the quest's ``TALK_STORYBOARD`` talks carry as
    their ``questId``; every current entry has exactly one.
    """

    id: id_types.AnecdoteId
    questIds: list[id_types.QuestId]
    titleTextMapHash: id_types.TextMapHash
    teaserTextMapHash: id_types.TextMapHash
    descTextMapHash: id_types.TextMapHash
    isHide: bool


AnecdoteExcelConfigData: TypeAlias = list[AnecdoteExcelConfigDataItem]
"""List of anecdote entries.

Example file: ExcelBinOutput/AnecdoteExcelConfigData.json
"""


class BlossomTalkExcelConfigDataItem(TypedDict):
    """A blossom talk-pool entry: the NPC talks that point at one world spot's
    blossom refresh event. Currently only Rich Ore Reserve (矿物富集点)
    refreshes have talk entries. Ships cleartext."""

    refreshId: id_types.BlossomRefreshId
    talkId: list[id_types.TalkId]


BlossomTalkExcelConfigData: TypeAlias = list[BlossomTalkExcelConfigDataItem]
"""List of blossom talk-pool entries.

Example file: ExcelBinOutput/BlossomTalkExcelConfigData.json
"""


class BlossomRefreshExcelConfigDataItem(TypedDict):
    """A blossom world-event refresh pool (the fields used here ship cleartext)."""

    id: id_types.BlossomRefreshId
    cityId: id_types.CityId
    clientShowType: str
    nameTextMapHash: id_types.TextMapHash
    descTextMapHash: id_types.TextMapHash


BlossomRefreshExcelConfigData: TypeAlias = list[BlossomRefreshExcelConfigDataItem]
"""List of blossom refresh pools.

Example file: ExcelBinOutput/BlossomRefreshExcelConfigData.json
"""


class CityConfigDataItem(TypedDict):
    """A city (region) entry (the fields used here ship cleartext)."""

    cityId: id_types.CityId
    cityNameTextMapHash: id_types.TextMapHash


CityConfigData: TypeAlias = list[CityConfigDataItem]
"""List of city entries.

Example file: ExcelBinOutput/CityConfigData.json
"""


class TalkRole(TypedDict):
    """Type definition for talk role."""

    type: str
    _id: NotRequired[str]  # NPC id reference; ships as a str on disk (see NpcId)
    id: NotRequired[str]  # NPC id reference; ships as a str on disk (see NpcId)


class TalkDialogItem(TypedDict):
    """Type definition for individual talk dialog entries."""

    id: id_types.DialogId
    talkRole: TalkRole
    talkContentTextMapHash: id_types.TextMapHash
    talkRoleNameTextMapHash: NotRequired[id_types.TextMapHash]
    nextDialogs: NotRequired[list[id_types.DialogId]]


class TalkData(TypedDict):
    """Talk data structure containing dialog list and metadata.

    Example file: BinOutput/Talk/Quest/7407811.json
    """

    talkId: id_types.TalkId
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

    id: id_types.TalkId
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

    subId: id_types.SubQuestId
    order: int
    descTextMapHash: id_types.TextMapHash
    finishCond: list[FinishCondItem]


class QuestData(TypedDict):
    """Quest data structure containing talks and metadata.

    Example file: BinOutput/Quest/74078.json
    """

    id: id_types.QuestId
    descTextMapHash: id_types.TextMapHash
    titleTextMapHash: id_types.TextMapHash
    chapterId: id_types.ChapterId  # 0 when the quest belongs to no chapter
    subQuests: list[SubQuestItem]
    talks: list[QuestTalkItem]


class QuestExcelConfigDataItem(TypedDict):
    """A sub-quest master-table row (only fields we use).

    Example file: ExcelBinOutput/QuestExcelConfigData.json
    """

    subId: id_types.SubQuestId
    mainId: id_types.QuestId


QuestExcelConfigData: TypeAlias = list[QuestExcelConfigDataItem]


class CutsceneVideoConfig(TypedDict):
    """A pre-rendered video cutscene's video/subtitle binding (only fields we use).

    The ``videoConfig`` block of a ``BinOutput/Cutscene/<id>.json`` variant entry
    (example file: BinOutput/Cutscene/1204205.json). Video names are empty
    strings (not absent) when a cutscene has no traveler-variant video.
    """

    videoName: str  # e.g. "Cs_..._Boy.usm"
    videoNameOther: str  # the other traveler variant
    subtitleId: NotRequired[id_types.LocalizationId]
    subtitleIdOther: NotRequired[id_types.LocalizationId]


class AvatarExcelConfigDataItem(TypedDict):
    """Type definition for avatar configuration entries."""

    id: id_types.AvatarId
    nameTextMapHash: id_types.TextMapHash
    skillDepotId: id_types.SkillDepotId
    candSkillDepotIds: list[
        id_types.SkillDepotId
    ]  # per-element depots for the Travelers


AvatarExcelConfigData: TypeAlias = list[AvatarExcelConfigDataItem]
"""List of avatar configuration items.

Example file: ExcelBinOutput/AvatarExcelConfigData.json
"""


class AvatarSkillDepotExcelConfigDataItem(TypedDict):
    """Type definition for avatar skill-depot entries."""

    id: id_types.SkillDepotId
    talents: list[
        id_types.TalentId
    ]  # constellation talent ids (6 per element); 0 = empty slot
    energySkill: (
        id_types.SkillId
    )  # elemental burst skill (used to derive the depot's element)


AvatarSkillDepotExcelConfigData: TypeAlias = list[AvatarSkillDepotExcelConfigDataItem]
"""List of avatar skill-depot items.

Example file: ExcelBinOutput/AvatarSkillDepotExcelConfigData.json
"""


class AvatarTalentExcelConfigDataItem(TypedDict):
    """Type definition for constellation (talent) entries."""

    talentId: id_types.TalentId
    nameTextMapHash: id_types.TextMapHash
    descTextMapHash: id_types.TextMapHash


AvatarTalentExcelConfigData: TypeAlias = list[AvatarTalentExcelConfigDataItem]
"""List of constellation (talent) items.

Example file: ExcelBinOutput/AvatarTalentExcelConfigData.json
"""


class AvatarSkillExcelConfigDataItem(TypedDict):
    """Type definition for avatar skill entries (only fields we use)."""

    id: id_types.SkillId
    costElemType: str  # e.g. Fire / Water / Wind / Rock / Electric / Grass / Ice


AvatarSkillExcelConfigData: TypeAlias = list[AvatarSkillExcelConfigDataItem]
"""List of avatar skill items.

Example file: ExcelBinOutput/AvatarSkillExcelConfigData.json
"""


class FetterStoryExcelConfigDataItem(TypedDict):
    """Type definition for fetter story configuration entries."""

    avatarId: id_types.AvatarId
    storyTitleTextMapHash: id_types.TextMapHash
    storyContextTextMapHash: id_types.TextMapHash


FetterStoryExcelConfigData: TypeAlias = list[FetterStoryExcelConfigDataItem]


class FettersExcelConfigDataItem(TypedDict):
    avatarId: id_types.AvatarId
    voiceTitleTextMapHash: id_types.TextMapHash
    voiceFileTextTextMapHash: id_types.TextMapHash


FettersExcelConfigData: TypeAlias = list[FettersExcelConfigDataItem]


class MainQuestExcelConfigDataItem(TypedDict):
    id: id_types.QuestId
    type: str  # AQ / LQ / WQ / EQ / IQ
    titleTextMapHash: id_types.TextMapHash  # the quest (act) title
    chapterId: id_types.ChapterId  # 0 when the quest belongs to no chapter
    suggestTrackMainQuestList: list[id_types.QuestId]  # "next quest(s)" pointers


MainQuestExcelConfigData: TypeAlias = list[MainQuestExcelConfigDataItem]


class CoopInteractionExcelConfigDataItem(TypedDict):
    """A hangout (Coop) story's link to its owning quest (only fields we use)."""

    id: id_types.CoopStoryId
    mainQuestId: id_types.QuestId  # the hangout quest this story belongs to


CoopInteractionExcelConfigData: TypeAlias = list[CoopInteractionExcelConfigDataItem]
"""Example file: ExcelBinOutput/CoopInteractionExcelConfigData.json"""


class CoopChapterExcelConfigDataItem(TypedDict):
    """A hangout (Coop) chapter: one character's hangout act (only fields we use)."""

    id: id_types.ChapterId
    avatarId: id_types.AvatarId  # the chapter's primary character
    chapterNameTextMapHash: id_types.TextMapHash


CoopChapterExcelConfigData: TypeAlias = list[CoopChapterExcelConfigDataItem]
"""Example file: ExcelBinOutput/CoopChapterExcelConfigData.json"""


class ChapterExcelConfigDataItem(TypedDict):
    """Type definition for chapter configuration entries."""

    id: id_types.ChapterId
    chapterTitleTextMapHash: id_types.TextMapHash
    chapterNumTextMapHash: id_types.TextMapHash
    groupId: (
        id_types.QuestSeriesId
    )  # series: groups the acts of one questline; 0 when none
    beginQuestId: (
        int  # first subquest id; // 100 is its (int) main quest id (0 if none)
    )


ChapterExcelConfigData: TypeAlias = list[ChapterExcelConfigDataItem]


class AchievementExcelConfigDataItem(TypedDict):
    """Type definition for an achievement configuration entry."""

    id: id_types.AchievementId
    goalId: id_types.AchievementGoalId
    orderId: int
    titleTextMapHash: id_types.TextMapHash
    descTextMapHash: id_types.TextMapHash
    isDisuse: bool
    isShow: str


AchievementExcelConfigData: TypeAlias = list[AchievementExcelConfigDataItem]


class AchievementGoalExcelConfigDataItem(TypedDict):
    """Type definition for an achievement section configuration entry."""

    id: id_types.AchievementGoalId
    orderId: int
    nameTextMapHash: id_types.TextMapHash


AchievementGoalExcelConfigData: TypeAlias = list[AchievementGoalExcelConfigDataItem]


class NewActivityExcelConfigDataItem(TypedDict):
    """An activity/event entry (only fields we use).

    Example file: ExcelBinOutput/NewActivityExcelConfigData.json
    """

    activityId: id_types.ActivityId
    nameTextMapHash: id_types.TextMapHash


NewActivityExcelConfigData: TypeAlias = list[NewActivityExcelConfigDataItem]


class HomeWorldNPCExcelConfigDataItem(TypedDict):
    """A Serenitea Pot companion entry (only fields we use).

    ``npcID`` is the companion's dedicated NPC variant whose NpcGroup talks are
    the Serenitea Pot dialogue.
    """

    npcID: id_types.NpcId


HomeWorldNPCExcelConfigData: TypeAlias = list[HomeWorldNPCExcelConfigDataItem]


class RoleCombatTarotAvatarExcelConfigDataItem(TypedDict):
    """An Imaginarium Theater cast entry (only fields we use).

    ``npcId`` is the avatar's dedicated theater NPC variant.
    """

    npcId: id_types.NpcId


RoleCombatTarotAvatarExcelConfigData: TypeAlias = list[
    RoleCombatTarotAvatarExcelConfigDataItem
]


class GCGWeekLevelExcelConfigDataItem(TypedDict):
    """A Genius Invokation TCG week-level opponent entry (only fields we use).

    ``npcId`` is the opponent's dedicated TCG NPC variant.
    """

    npcId: id_types.NpcId


GCGWeekLevelExcelConfigData: TypeAlias = list[GCGWeekLevelExcelConfigDataItem]


class ReliquarySetExcelConfigDataItem(TypedDict):
    """Type definition for artifact set configuration entries."""

    setId: id_types.ArtifactSetId
    containsList: list[id_types.ReliquaryId]
    equipAffixId: id_types.EquipAffixId


class ReliquaryExcelConfigDataItem(TypedDict):
    """Type definition for individual artifact configuration entries."""

    id: id_types.ReliquaryId
    nameTextMapHash: id_types.TextMapHash
    descTextMapHash: id_types.TextMapHash
    storyId: id_types.StoryId


class EquipAffixExcelConfigDataItem(TypedDict):
    """Type definition for equipment affix (artifact set bonus) entries."""

    id: id_types.EquipAffixId
    nameTextMapHash: id_types.TextMapHash


class WeaponExcelConfigDataItem(TypedDict):
    """Type definition for weapon configuration entries.

    ``storyId`` points at the weapon's DocumentExcelConfigData entry (0 when the
    weapon has no story document).
    """

    id: id_types.WeaponId
    nameTextMapHash: id_types.TextMapHash
    descTextMapHash: id_types.TextMapHash
    storyId: id_types.DocumentId


ReliquarySetExcelConfigData: TypeAlias = list[ReliquarySetExcelConfigDataItem]
ReliquaryExcelConfigData: TypeAlias = list[ReliquaryExcelConfigDataItem]
EquipAffixExcelConfigData: TypeAlias = list[EquipAffixExcelConfigDataItem]
WeaponExcelConfigData: TypeAlias = list[WeaponExcelConfigDataItem]
