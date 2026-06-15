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
5. Time a complete regeneration of both languages:

   ```bash
   uv run scripts/agd_tools.py generate-all -f text/chs
   AGD_LANGUAGE=ENG uv run scripts/agd_tools.py generate-all -f text/eng
   ```

   Never use `--only` for committed corpus output. It is allowed only for ad hoc output in a throwaway directory.

6. Audit the generated diff using the procedure below. Treat any unexplained lost content as a failure to investigate before committing.
7. Run pre-commit separately from committing and add any resulting changes.
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
