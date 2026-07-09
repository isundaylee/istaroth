---
name: regen-text
description: Regenerate, audit, commit, and push Istaroth's generated text corpus in the text/ submodule. Use when the user asks to "regen corpus", regenerate committed text output, audit a corpus diff for content loss, or push a previously verified text regeneration.
---

# Regenerate Text

Run every command from the parent repository root unless explicitly told to run inside `text/`. Preserve the parent repository's single-commit PR workflow.

## Regenerate the corpus

When the user asks to **regen corpus**:

1. Inspect the parent and submodule status. Do not overwrite unrelated user changes.
2. Rebase onto the latest target branch:

   ```bash
   git fetch origin
   git rebase origin/main
   ```

3. Initialize the submodule shallowly when needed:

   ```bash
   git submodule update --init --depth 1 text
   ```

   Depth 1 is sufficient because the audit compares the working tree with the pinned `HEAD`.

4. In `text/`, check out `main` before committing. If the shallow checkout lacks the local branch, create or reset it at the pinned commit without discarding changes.
5. Time a complete regeneration of both languages. The two write to
   independent directories (`text/chs` vs `text/eng`), so run them in parallel.
   Each run writes its exit code to a sentinel file the moment it finishes, so
   completion (and success) can be detected reliably — including across separate
   tool calls when the regen is launched detached/in the background:

   ```bash
   source .env.common   # provides AGD_PATH; without it both runs fail instantly
   rm -f /tmp/regen-chs.status /tmp/regen-eng.status
   ( uv run scripts/agd_tools.py generate-all -f text/chs > /tmp/regen-chs.log 2>&1; echo $? > /tmp/regen-chs.status ) &
   ( AGD_LANGUAGE=ENG uv run scripts/agd_tools.py generate-all -f text/eng > /tmp/regen-eng.log 2>&1; echo $? > /tmp/regen-eng.status ) &
   ```

   A full dual-language regen takes only a few minutes, so check the sentinel
   files soon after launching. Peek at both logs shortly after launch to catch
   instant failures (e.g. `Error: AGD_PATH environment variable not set`).

   To check for completion, poll for both sentinel files to exist, then read the
   codes — do NOT use `pgrep`/`ps` name matching (it is fragile and can match the
   checker itself):

   ```bash
   if [ -f /tmp/regen-chs.status ] && [ -f /tmp/regen-eng.status ]; then
     echo "chs=$(cat /tmp/regen-chs.status) eng=$(cat /tmp/regen-eng.status)"   # both present => both done
   else
     echo "still running"
   fi
   ```

   When running both in the same foreground shell instead, capture the PIDs
   (`chs_pid=$!`) right after each `&` and `wait "$chs_pid"; chs_status=$?` on
   each. Either way, both must exit 0; inspect the corresponding log on any
   non-zero status. A finished log ends with a `Document hierarchy written to
   …/metadata/agd/hierarchy.json` line, a useful secondary completeness signal.
   Never use `--only` for committed corpus output. It is allowed only for ad hoc output in a throwaway directory.

6. Audit the generated diff using the procedure below. Treat any unexplained lost content as a failure to investigate before committing.
7. Run pre-commit separately from committing and add any resulting changes.
   `pre-commit` is not on PATH; invoke it as `uv run pre-commit run`.
8. Commit the generated data inside `text/` on its `main` branch.
9. Record the submodule pointer in the parent repository's single code commit:
   - Amend the existing code commit with `git add text && git commit --amend --no-edit` when the regen accompanies a code change.
   - For a pure text regeneration, create the parent's one commit normally.
10. Report the wall-clock regeneration duration and audit results. Do not push either repository; wait for user verification.

## Audit corpus diffs

Run the audit inside `text/`. Compare each changed file's working-tree content with `git show HEAD:<path>`.

1. Audit `chs` and `eng` independently. Do not cross-normalize language-specific macros such as `{NICKNAME}` or `{M#...}{F#...}`.
2. Normalize each line by stripping whitespace and dropping:
   - blank lines
   - `Option \d+:`
   - `## Talk N`
   - `### ...`
   - `(Quest is part of chapter...)`
3. Compare `collections.Counter` values per file:
   - `old - new` is genuinely lost content.
   - `new - old` is added content.
4. Aggregate results across all changed files. `lost-content == 0` is the pass condition; do not rely on `--numstat` or net line counts.
5. Split additions into:
   - brand-new lines absent from the old file
   - increased multiplicity of lines already present in the old file
6. Categorize totals by `agd_quest`, `agd_talk`, and `agd_talk_group`.
7. After the aggregate passes, sample files for growth ratios and inspect one or two representative diffs. Avoid a full serial `git show` scan of every file.

## Push a verified regeneration

When the user later asks to **push the text regen** after verification:

1. Confirm both repositories are clean and the parent points at the intended submodule commit.
2. Push the `istaroth-text` commit from `text/` to its remote `main` branch first.
3. Force-push the current parent PR branch because amending the submodule pointer rewrote its single commit. Use the existing upstream and prefer `--force-with-lease`.
4. Report both pushed commit IDs and branch names.
