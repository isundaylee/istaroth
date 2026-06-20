---
name: pr
description: Squash the current branch's work into a single commit and open (or update) a GitHub pull request with an appropriate title and description. Use when asked to "create a PR", "open a pull request", "put this up for review", or to update an existing PR for the current branch.
---

Turn the current branch's work into a single clean commit and a GitHub pull
request. Follow this project's git conventions exactly (see the "Git Workflow
Best Practices" in the root `AGENTS.md`).

## Workflow

Time each step so the final report can show where the pre-PR work went. Wrap
each significant command (or group) so its wall-clock duration is captured, e.g.:
```bash
s=$(date +%s); pre-commit run; echo "[timing] pre-commit: $(( $(date +%s) - s ))s"
```
Keep a running tally of the per-step seconds (pre-commit, type/other checks,
squash/commit, push, PR create/edit) and surface it in step 6. Don't let timing
get in the way of the actual work — if a step wasn't run, just omit it from the
summary rather than reporting a fabricated number.

### 1. Confirm the branch
- Never open a PR from the default branch (`main`). If `git rev-parse --abbrev-ref HEAD` is `main`, create a feature branch first (`git switch -c <descriptive-name>`) carrying the working-tree changes.
- `git fetch origin` and note how the branch relates to `origin/main` so the PR diff is what you expect.

### 2. Get the tree clean and reviewed
- Run pre-commit on the changes and stage whatever it rewrites BEFORE committing:
  ```bash
  pre-commit run
  ```
  Re-run until it passes, staging its edits each time. (Per project rule: always
  run pre-commit separately and add the resulting changes before committing.)
- Run only the checks that pre-commit does NOT already cover. pre-commit runs
  eslint (whole `frontend/src/`) and mypy (changed files), so don't re-run those.
  The notable gap is frontend type-checking — eslint does not type-check — so for
  frontend changes run `cd frontend && node_modules/.bin/tsc --noEmit`. Fix
  failures before opening the PR — don't put up a red branch.

### 3. Squash the initial work into ONE clean commit
When first opening the PR, collapse the branch's incremental work into one
commit (subsequent review rounds will add commits on top — see Notes):
- If there is exactly one commit already, amend into it: `git add -A && git commit --amend`.
- If there are several, squash them: `git reset --soft $(git merge-base HEAD origin/main) && git add -A && git commit`.
- Fold the `text/` submodule pointer (when it moved) INTO this commit rather than
  a separate "Update text" commit: `git add text && git commit --amend --no-edit`.

The branch is squash-merged on GitHub, so the final commit message comes from the
PR title + description (step 5), NOT these per-commit messages — keep the PR
description complete and accurate.

Write the commit message via a file, not inline `-m`/`--body` (bodies routinely
contain backticks/apostrophes the shell mangles):
```bash
git commit -F /tmp/commit-msg.txt        # or: git commit --amend -F /tmp/commit-msg.txt
```
- Subject: concise, imperative.
- Body: brief; bullets only when they help.
- If the work closes a tracked issue, add a closing keyword in the body (e.g.
  `Closes #55`) so GitHub auto-closes it on push.
- End the commit message with the required trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```

### 4. Push
```bash
git push -u origin HEAD        # add --force-with-lease only when updating an already-pushed branch you own
```
Force-pushing your own PR branch is fine. NEVER force-push or rebase shared
history such as the `istaroth-text` submodule `main`.

### 5. Open (or update) the PR
- Check for an existing PR first: `gh pr view --json number,url,state 2>/dev/null`.
- If none, create it with the body passed via a file:
  ```bash
  gh pr create --title "<concise title>" --body-file /tmp/pr-body.md
  ```
- If one exists, the push already updated the diff; refresh the description when
  the scope changed: `gh pr edit --body-file /tmp/pr-body.md`.

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

Also print a short timing summary of the pre-PR steps, using the per-step
seconds tracked above — one line per step plus a total, e.g.:
```
Timing — pre-commit 12s · checks 34s · commit 2s · push 3s · PR create 4s · total 55s
```
Only include the steps that actually ran this invocation.

## Notes
- Do NOT push or open the PR until the user has had a chance to review when the
  change includes regenerated corpus/text data — confirm first per the
  regen-text rules.
- Address review feedback as NEW commits — one per review round — instead of
  amending or re-squashing into existing commits, so the reviewer sees exactly
  what each round changed. The branch may carry several commits as a result;
  that's fine, squash-merge collapses them on merge. Re-squash only when the user
  explicitly asks.
