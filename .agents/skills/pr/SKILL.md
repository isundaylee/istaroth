---
name: pr
description: Squash the current branch's work into a single commit and open (or update) a GitHub pull request with Graphite (`gt`). Use when asked to "create a PR", "open a pull request", "put this up for review", or to update an existing PR for the current branch.
---

Turn the current branch's work into a single clean commit and a GitHub pull
request, using the Graphite CLI (`gt`). Follow this project's git conventions
exactly (see the "Git Workflow Best Practices" in the root `AGENTS.md`).

This project standardizes on Graphite: assume `gt` is installed and
authenticated (`gt auth`). Graphite owns the branch → PR mapping, so **the
branch's commit message is the PR** — its subject becomes the PR title and its
body becomes the PR description, which in turn becomes the squash-merge commit
message. There is no separate PR-body file: write the description as the commit
message. `gt submit` handles push + PR create/update in one step.

## Workflow

Optimize for wall-clock: the happy path is **three round-trips, not seven**.
Each separate tool call costs a model round-trip, so batch aggressively:

- **Parallelize independent commands.** Issue them as multiple tool calls in one
  message so network and CPU overlap. The kickoff checks (branch/stack
  inspection, `pre-commit`, frontend `tsc`) depend on nothing but the working
  tree — fire them together.
- **Chain the finalize sequence into ONE call.** Once the tree is green, squash →
  commit → `gt submit` is a strict `&&` chain; running it as one command saves
  round-trips and short-circuits on first failure.

Happy path at a glance (one-commit-or-clean branch, checks pass):
1. Kickoff — parallel: `(a)` branch + stack + merge-base inspection, `(b)`
   `pre-commit run` (+ frontend `tsc` if `frontend/` changed).
2. Write `/tmp/pr-<branch>-commit.txt` — the commit message, which IS the PR
   title + description (one `Write` call). Substitute `<branch>` with the actual
   branch name so the path is unique per PR — never reuse a fixed
   `/tmp/commit-msg.txt`, since a leftover file trips the Write tool's
   read-before-overwrite guard. Use the SAME concrete path in the Write call and
   the finalize chain.
3. Finalize — one `&&` chain: squash into one commit, track, `gt submit`.

Keep a rough **per-phase** timing (kickoff, finalize) and surface it in the last
step — do NOT wrap every command separately, since that forces the serial
round-trips this skill is trying to avoid. One `s=$(date +%s); …; echo "[timing]
$(( $(date +%s) - s ))s"` around each grouped call is enough. Omit any phase that
didn't run.

### 1. Kickoff — branch/stack check + checks, in parallel

These are independent; issue them as parallel tool calls in ONE message.

