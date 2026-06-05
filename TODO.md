# TODO

Follow-up work, grouped by area. Keep bullets brief but with enough context (and quest/talk IDs) to act on later. See `AGENTS.md` > Task Tracking for conventions.

## Text / Quest dialogue extraction

- **Out-of-place trailing talks in quest `74078` ("溪舟的尾波").** After the earliest-reference ordering fix, three talks still land at the very end (orders 100/103/105) but read as mid-quest content: order 100 = talk `7407812` ("卡特皮拉: 行，我也送你们一程吧。"), order 103 = talk `7407801` ("派蒙: 纳齐森科鲁兹，你从哪里看来的这些东西？"), order 105 = talk `7407802` ("纳齐森科鲁兹: 「伊啊，伊啊，潘…」"). Suspicious signal: talks `7407801`/`7407802` carry the LOWEST subId increments (likely authored early) yet their only finishCond reference is a high-`order` `COMPLETE_TALK` (subIds `7407803`/`7407805`), so they get gated to the end. Investigate whether their true play point is earlier and only encoded outside `finishCond` (talk-internal condition or a branch), and whether subId-increment order should be a tiebreaker/fallback ordering signal when finishCond placement looks late. Note: the authoritative flow lives in the quest's Lua scripts, which are NOT dumped in AGD (see the DAG investigation in commit history), so this likely can't be fully resolved from data alone.

- **Describe non-talk subQuest objective steps.** `get_quest_info` / `_iter_subquest_talk_ids` (`istaroth/agd/processing.py`) now place talks via the finish-condition param for the three talk-bearing condition types (`QUEST_CONTENT_COMPLETE_TALK`, `QUEST_CONTENT_COMPLETE_ANY_TALK`, `QUEST_CONTENT_FINISH_PLOT`), ordered by the earliest referencing subQuest `order`. All other `QUEST_CONTENT_*` types are dropped. Add handling that renders a brief description of their finishing objective (e.g. "defeat N monsters", "reach location", "give item", time/gadget conditions) inline at the step's `order`, so quest text conveys non-dialogue progression. The `match` in `_iter_subquest_talk_ids` is the place to branch; see the per-type counts gathered during the COMPLETE_TALK investigation for the full type list and frequencies.

- **Why some subId talks are absent from the quest `talks[]` array (investigated).**
  `talks[]` is NOT a superset of subId-reached talks: subId reaches ~1,659 talk files that `talks[]` omits (across 805 quests), overwhelmingly `Npc/` talks (1,427) plus `Activity`/`Gadget`/`FreeGroup`. By completion-condition type, these subId-only talks are mostly `QUEST_CONTENT_COMPLETE_TALK` (1,100), then `FINISH_PLOT` (150), `LUA_NOTIFY` (128), `(none)` (46). Confirmed real dialogue (294/300 sampled carry text; e.g. `Activity/4006411` is a Kazuha/Xinyan scene). Takeaway: `talks[]` and subId/`COMPLETE_TALK` are complementary — extraction must union both. Examples of subId-only quests: `72234`, `70823`, `73219`.

## Tech Debt

- **Collect & report non-fatal parsing issues in aggregate.** Per-item parsing should stay strict for unexpected data, but some conditions are non-fatal data gaps we currently handle inline (e.g. a `COMPLETE_TALK`/`COMPLETE_ANY_TALK` param pointing at an absent talk → `[Missing Talk]` placeholder in `processing._resolve_authoritative_talk`; ~66 quests / 65 distinct dangling talk ids). Add a mechanism for each item parse to record such non-fatal issues (issue type, item id, detail) into a shared collector instead of only emitting a placeholder, then report the aggregated stats at the end of a `generate-all` run so gaps are visible/trackable rather than buried in output.

- **Genuinely-missing talk data (31 IDs, 9 quests).** A handful of real talks in `TalkExcelConfigData` have no data file — these are the only true gaps. Most trace to `talk_parsing._BAD_TALK_PATHS` (blocklisted bad files: `GlobalDialog.json`, `80045/80046.json`, `7401203-5.json`, etc.). IDs: `1180101, 7320408, 7323513-7323516, 7323520, 7323550, 7325602, 7325605, 7325608, 7325613-7325614, 7325618-7325619, 7325621, 7325625, 7328510, 7332901, 7332910, 7333001-7333013, 7418502, 7900501`. Decide whether to source these elsewhere or accept as upstream gaps.

- **Talk groups silently dropped on missing talk.** `get_talk_group_info` raises `RuntimeError` if any referenced talk fails to load (`processing.py`); in non-strict mode the whole `agd_talk_group` file is then skipped (no output, no placeholder). Consider degrading gracefully (skip the missing entry) instead of dropping the entire group.

## Testing

- **Better integration test coverage**, including a simple MCP server test case. (migrated from beads `istaroth-div`)
