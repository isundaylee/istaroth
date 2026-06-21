---
name: changelog
description: Generate or update CHANGELOG.md from landed git history. Use when the user asks to "write a changelog", "update the changelog", or summarize what changed over the last week/period.
---

# Update Changelog

Maintain `CHANGELOG.md` at the repo root. Run every command from the repo root.

## Determine the range

1. Read the cutoff marker near the top of `CHANGELOG.md`:

   ```
   <!--
   Last updated through commit: <full-hash> (<short-hash>)
   ...
   -->
   ```

   Document only commits landed **after** that hash. If `CHANGELOG.md` does not
   exist yet, ask the user (or infer from the request) how far back to go.

2. List the commits to document, newest first:

   ```bash
   git log <cutoff-hash>..HEAD --pretty=format:"%H|%ad|%s" --date=short
   ```

   For a fresh changelog with a date bound instead of a hash, use
   `git log --since="<date>" ...`.

## Structure

- **Group by week**, newest week first. Weeks run **Monday–Sunday**; a commit
  dated on a Sunday closes the week that began the preceding Monday. Heading
  format: `## Week of YYYY-MM-DD – YYYY-MM-DD`.
- Within each week, **one top-level bullet per area** (the general subsystem a
  change touched). Common areas: `Frontend`, `MCP`, `RAG`, `Backend`,
  `Text/corpus`, `Dev infra`, `CI/build`, `AGD types`, `Parsing robustness`,
  `Tech debt`, `Docs`, `Project/docs`. Add a new area label when a recurring one
  isn't covered.
- Under each area, write sub-bullets describing the changes. **Group similar
  commits together** rather than listing them one-to-one — e.g. a dozen
  floating-panel PRs collapse into a few sub-bullets. Keep descriptions brief and
  outcome-focused; reference PR/issue numbers only when they add value.

### Text/corpus split

The `Text/corpus` area is special: split its sub-bullets into two labeled
groups, **new content first**, then changes:

```
- **Text/corpus**
  - *New content:*
    - <newly extracted categories / data>
  - *Enhancements & fixes:*
    - <restructuring, keying fixes, titling, corpus regeneration>
```

Classify a commit as *new content* when it surfaces game data not previously in
the corpus (a new category, newly extracted descriptions/stories). Everything
else — restructuring, dedup, keying fixes, human-readable titles, regenerations
— goes under *Enhancements & fixes*.

## Update the cutoff marker

After writing the entries, set the marker to the newest documented commit
(`HEAD` of the range). Keep both the full hash and the short hash:

```
Last updated through commit: <full-hash> (<short-hash>)
```

## Notes

- Fold `Update text` commits and submodule-pointer moves into the relevant
  corpus entry; don't list them on their own.
- When unsure which area a commit belongs to, read its diff/subject — the PR
  title usually names the subsystem.
- Don't invent changes. Every bullet must trace to a real commit in the range.
