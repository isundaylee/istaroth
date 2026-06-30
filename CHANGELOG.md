# Changelog

<!--
Last updated through commit: 9cbf099ea3544d8e6d6c6d775eb062028ffebc40 (9cbf099)
When extending this changelog, document commits landed after the hash above,
then update this marker to the new cutoff commit.
-->

## Week of 2026-06-29 – 2026-07-05

- **Frontend**
  - Re-skinned the web UI with a navy + gold palette and flat hairline surfaces,
    then unified it into a single connected-card layout with a re-skinned home
    hero.
  - Migrated styling to component-scoped CSS Modules (including the nav) and
    dropped dead citation `!important` rules.
  - Modularized base form primitives (Select/Button/TextInput) via variant props.
  - Added a visible hairline border to composer controls in dark mode and fixed
    three mobile layout issues on the nav and Retrieve page.

## Week of 2026-06-22 – 2026-06-28

- **Frontend**
  - Scaffolded component-scoped CSS Modules (Composer, Card) with a token layer.
  - Leaned on nav and breadcrumbs and integrated the Retrieve composer.
- **RAG**
  - Reframed retrieval-intent classification around context-need and stopped the
    query normalizer from substituting phonetically-near proper nouns.
  - Captured retrieval-eval runs as local OTEL span traces.
- **Text/corpus**
  - *Enhancements & fixes:*
    - Rendered `PLAYERAVATAR`/`MATEAVATAR` `SEXPRO` pronoun placeholders in text
      output.
- **CI/build**
  - Added a frontend `tsc` pre-commit hook and fixed a dev-stack `node_modules`
    clobber.
- **Docs**
  - Documented the MCP servers and image-presentation caveat in AGENTS.md.

## Week of 2026-06-15 – 2026-06-21

- **Frontend**
  - Unified citation and proper-noun popups on a shared `FloatingPanel`, made
    them draggable, resizable from the bottom-right corner, minimizable,
    fullscreen-capable, and nestable; contained citation popup scrolling and
    adopted OS-default scrollbars.
  - Citations now render as full document text with the cited span highlighted,
    and chunk-loading controls were simplified.
  - Added on-the-fly proper-noun highlighting in conversation answers and on
    library text pages.
  - Cached query results by cache key for instant replay, recorded anonymous
    conversation history, and added library selection actions, retrieval
    thoroughness presets, and updated Q&A composer controls.
  - Unified library browsing into a single document tree with consistent
    breadcrumbs, hid the TOC for standalone quests, and highlighted the active
    quest with inline TOC quests.
  - Consolidated the primary-blue palette into fill/text tokens, wrapped long
    lines in keyword-search snippets, added GitHub-style keyboard navigation,
    auto-focused the search box, and surfaced chunk character offsets in document
    metadata.
  - Fixed undefined-CSS-variable links and stale talk-group cards.
- **MCP**
  - Added corpus browsing by category via manifest navigation.
  - Added a `get_document_hierarchy` tool with canonical hierarchy navigation.
  - Added a `retrieve_bm25` tool for exact-term BM25 search.
- **RAG**
  - Switched context rendering to raw-file slices backed by `ScoredChunk` and
    deduplicated overlapping chunk content.
  - Streamed pipeline progress to the web UI.
  - Extracted library proper nouns on the fly via LLM and filtered the
    proper-noun dictionary with a negative list.
  - Added TextMap fallback for recovering dropped text IDs.
  - Recorded Q&A retrieval stats, returned user-facing messages for common LLM
    API failures, and tuned the query decomposition prompt.
  - Migrated the RAG pipeline to a LangGraph `StateGraph`.
  - Added an LLM query-normalization node and an adaptive retrieval budget driven
    by query-intent classification (with the `conversations.budget` migration),
    plus DeepInfra flash generation models.
  - Added a retrieval-quality eval harness with production-query breadth and
    precision fixtures (e.g. 深渊教团, 卡特的全名), a parallelized runner, a single
    coverage metric matched against actual chunks, and an LLM judge to rescue
    false-miss facets; removed the legacy `retrieve_eval` CLI and dead code.
  - Added a LangSmith query tool for production trace inspection.
