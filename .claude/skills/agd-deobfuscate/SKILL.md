---
allowed-tools: Bash,Read,Edit,Glob,Grep
---

Fill in new deobfuscation entries in `istaroth/agd/deobfuscation.py` by comparing a cleartext AGD revision against a new obfuscated HEAD revision.

## Context

AnimeGameData (AGD, at path `<AGD>`) periodically ships new builds where field names in JSON files are obfuscated. The file `istaroth/agd/deobfuscation.py` maintains `_COMMON_FIELD_MAPPINGS`, a dict mapping obfuscated keys → cleartext field names. Each new obfuscation round needs a new batch of entries.

The set of fields to find is determined by reading the **latest comment block section** already in `_COMMON_FIELD_MAPPINGS` (e.g. `# OSRELWin6.3.0_R41701329_S41708913_D41667700`) and using its cleartext values as the target list.

## Workflow

### 1. Read the existing file

Read `istaroth/agd/deobfuscation.py` to find:
- The latest comment section block and the cleartext field names it maps (these are the fields to find for the new version)
- All existing obfuscated keys (to avoid duplicates)

### 2. Identify the HEAD commit title

```bash
cd <AGD> && git log --oneline HEAD | head -1
```

This gives the comment label for the new section (e.g. `CNRELWin6.4.0_R42630645_S42523468_D42623923`).

### 3. Compare reference files

Use these four reference file types (adjust filenames to ones that exist at both revisions):

- `BinOutput/Quest/<id>.json` — quest-level fields plus `subQuests` and `talks` items
- `BinOutput/Talk/Npc/<id>.json` — `talkId`, `dialogList`, dialog item fields
- `BinOutput/Talk/GadgetGroup/<id>.json` — `configId`, `talks` (group-level)
- `BinOutput/Talk/NpcGroup/<id>.json` — `npcId`, `talks` (group-level)

For each file, show both revisions:
```bash
cd <AGD>
git show <cleartext_rev>:<file_path>
git show HEAD:<file_path>
```

### 4. Build the mapping

Match values between cleartext and obfuscated versions to identify which obfuscated key corresponds to which cleartext field.

**Quest file disambiguation tip**: `id`, `resId`, `series`, and `chapterId` can all share the same value in some quests. Cross-check with a second quest (e.g. `BinOutput/Quest/74078.json`) where they differ:
```bash
git show <cleartext_rev>:BinOutput/Quest/74078.json | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('id:', d.get('id'), 'resId:', d.get('resId'), 'series:', d.get('series'), 'chapterId:', d.get('chapterId'))"
git show HEAD:BinOutput/Quest/74078.json | python3 -c "
import json,sys; d=json.load(sys.stdin)
for k,v in d.items():
    if isinstance(v,int) and v>1000: print(k,':',v)"
```

### 5. Verify

Cross-check identified keys against a second quest file to confirm `subId`/`order`/`questId`/`npcId`:
```bash
git show HEAD:BinOutput/Quest/74078.json | python3 -c "
import json,sys; d=json.load(sys.stdin)
sq=d.get('<subQuests_key>',[])
for s in sq[:2]: print({k:v for k,v in s.items() if isinstance(v,int) and v>0})
tk=d.get('<talks_key>',[])
for t in tk[:2]: print({k:v for k,v in t.items() if isinstance(v,(int,list)) and v})"
```

### 6. Add entries to deobfuscation.py

Append a new block at the end of `_COMMON_FIELD_MAPPINGS` in `istaroth/agd/deobfuscation.py`, covering exactly the fields from the latest previous section that were found in the reference files:

```python
    # <HEAD commit title>
    "<OBF_KEY>": "<cleartext_field>",
    ...
```

Only include fields actually observed in the reference files. Skip any that could not be confirmed.

## Notes

- The same obfuscated key may appear at multiple nesting levels (e.g. `id` appears in top-level quest, inside `subQuests` items, and inside `talks` items — all map to the same key).
- `npcId` in NpcGroup files also appears as `activityId` at the group's top level — false collision; `npcId` is correct for item context and the top-level field is unused by this codebase.
- Confirm no new key duplicates an existing entry in `_COMMON_FIELD_MAPPINGS` before adding.
