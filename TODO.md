# TODO

Follow-up work, grouped by area. Keep bullets brief but with enough context (and quest/talk IDs) to act on later. See `AGENTS.md` > Task Tracking for conventions.

## Text / Quest dialogue extraction

- **Subset/superset talkId collisions are dropped, deleting quests/groups.** `talk_parsing._resolve_talk_candidates` drops a colliding talkId as "ambiguous" whenever the text-bearing candidates aren't byte-identical — including when one candidate's content is a strict *superset* of the other(s) (a stub-vs-full pair). This discards real, reachable content and, via strict quest/group parsing, deletes whole quests/groups. Confirmed cases (all Quest↔Npc; FreeGroup already excluded): `7508751` (Npc 4 lines ⊂ Quest 10 → deletes quest `75079`), `7405102` (Quest 11 ⊂ Npc 21 → deletes `13489_NpcGroup`), `7409902` (Quest 12 ⊂ Npc 21 → deletes `21191_NpcGroup`). ~6 config-backed subset cases total (more were FreeGroup, now excluded).

- **Attach "free talk" orphans (and the whole excluded `FreeGroup` dir) to their quests.** `Talk/FreeGroup/` is now excluded wholesale in `talk_parsing._EXCLUDE_DIRECTORIES`: these are Lua-invoked free talks that reuse other talks' ids with no quest linkage in the dumped data (no `TalkExcelConfigData` entry beyond the shared id, no group/`nextTalks`/`nextDialogs`/InterAction reference; dialogs appear nowhere else, e.g. `FreeGroup/7407804.json` dialogs `740789911/740789912`). Excluding them costs almost nothing reachable today (only 3 FreeGroup-only ids are in the config: `7319311`, `7414802`, `4002801` — 7 lines total), BUT also defers ~1,800 cases where the FreeGroup file is the *fuller* version of a quest talk whose `Talk/Quest/` copy is a stub (e.g. `402217`: Quest 1-line stub vs FreeGroup 36-line 审判日 investigation; the quest now renders the stub). Investigate attaching FreeGroup talks to their owning quest — infer ownership from the shared `talkId`/numbering prefix or `performCfg`/`QuestDialogue/.../<questId>/` path — and prefer the fuller version when it supersedes a stub. Re-including the dir without this would reintroduce ~1,800 ambiguous collisions.

- **Extract Coop (hangout) talks.** Coop talk files are named `<coopStoryId>_<localTalkId>.json` (e.g. `Talk/Coop/1900102_10.json`), where the `talkId` is only a per-story local id reused across many unrelated hangout conversations (~282 bare ids like `10`/`100`/`101` collide across stories). None are in `TalkExcelConfigData`, so they are unreachable via the by-talkId mapping and the standalone `Talks` renderable, and they're not referenced by any talk group — so hangout-event dialogue is currently not in the corpus at all. Investigate a Coop-specific extraction keyed by the unique `<coopStoryId>_<localTalkId>` (likely a new renderable that walks the Coop story files directly), rather than the global `talkId`. The collision-resolution `logger.debug` for these (no-initDialog, conflicting content) is where they surface today.

- **Why some subId talks are absent from the quest `talks[]` array (investigated).**
  `talks[]` is NOT a superset of subId-reached talks: subId reaches ~1,659 talk files that `talks[]` omits (across 805 quests), overwhelmingly `Npc/` talks (1,427) plus `Activity`/`Gadget`/`FreeGroup`. By completion-condition type, these subId-only talks are mostly `QUEST_CONTENT_COMPLETE_TALK` (1,100), then `FINISH_PLOT` (150), `LUA_NOTIFY` (128), `(none)` (46). Confirmed real dialogue (294/300 sampled carry text; e.g. `Activity/4006411` is a Kazuha/Xinyan scene). Takeaway: `talks[]` and subId/`COMPLETE_TALK` are complementary — extraction must union both. Examples of subId-only quests: `72234`, `70823`, `73219`.

## Frontend

- **Add a filter/search box to the quest hierarchy view.** The old flat `agd_quest` list (`LibraryFilesPage`) had a client-side title filter; the new hierarchical `QuestHierarchyPage` dropped it. Add back a client-side search box that filters across the tree (e.g. match quest/series/chapter titles and surface matching quests regardless of their current drill-down position), so users can find a quest without manually drilling through type → series → chapter.

## Tech Debt

- **Collect & report non-fatal parsing issues in aggregate.** Per-item parsing should stay strict for unexpected data, but some conditions are non-fatal data gaps we currently handle inline (e.g. a `COMPLETE_TALK`/`COMPLETE_ANY_TALK` param pointing at an absent talk → `[Missing Talk]` placeholder in `processing._resolve_authoritative_talk`; ~66 quests / 65 distinct dangling talk ids). Add a mechanism for each item parse to record such non-fatal issues (issue type, item id, detail) into a shared collector instead of only emitting a placeholder, then report the aggregated stats at the end of a `generate-all` run so gaps are visible/trackable rather than buried in output.

- **Genuinely-missing talk data (31 IDs, 9 quests).** A handful of real talks in `TalkExcelConfigData` have no data file — these are the only true gaps. Most trace to `talk_parsing._BAD_TALK_PATHS` (blocklisted bad files: `GlobalDialog.json`, `80045/80046.json`, `7401203-5.json`, etc.). IDs: `1180101, 7320408, 7323513-7323516, 7323520, 7323550, 7325602, 7325605, 7325608, 7325613-7325614, 7325618-7325619, 7325621, 7325625, 7328510, 7332901, 7332910, 7333001-7333013, 7418502, 7900501`. Decide whether to source these elsewhere or accept as upstream gaps.

- **Talk groups silently dropped on missing talk.** `get_talk_group_info` raises `RuntimeError` if any referenced talk fails to load (`processing.py`); in non-strict mode the whole `agd_talk_group` file is then skipped (no output, no placeholder). Consider degrading gracefully (skip the missing entry) instead of dropping the entire group.

## Testing

- **Better integration test coverage**, including a simple MCP server test case. (migrated from beads `istaroth-div`)
