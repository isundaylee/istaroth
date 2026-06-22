---
name: retrieval-fixtures
description: Add or revise retrieval-quality eval fixtures under istaroth/rag/eval/retrieval_fixtures/ (one JSON file per category, e.g. breadth.json). Use when asked to add a retrieval eval case, add a new eval category, improve a fixture's ground truth, or harden fixtures against false misses. Fixtures grade whether retrieval surfaces the sources a query needs, measured by passage-anchored facet coverage.
---

# Add a Retrieval Eval Fixture

Run every command from the repository root. The pieces:

- Data: `istaroth/rag/eval/retrieval_fixtures/<category>.json` — one file per category (e.g. `breadth.json`).
- Loader / types / metric: `istaroth/rag/eval/retrieval.py`.
- Runner: `scripts/rag_tools.py eval-retrieval` (runs ALL categories; `--category X` to filter).
- Tests: `tests/test_retrieval_fixtures.py`.

The machinery is general — it grades any retrieval property by passage-anchored
facet coverage. "breadth" is just the first category. A new category is a new
JSON file; the runner and tests pick it up automatically.

## What a fixture is

A query plus the ground truth for grading retrieval on it:

- `query` — the user question (Chinese, for the CHS corpus).
- `subtype` — optional, category-specific tag (breadth uses `enumeration` / `broad_theme`); omit if the category has none.
- `expected_coverage` — the **facets** a complete answer must cover (entities, regions, sub-topics, …).
- `relevant_passages` — for each facet, one or more **anchor passages**: short verbatim slices of corpus text identifying a source that attests the facet. A facet is covered if ANY of its passages matches a retrieved source.
- `facet_descriptions` — optional `{facet: "natural-language meaning"}` map, used ONLY by the `--judge` rescue pass to tell the LLM what each facet means. Omit it and the judge falls back to the anchors' `label`s, which are usually descriptive enough; add an explicit entry only when the labels are too terse to judge against.
- `rationale`, `notes`, `known_redundancy` — free text (`known_redundancy` notes near-duplicate sources, else `""`).

The metric: run retrieval, match each anchor against the FULL file content of
every retrieved source, count facets covered at cutoff k. Coverage far below what
the corpus contains is a retrieval gap.

## The non-obvious rules (read these — they are why fixtures go wrong)

1. **Derive ground truth from the CORPUS, never from retrieval output.** Search
   the corpus directly with `rg`. Reading off what retrieval returns is circular —
   you only "find" facets retrieval already surfaces, hiding the misses you want
   to measure.

2. **Every facet needs MULTIPLE anchors from DISTINCT sources.** A facet is
   usually attested in several files with different wording. A single anchor means
   that if retrieval surfaces a *different* valid source, the metric reports a
   FALSE MISS. Add 2-3 alternates per facet from different files.

3. **An anchor is the relevant portion, not the whole chunk** — a short,
   distinctive, verbatim slice. Matching is whitespace-normalized substring
   containment, so it survives re-chunking but must be exact otherwise
   (punctuation 「」… included).

4. **Verify every anchor exists verbatim before committing it** (command below).
   If `rg` can't find it, the text differs from what you typed — fix the anchor.

5. **Distinguish true misses from false misses after running the eval.** For each
   MISSING facet, print the retrieved source paths and `rg` those files for the
   facet's concept. If a retrieved source attests it in other words → false miss;
   add that wording as an alternate anchor. If NO retrieved source attests it →
   genuine retrieval miss; leave it (that is a real finding). The `--judge` flag
   (see below) automates this loop: it asks an LLM whether any retrieved source
   attests each missing facet and persists the supporting span as a new anchor, so
   genuine misses stay misses but false misses self-heal across runs.

6. **Prefer official (in-game) sources; mark non-official ones.** `tps_shishu/` is
   the non-official 诗漱 worldbook → `"official": false`; in-game canon →
   `"official": true`. Some facets are attested only non-officially — worth noting.

