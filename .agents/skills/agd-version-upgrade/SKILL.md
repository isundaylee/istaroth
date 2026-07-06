---
name: agd-version-upgrade
description: Ingest a new AnimeGameData (AGD) build end-to-end — deobfuscation mappings, TextMap fallback-list audit, first-seen version index, and corpus regen. Use when bumping AGD_PATH / AGD to a new game version.
---

# Ingest a New AGD Version

Orchestrates the steps needed whenever `<AGD>` moves to a new build: new
deobfuscation mappings, an audit of the TextMap fallback list, an update of
the first-seen version index, then a corpus regen. Some steps have their own
skill; this one sequences them and adds the steps that don't otherwise have
a home.

## 1. Add deobfuscation mappings

Run the `agd-deobfuscate` skill (`.agents/skills/agd-deobfuscate/SKILL.md`)
first. This is the most important step of ingesting a new version: 6.x+
builds obfuscate JSON field names, and any field missing from
`istaroth/agd/deobfuscation.py`'s new-version block reads as absent rather
than erroring — it produces silently incomplete output (e.g. dropped
speaker names, empty fields) instead of a loud failure. Every later step
depends on this being correct and complete for the new build.

## 2. Audit the TextMap fallback list

Every version bump drops some `talkContentTextMapHash` entries from the
current build's TextMap that resolved in the previous build (investigated in
issue #273: renders as `Missing text (<hash>)` in the corpus). `DataRepo`
recovers these via `_TEXT_MAP_FALLBACK_REFS` in `istaroth/agd/repo.py` — a
small tuple of pinned older-build commit refs (in `<AGD>`), ordered
newest-to-oldest, merged in as a fallback source when the current TextMap
lacks a hash.

1. Regenerate a representative slice ad hoc (`--only agd_quest` is enough —
   dialog-heavy and where regressions concentrate) into a throwaway
   directory for both languages:

   ```bash
   AGD_PATH=<AGD> uv run scripts/agd_tools.py generate-all -f --only agd_quest /tmp/audit_chs
   AGD_PATH=<AGD> AGD_LANGUAGE=ENG uv run scripts/agd_tools.py generate-all -f --only agd_quest /tmp/audit_eng
   ```

2. Count unique missing hashes and compare against the pre-upgrade corpus
   (the last committed `text/agd_quest`):

   ```bash
   grep -rho "Missing text ([0-9]*)" /tmp/audit_chs | sort -u | wc -l
   grep -rho "Missing text ([0-9]*)" text/chs/agd_quest | sort -u | wc -l
   ```

3. If the new build's count jumped meaningfully above the old corpus's
   baseline, the new build dropped hashes the old build still had. Add the
   **immediately preceding minor-version build's commit** (from `<AGD>`'s
   git history — `git log --oneline --all | grep <prev-minor-version>` — pick
   the last commit for that version) to the front of
   `_TEXT_MAP_FALLBACK_REFS`, newest-first.
   - Per the #273 investigation, going back further than the 1-2 immediately
     preceding minor versions has essentially zero marginal recovery —
     nothing older than that ever contributed a recoverable hash in that
     audit. Don't add a long tail of old refs; add just enough of the most
     recent versions to flatten the count.
   - Verify by re-running step 1 with the new ref in place and confirming
     the missing-hash count drops back toward baseline.
   - Not every hash is recoverable this way: some are genuinely new content
     whose TextMap row is simply absent from the new dump. Don't chase the
     count to zero — chase it back to the old baseline.
4. `uv run pytest tests/test_repo.py tests/test_processing.py` (with
   `AGD_PATH` set) to confirm the SEXPRO pronoun-hash resolution and
   fallback-ordering tests still pass — they're sensitive to
   `_TEXT_MAP_FALLBACK_REFS` changes.

## 3. Update the first-seen version index

Corpus items carry `min_version`/`max_version` metadata resolved from the
per-version delta files in `text/first_seen/` in the `text/` submodule (see
`istaroth/agd/first_seen.py`). Ingesting a new build must extend the index,
or `generate-all` fails on the new build's ids:

1. Append the new version's `(version, commit)` entry to `_SNAPSHOTS` in
   `scripts/build_first_seen.py`. Use the new build's snapshot commit in
   `<AGD>`'s git history; normalize hotfix versions to `major.minor`.
2. Run `uv run python scripts/build_first_seen.py --agd-path <AGD>` — it
   scans only the new snapshot and writes
   `text/first_seen/<version>.json` with the ids not seen in any earlier
   version. The new data file is committed to the `text/` submodule as part
   of the corpus regen commit (step 4); the `_SNAPSHOTS` entry is committed
   in the main repo.

## 4. Regenerate and commit the corpus

Run the `regen-text` skill (`.agents/skills/regen-text/SKILL.md`) for the
full committed regeneration, diff audit, and commit — never commit the ad
hoc `--only` output from step 2.
