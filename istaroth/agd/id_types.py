"""AGD id ``TypeAlias`` definitions.

Documentation-only aliases (transparent to mypy) that name the many distinct
kinds of AGD id, so a signature says *which* id it carries instead of a bare
``int``. Each alias is the id's on-disk JSON wire type -- every AGD id ships as
``int`` -- and the pipeline carries it as ``int`` end-to-end. ``str`` appears
only at genuine boundaries: output filenames, ``TextMap`` lookups, and the few
spots that compare an id to a file-path stem.
"""

from typing import TypeAlias

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

CutsceneId: TypeAlias = int
"""Cutscene id (a ``BinOutput/Cutscene/<id>.json`` file stem). The id encodes the
cutscene's trigger site in one of several historical shapes -- a sub-quest id, a
dialog-style ``talkId*100+n``, or a ``mainQuestId``-prefixed number -- which the
subtitle renderable decodes to name the owning quest."""

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

Dialog/talk role *references* (``talkRole.id`` / ``_id``) ship as plain ``str``
on the wire (sometimes non-numeric placeholders) and are parsed to this alias
at the lookup boundary.
"""

ActivityId: TypeAlias = int
"""Activity id (``ActivityGroup.activityId``); groups an activity's talk files.

Overlaps the ``NpcId`` range (e.g. ``2001`` is both an activity and an NPC), so
an ActivityGroup rendered file derives its manifest id via
``talk_parsing.activity_group_metadata_id`` rather than using this id raw."""

AnecdoteId: TypeAlias = int
"""Anecdote (Odd Encounter, 奇遇) id (``AnecdoteExcelConfigDataItem.id``); one
world vignette grouping the ``TALK_STORYBOARD`` talks of its quest."""

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

``ReadablesTracker`` keys on this, and it also doubles as the readable
renderable key; distinct from the readable *stem* (no ``.txt``).
"""