7. **`chunk_context` does not affect the metric** — the runner matches each
   source's full file content, so coverage = which files surface, not depth.

8. **Use ATOMIC, single-intent queries.** A retrieval-layer fixture must test
   retrieval, not the upstream question-decomposition layer:

9. **Every anchor's source file must be plausibly reachable from the query.**
   The file should contain tokens from the query (or from likely query rewrites)
   — otherwise the passage anchors a source retrieval has no path to find.
   For example, anchoring a passage from a colleague's log that never mentions
   "卡特" for a query about "卡特的全名" would be invalid: no rewrite starting
   from "卡特" produces a query that lands in that file, so a MISS would measure
   impossibility rather than a retrieval gap. If a file doesn't share any query
   token, find a different source for that facet.
   `pipeline._preprocess_question` splits a compound question into 1-3 sub-queries
   before retrieval, but `eval-retrieval` calls `store.retrieve` directly
   (bypassing it). So a compound query ("七神分别是谁，掌管什么元素与理想") or a
   per-region survey ("…在不同地区分别代表什么") would test a path production never
   uses. Phrase each query as one focused intent ("提瓦特的七位执政官分别是谁？",
   "神之眼代表着什么？"); breadth still arises because that single intent's evidence
   is scattered across many files.

## The corpus

CHS corpus: `text/chs` (the `text/` submodule). In a worktree the submodule is
usually empty — populate it with a shallow clone before searching:

```bash
git submodule update --init --depth 1 text/
```

Files are `agd_<category>/<id>_<name>.txt` (e.g. `agd_character_story/`,
`agd_quest/`, `agd_book/`, `agd_voiceline/`) plus non-official `tps_shishu/`.
Filenames carry names, so they are searchable.

Note: `misc/`, `manifest/`, `metadata/`, and `stats/` are **not** part of the
indexed corpus — `misc/proper_nouns.txt` is a jieba dictionary, not a document,
so do not anchor passages from those directories.

## Procedure

1. **Pick the category.** Adding to an existing category → edit that JSON file.
   New category → create `retrieval_fixtures/<category>.json` with top-level
   `"category": "<category>"` (must equal the filename stem) and `"description"`,
   plus `"fixtures": [...]`.

2. **Pick an atomic query** (one focused retrieval intent — rule 8) and decide its
   facet list (`expected_coverage`). Use Genshin lore knowledge (the `genshin`
   skill) for what a complete answer needs.

3. **For each facet, find anchors with `rg`** (run from the corpus dir):

   ```bash
   cd text/chs
   rg -l "潘塔罗涅" -g'!tps_shishu/**' .                                  # official files attesting the facet
   rg -No "潘塔罗涅卡财务审批卡得非常紧[^\n]{0,30}" agd_book/201154_木偶的笔记本.txt  # pull a verbatim slice
   ```
   `rg`'s regex is on by default — do NOT pass `-E` (in `rg`, `-E` = `--encoding`
   and errors). `-N` drops line numbers, `-o` prints only the match. Take 2-3
   anchors per facet from different files.

4. **Verify every anchor exists verbatim:**

   ```bash
   cd text/chs
   chk() { rg -q -- "$1" "$2" && echo "OK   $1" || echo "MISS $1"; }
   chk "潘塔罗涅卡财务审批卡得非常紧" agd_book/201154_木偶的笔记本.txt
   ```

5. **Add the fixture(s)** to the category JSON (schema below). One passage may
   cover several facets (multiple entries in `covers`); a facet may have several
   passages.

6. **Validate structure:**

   ```bash
   uv run pytest tests/test_retrieval_fixtures.py -q
   uv run mypy istaroth/rag/eval/retrieval.py
   ```

