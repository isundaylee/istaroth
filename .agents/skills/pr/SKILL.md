---
name: pr
description: Squash the current branch's work into a single commit and open (or update) a GitHub pull request with an appropriate title and description. Use when asked to "create a PR", "open a pull request", "put this up for review", or to update an existing PR for the current branch.
---

Turn the current branch's work into a single clean commit and a GitHub pull
request. Follow this project's git conventions exactly (see the "Git Workflow
Best Practices" in the root `AGENTS.md`).

## Workflow

Optimize for wall-clock: the happy path is **three round-trips, not seven**.
Each separate tool call costs a model round-trip, so batch aggressively:

- **Parallelize independent commands.** Issue them as multiple tool calls in one
  message so network and CPU overlap. The kickoff checks (branch/fetch
  inspection, `pre-commit`, frontend `tsc`) depend on nothing but the working
  tree — fire them together.
- **Chain the finalize sequence into ONE call.** Once the tree is green, squash →
  commit → push → `gh pr create` is a strict `&&` chain; running it as one
  command saves three round-trips and the steps short-circuit on first failure.

Happy path at a glance (one-commit-or-clean branch, checks pass):
1. Kickoff — parallel: `(a)` branch + fetch + merge-base inspection, `(b)`
   `pre-commit run` (+ frontend `tsc` if `frontend/` changed).
2. Write `/tmp/pr-<branch>-commit.txt` and `/tmp/pr-<branch>-body.md` (two `Write` calls, parallel). Substitute `<branch>` with the actual branch name (from kickoff) so the paths are unique per PR — never reuse a fixed `/tmp/commit-msg.txt`, since a leftover file from a prior run trips the Write tool's read-before-overwrite guard. Use the SAME concrete paths in the Write calls and the finalize chain.
3. Finalize — one `&&` chain: squash, commit, push, create PR.

Keep a rough **per-phase** timing (kickoff, finalize) and surface it in step 6 —
do NOT wrap every command separately, since that forces the serial round-trips
this skill is trying to avoid. One `s=$(date +%s); …; echo "[timing] $(( $(date
+%s) - s ))s"` around each grouped call is enough. Omit any phase that didn't run.

### 1. Kickoff — branch check + checks, in parallel

These are independent; issue them as parallel tool calls in ONE message.

- **(a) Branch + diff inspection** — one call:
  ```bash
  git fetch origin --quiet
  echo "branch: $(git rev-parse --abbrev-ref HEAD)"
  echo "merge-base: $(git merge-base HEAD origin/main)"
  git log --oneline "$(git merge-base HEAD origin/main)"..HEAD
  ```
  Never open a PR from the default branch (`main`). If the branch is `main`,
  create a feature branch first (`git switch -c <descriptive-name>`) carrying the
  working-tree changes. Note how the branch relates to `origin/main` so the PR
  diff is what you expect.
- **(b) pre-commit** (+ frontend type-check) — run pre-commit on the changes and
  stage whatever it rewrites BEFORE committing (it's managed by uv, so invoke it
  through `uv run`):
  ```bash
  uv run pre-commit run
  ```
  Re-run until it passes, staging its edits each time. (Per project rule: always
  run pre-commit separately and add the resulting changes before committing.)
  Run only the checks pre-commit does NOT cover: it runs eslint (whole
  `frontend/src/`) and mypy (changed files), so don't re-run those. The gap is
  frontend type-checking — eslint does not type-check — so when `frontend/`
  changed, add `cd frontend && node_modules/.bin/tsc --noEmit` (same parallel
  batch). Fix failures before opening the PR — don't put up a red branch.

While these run, draft the commit message and PR body (steps 3/4) so the files are
ready the moment the tree is green.

### 3. Squash the initial work into ONE clean commit
When first opening the PR, collapse the branch's incremental work into one
commit (subsequent review rounds will add commits on top — see Notes). Because
`git add -A` stages everything including the moved `text/` submodule pointer,
the squash is a single commit with no separate "Update text" amend:
- Several commits (usual): `git reset --soft $(git merge-base HEAD origin/main) && git add -A && git commit -F /tmp/pr-<branch>-commit.txt`.
- Exactly one commit already: amend into it: `git add -A && git commit --amend -F /tmp/pr-<branch>-commit.txt`.
- Only if you committed the code BEFORE the submodule pointer moved do you need a
  follow-up `git add text && git commit --amend --no-edit`; the `git add -A`
  above already covers the common case.

The branch is squash-merged on GitHub, so the final commit message comes from the
PR title + description (step 4), NOT these per-commit messages — keep the PR
description complete and accurate.

Write the commit message to `/tmp/pr-<branch>-commit.txt` (a `Write` call, done during
the step-1 kickoff) and pass it with `-F`, never inline `-m`/`--body` — bodies
routinely contain backticks/apostrophes the shell mangles.
- Subject: concise, imperative.
- Body: brief; bullets only when they help.
- If the work closes a tracked issue, add a closing keyword in the body (e.g.
  `Closes #55`) so GitHub auto-closes it on push.
- End the commit message with the required trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```

### 4. Finalize — commit + push + PR in ONE chain

For a brand-new PR (the happy path), squash, push, and create are a strict
dependency chain — run them as a single `&&` call so each round-trip is paid
once. With the squash already done in step 3, the rest is:
```bash
git push -u origin HEAD \
  && gh pr create --title "<concise title>" --body-file /tmp/pr-<branch>-body.md
```
Or fold step 3's squash in too, for the full happy-path one-liner:
```bash
git reset --soft "$(git merge-base HEAD origin/main)" \
  && git add -A \
  && git commit -F /tmp/pr-<branch>-commit.txt \
  && git push -u origin HEAD \
  && gh pr create --title "<concise title>" --body-file /tmp/pr-<branch>-body.md
```
Force-pushing your own PR branch is fine (`--force-with-lease` when updating an
already-pushed branch you own). NEVER force-push or rebase shared history such as
the `istaroth-text` submodule `main`.

**Updating an existing PR** (review rounds): the push already refreshes the diff,
so don't blindly create. Check once and branch:
```bash
git push && { gh pr view --json url -q .url || gh pr create --title "<title>" --body-file /tmp/pr-<branch>-body.md; }
```
Refresh the description only when the scope changed: `gh pr edit --body-file /tmp/pr-<branch>-body.md`.

PR description should cover, briefly (it becomes the squash-merge commit message,
so make it self-contained):
- **What & why** — the change and its motivation.
- **Notable details** — anything a reviewer needs (tradeoffs, follow-ups, data/checkpoint or submodule version assumptions).
- **Testing** — what you ran (checks, manual verification) and the result.
- `Closes #<n>` for any issue it resolves.

When the scope grows over review rounds, refresh the description (`gh pr edit
--body-file ...`) so the eventual merge commit message stays correct.

### 6. Report back
Print the PR URL (from `gh pr create`/`gh pr view`) so the user can open it.

Also print a short per-phase timing summary, using the seconds tracked around
the grouped calls — one line plus a total, e.g.:
```
Timing — kickoff (pre-commit+checks) 34s · finalize (commit+push+PR) 9s · total 43s
```
Only include the phases that actually ran this invocation.

## Notes
- Do NOT push or open the PR until the user has had a chance to review when the
  change includes regenerated corpus/text data — confirm first per the
  regen-text rules.
- Address review feedback as NEW commits — one per review round — instead of
  amending or re-squashing into existing commits, so the reviewer sees exactly
  what each round changed. The branch may carry several commits as a result;
  that's fine, squash-merge collapses them on merge. Re-squash only when the user
  explicitly asks.
