# TODO

Follow-up work, grouped by area. Keep bullets brief but with enough context (and quest/talk IDs) to act on later. See `AGENTS.md` > Task Tracking for conventions.

## Text / Quest dialogue extraction

- **Use the `COMPLETE_TALK` condition param as the authoritative talk pointer in quests.**
  `get_quest_info` (`istaroth/agd/processing.py`) currently probes every subQuest `subId` as if it were a talk file ID. The game actually names the talk inside each subQuest's `QUEST_CONTENT_COMPLETE_TALK` finish condition (first param). Of 15,161 `COMPLETE_TALK` conditions, 15,029 resolve to a real talk file; only **7,458 have param == subId** — the rest point elsewhere, so subId-probing misses them. Parsing the param resolves to 13,928 distinct talk files, incl. **178 NEW talks reached by neither `subId` nor the quest `talks[]` array**. Example: quest `73130` subId `7313003` → talk param `7313001` → `BinOutput/Talk/FreeGroup/7313001.json`; quest `73130` subId `7313005` → param `7313003`. Switching to param-based extraction would (a) recover those 178+ talks and (b) let us drop the blind subId probe that generates the ~10k false-positive `[Missing Talk]` placeholders.

- **Investigate talks appearing in incorrect quest order.** Some quests render dialogue out of narrative sequence — e.g. https://istaroth.me/library/agd_quest/74078. Likely tied to how subQuest `order` and the non-subquest `talks[]` pass interleave (subQuest talks are sorted by `order`, but the non-subquest "Additional Conversations" are appended separately with no ordering relative to them). Determine the correct ordering signal and fix the render sequence.

- **Why some subId talks are absent from the quest `talks[]` array (investigated).**
  `talks[]` is NOT a superset of subId-reached talks: subId reaches ~1,659 talk files that `talks[]` omits (across 805 quests), overwhelmingly `Npc/` talks (1,427) plus `Activity`/`Gadget`/`FreeGroup`. By completion-condition type, these subId-only talks are mostly `QUEST_CONTENT_COMPLETE_TALK` (1,100), then `FINISH_PLOT` (150), `LUA_NOTIFY` (128), `(none)` (46). Confirmed real dialogue (294/300 sampled carry text; e.g. `Activity/4006411` is a Kazuha/Xinyan scene). Takeaway: `talks[]` and subId/`COMPLETE_TALK` are complementary — extraction must union both. Examples of subId-only quests: `72234`, `70823`, `73219`.

## Features

- **Quest hierarchy navigation.** Let users browse quests by their hierarchy (quest series/chapters → quests → talks) instead of the current flat `agd_quest` list. Surface the chapter/series grouping already present in the data (`chapterId`, `chapterTitle`) so related quests link together in the library UI.

## Tech Debt

- **Genuinely-missing talk data (31 IDs, 9 quests).** A handful of real talks in `TalkExcelConfigData` have no data file — these are the only true gaps. Most trace to `talk_parsing._BAD_TALK_PATHS` (blocklisted bad files: `GlobalDialog.json`, `80045/80046.json`, `7401203-5.json`, etc.). IDs: `1180101, 7320408, 7323513-7323516, 7323520, 7323550, 7325602, 7325605, 7325608, 7325613-7325614, 7325618-7325619, 7325621, 7325625, 7328510, 7332901, 7332910, 7333001-7333013, 7418502, 7900501`. Decide whether to source these elsewhere or accept as upstream gaps.

- **Talk groups silently dropped on missing talk.** `get_talk_group_info` raises `RuntimeError` if any referenced talk fails to load (`processing.py`); in non-strict mode the whole `agd_talk_group` file is then skipped (no output, no placeholder). Consider degrading gracefully (skip the missing entry) instead of dropping the entire group.

## Testing

- **Better integration test coverage**, including a simple MCP server test case. (migrated from beads `istaroth-div`)