- **(a) Branch + stack inspection** — one call:
  ```bash
  git fetch origin --quiet
  gt log short
  echo "branch: $(git rev-parse --abbrev-ref HEAD)"
  echo "merge-base: $(git merge-base HEAD origin/main)"
  git log --oneline "$(git merge-base HEAD origin/main)"..HEAD
  ```
  Never open a PR from trunk (`main`). If you're on `main`, create a tracked
  feature branch carrying the working-tree changes first — `git switch -c
  <descriptive-name>` (you'll `gt track --parent main` it in finalize). Note how
  the branch relates to `origin/main` so the PR diff is what you expect.
- **(b) pre-commit** (+ frontend type-check) — run pre-commit on the changes and
  stage whatever it rewrites BEFORE committing (it's managed by uv, so invoke it
  through `uv run`):
  ```bash
  uv run pre-commit run
  ```
  Re-run until it passes, staging its edits each time. (Per project rule: always
  run pre-commit separately and add the resulting changes before committing.)
  `gt submit` runs git hooks by default, but running pre-commit explicitly here
  lets you stage its rewrites into the commit instead of failing the submit.
  Run only the checks pre-commit does NOT cover: it runs eslint (whole
  `frontend/src/`) and mypy (changed files), so don't re-run those. The gap is
  frontend type-checking — eslint does not type-check — so when `frontend/`
  changed, add `cd frontend && node_modules/.bin/tsc --noEmit` (same parallel
  batch). Fix failures before opening the PR — don't put up a red branch.

While these run, draft the commit message (step 2) so the file is ready the
moment the tree is green.

### 2. Write the commit message = the PR

Write `/tmp/pr-<branch>-commit.txt`. Because Graphite turns this message into the
PR, it must be a complete, self-contained PR description (it becomes the
squash-merge commit message):
- **Subject** — concise, imperative; becomes the PR title.
- **Body** — what & why, notable details a reviewer needs (tradeoffs,
  follow-ups, data/checkpoint or submodule version assumptions), and testing
  (what you ran and the result). Bullets only when they help.
- If the work closes a tracked issue, add a closing keyword (e.g. `Closes #55`)
  so GitHub auto-closes it on merge.
- End with the required trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```

### 3. Squash the branch's work into ONE clean commit

When first opening the PR, collapse the branch's incremental work into one
commit (review rounds amend this single commit rather than adding to it — see
Notes). Because `git add -A` stages everything including the moved `text/`
submodule pointer, the squash is a single commit with no separate "Update text"
amend:
- Several commits (usual): `git reset --soft "$(git merge-base HEAD origin/main)" && git add -A && git commit -F /tmp/pr-<branch>-commit.txt`.
- Exactly one commit already: amend into it — `git add -A && git commit --amend -F /tmp/pr-<branch>-commit.txt` (or `gt modify` to amend + auto-restack any branches above).
- Only if you committed the code BEFORE the submodule pointer moved do you need a
  follow-up `git add text && git commit --amend --no-edit`; the `git add -A`
  above already covers the common case.

### 4. Finalize — squash + track + submit in ONE chain

For a brand-new PR (the happy path), run the squash, track, and submit as a
single `&&` call:
```bash
git reset --soft "$(git merge-base HEAD origin/main)" \
  && git add -A \
  && git commit -F /tmp/pr-<branch>-commit.txt \
  && gt track --parent main \
  && gt submit --no-interactive --publish
```
- `gt track --parent main` registers the branch on trunk (idempotent if already
  tracked); skip it only when the branch is already tracked with the right
  parent.
- `gt submit` submits just this branch's PR (from trunk up to it). It force-pushes
  your own branch with `--force-with-lease` and prints the PR URL.
- `--publish` opens the PR ready-for-review, not draft (this project does not use
  draft PRs). `--no-interactive` skips the metadata editor and takes the PR
  title/description straight from the commit message.

NEVER force-push or rebase shared history such as the `istaroth-text` submodule
`main`; force-pushing your own PR branch (what `gt submit` does) is fine.

**Updating an existing PR** (review rounds): fold the new work into the branch's
single commit — `git add -A && gt modify` amends the commit and auto-restacks any
branches above it — then re-run `gt submit --no-interactive --publish` to
force-push and update the PR. Keep it one commit per PR; don't stack a commit per
round (see Notes). When the scope changed enough that the PR title/description is
now stale, update the commit message as you amend (`gt modify` opens it, or `git
commit --amend`), then push the refreshed metadata — plain `gt submit` will NOT
re-push the title/description, so use `gt submit --edit` (interactive) or `gh pr
edit` non-interactively.

### 5. Report back
Print the PR URL (from `gt submit`) so the user can open it, plus a short
per-phase timing summary using the seconds tracked around the grouped calls —
one line plus a total, e.g.:
```
Timing — kickoff (pre-commit+checks) 34s · finalize (commit+submit) 9s · total 43s
```
Only include the phases that actually ran this invocation.

## Notes
- Do NOT push or open the PR until the user has had a chance to review when the
  change includes regenerated corpus/text data — confirm first per the
  regen-text rules.
- Keep each PR a SINGLE commit, including across review rounds: amend with `gt
  modify` instead of adding a commit per round. Graphite lets reviewers diff a
  PR's previously submitted version against its current one, so incremental
  commits aren't needed to show what changed between rounds.
- For work that splits into dependent pieces, stack the PRs: `gt create` each
  branch on top of the one below, then `gt submit --stack` to open/update the
  whole stack at once (each PR based on the branch beneath it, the bottom on
  `main`). `gt sync` pulls `main`, restacks, and cleans up merged branches.