7. **Run the eval against production config:**

   ```bash
   set -a; source .env.common; source .env.web; set +a   # cohere key is CO_API_KEY (NOT COHERE_API_KEY); deepinfra key for embeddings
   uv run python scripts/rag_tools.py eval-retrieval --repeat 3
   # add --category <name> to run just one category
   ```
   The eval defaults to the most generous production preset (**thorough: k=10,
   chunk_context=5**) and retrieves at that actual k, so the candidate pool matches
   production. Other presets (frontend `QueryForm.tsx`): fast k=4, balanced k=7.
   Reranker `cohere`, query transformer `rewrite`. `rewrite` is LLM-driven and
   **non-deterministic** — a facet's rank wobbles run-to-run; use `--repeat N`
   (reports mean coverage + per-facet hit rate) rather than trusting one run.

8. **Harden against false misses** (rule 5). For each MISSING facet:

   ```bash
   set -a; source .env.common; source .env.web; set +a
   uv run python - <<'PY'
   from istaroth.rag import document_store_set
   ss = document_store_set.DocumentStoreSet.from_env()
   store = ss.get_store(ss.available_languages[0])
   out = store.retrieve("<your query>", k=10, chunk_context=5)  # thorough preset
   for i,(s,docs) in enumerate(out.results,1):
       print(i, docs[0].metadata["path"])
   PY
   ```
   Then `rg` the listed files for the facet's concept; if one attests it, add that
   wording as an alternate anchor and re-run step 7.

## Automating false-miss hardening with the LLM judge

`eval-retrieval --judge` adds a rescue pass after the deterministic anchor match.
For every facet still MISSING in a fixture, it makes ONE call to a cheap model
(DeepSeek V4 Flash on DeepInfra, OpenAI-compatible; needs `DEEPINFRA_API_KEY`)
with the query, the union of retrieved sources, and each missing facet's
description. The model copies a short verbatim span from the sources that attests
the facet, or returns nothing if none does. Each span is then verified to actually
occur in a retrieved source (hallucinated spans are dropped) and, by default,
persisted back into the fixture JSON as a new anchor labelled `judge:<path>` with
`official` inferred from the source path. So the judge fires once per false miss;
on the next run the deterministic matcher catches it for free.

```bash
set -a; source .env.common; source .env.web; set +a
uv run python scripts/rag_tools.py eval-retrieval --judge --repeat 3
# --no-judge-write   judge but don't persist (dry run)
# --judge-model X    override the DeepInfra model id
```

Review the persisted anchors in `git diff` before committing — the span must
genuinely attest the facet, not merely co-occur with it. A judge that never fires
means either coverage is already complete or anchors/descriptions are too sparse
for it to work with.

## Fixture JSON schema

File: `retrieval_fixtures/<category>.json`

```json
{
  "category": "breadth",
  "description": "What retrieval property this category probes.",
  "captured_at": "YYYY-MM-DD",
  "capture_method": "How ground truth was derived (corpus search, etc.).",
  "caveat": "Matching/measurement caveats.",
  "fixtures": [
    {
      "query": "提瓦特的七位执政官分别是谁？",
      "language": "CHS",
      "subtype": "enumeration",
      "rationale": "Why this atomic query stresses the property (1-3 sentences).",
      "expected_coverage": ["venti_anemo", "zhongli_geo", "..."],
      "relevant_passages": [
        {"passage": "<verbatim slice>", "label": "<who/what + source>", "official": true, "covers": ["venti_anemo"]}
      ],
      "facet_descriptions": {"venti_anemo": "<optional: what this facet means, for the --judge pass>"},
      "known_redundancy": "",
      "notes": ""
    }
  ]
}
```

Loader enforces (a failing test means one is violated): the file's `category`
equals its filename stem; facet names in `expected_coverage` are unique; every
`covers` entry names a known facet; every passage covers ≥1 facet; every expected
facet is covered by ≥1 passage; every `facet_descriptions` key names a known
facet. `subtype`, `facet_descriptions`, `known_redundancy`, `notes` are optional.