- **Backend**
  - Exposed file table-of-contents as a backend endpoint (removing duplicated
    frontend logic) and resolved `title_key` at hierarchy build time.
  - Reduced DataRepo Excel-loader boilerplate and fixed deterministic talk-group
    selection.
- **Text/corpus**
  - *New content:*
    - Extracted monster/enemy descriptions as a new `agd_creature` category.
    - Extracted Coop (hangout) talks as a new category.
  - *Enhancements & fixes:*
    - Grouped multi-volume book series into single readables.
    - Keyed `GadgetGroup` by composite `(configId, groupId)` and updated the
      corpus sanity test for composite filenames.
    - Rendered Hangout text with explicit branch routing and fork numbering, and
      renamed the `AGD_COOP` category to `AGD_HANGOUT`.
    - Regenerated the corpus.
- **Dev infra**
  - Added a dev-compose wrapper for per-worktree Docker dev stacks with Paseo
    worktree/service support and `PASEO_PORT`.
  - Sped up and parallelized startup, disabled pyc compilation, and made the dev
    frontend reachable by hostname.
  - Mounted dev-stack code read-only and shared backend env via a YAML anchor.
  - Fixed Paseo port refresh and Conductor port conflicts, isolated per-worktree
    checkpoints via copy-on-write clone, and added a time component to checkpoint
    tags.
  - Defaulted setup to rebase onto the configured upstream and skipped pre-PR
    checks already covered by pre-commit.
  - Used a named volume for dev data instead of a bind mount.
- **CI/build**
  - Made CPU-only PyTorch the default and simplified CI workflows.
  - Sped up mypy and test workflows and fixed Docker export freshness and
    CUDA-torch re-sync issues.
  - Cached chunk embeddings across checkpoint builds and built checkpoint
    languages in parallel.
- **Tech debt**
  - Split `istaroth/agd/types.py` into focused per-category modules.
  - Typed TextMap hashes as `int` end-to-end with named readable filenames.
  - Split crowded `processing.py`/`rendering.py` into per-renderable-type
    modules and dropped the stale category↔prefix map and orphaned naming check.
- **Docs**
  - Documented parallel CHS/ENG text regeneration.
  - Added a weekly CHANGELOG and changelog skill, and batched the `pr` skill's
    happy path into three round-trips.

## Week of 2026-06-08 – 2026-06-14

- **Text/corpus**
  - *New content:*
    - Extracted character constellation names/descriptions and achievement
      sections.
    - Discovered weapons from config and merged multi-page weapon stories.
  - *Enhancements & fixes:*
    - Grouped multi-volume series.
    - Gave human-readable titles to material-type and talk-group files and
      skipped `？？？` readables.
    - Resolved subset/superset `talkId` collisions and duplicate dialog options.
    - Regenerated the corpus.
- **Parsing robustness**
  - Promoted never-occurring parsing issues to hard errors and made
    quest-hierarchy chapter lookup strict.
  - Collected and reported non-fatal parsing issues in aggregate, and degraded
    gracefully on missing talks in talk groups.
- **AGD types**
  - Added documented `TypeAlias`es for AGD ids and made them match their on-disk
    `int` wire type.
  - Mapped legacy talk-group IDs.
- **RAG**
  - Fixed the RRF reranker dedup key.
- **Frontend**
  - Added a cross-tree search box to the quest hierarchy view.
- **CI/build**
  - Built and released checkpoints via GitHub Actions and parallelized
    vector-store embedding with bounded batches.
  - Added path filters to test, mypy, and frontend workflows.
- **Project/docs**
  - Shared agent skills across tools, migrated TODO follow-ups to GitHub issues,
    and documented the regen-corpus / push-text-regen workflow.
