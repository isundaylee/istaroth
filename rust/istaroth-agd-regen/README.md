# istaroth-agd-regen (Rust prototype)

Prototype rewrite of `scripts/agd_tools.py generate-all` for the **CHS** corpus,
built to estimate the performance floor of a Rust port. Output is
**byte-identical** to the Python pipeline for all 19 `agd_*` content
directories, `manifest/agd.json`, `metadata/agd/hierarchy.json`, and the
`stats/agd/*` diagnostics (`metadata.json`, `summary_table.txt`,
`unused_stats.json`, `parsing_issues.json`/`.info`, `errors.info`).

Structured as a library (`src/lib.rs`, entry point `generate::generate_all`)
plus a thin clap CLI (`src/main.rs`).

Also includes `build-first-seen`, a port of `scripts/agd_build_first_seen.py`:
a full `--rebuild-all` reproduces every committed `text/first_seen/*.json`
byte-identically in ~7 s (snapshot scans run in parallel).

## Run

```bash
source .env.common   # AGD_PATH
cargo build --release --manifest-path rust/Cargo.toml
# from the repo root, so text/first_seen resolves (or set FIRST_SEEN_DIR)
./rust/target/release/istaroth-agd-regen generate-all -f tmp-local/rust-chs
# -v additionally prints per-phase [load] timing details

# first-seen delta files (writes to FIRST_SEEN_DIR, default text/first_seen):
./rust/target/release/istaroth-agd-regen build-first-seen [--rebuild-all]
```

## Build times (part of the iteration loop)

| build | time |
|---|---|
| cold `--profile fast` (after `cargo clean`, deps included) | ~15 s |
| cold `--release` | ~20 s |
| incremental `--profile fast` (opt, no LTO, incremental codegen) | **~1 s** |
| incremental `--release` (touch one file; thin-LTO relink dominates) | ~15 s |
| `cargo check` | ~6 s |

Use `--profile fast` for everything: it inherits release (same opt-level,
debug-assertions off), dropping only thin-LTO/low codegen-units — and this
workload (I/O + serde parsing + git subprocesses + allocator) doesn't benefit
from those: measured runtime is identical to release within noise (~2.8–2.9 s),
and output is byte-identical. The `release` profile is kept only as the
LTO'd variant if binary size ever matters. Day-to-day iteration is
edit → ~1 s build → ~2.9 s run (~4 s total, vs ~17 s run for Python with no
build step).

## Verify against Python

```bash
uv run --isolated --python 3.14t --only-group regen \
  scripts/agd_tools.py generate-all -f tmp-local/ref-chs
diff -rq tmp-local/ref-chs tmp-local/rust-chs   # whole tree incl. stats/agd
```

(`stats/agd/metadata.json` matches only when both runs share the same istaroth
HEAD/dirty state.)

## Results (16-core host, warm page cache, 2026-07)

| | wall time |
|---|---|
| Python (3.14t free-threaded, this repo) | ~16.9 s |
| Rust prototype | ~2.8 s (**~6×**) |

Rust breakdown: ~1.5 s data loading (critical path: `git show` of the three
fallback TextMaps and the excel parses), ~1.0 s all 19 rendering passes,
~0.3 s startup + file writes. Plausible further floor with typed excel parsing
everywhere and a cached fallback-TextMap sidecar: ~1.5–2 s.

## Fidelity notes

- Python-quirk emulation lives in: `pyset.rs` (CPython int-set iteration order,
  visible in orphaned-dialog listings and branch-wait picks), `util.rs`
  (`str.strip`/`str.title`/`\w` regex semantics, code-point slicing),
  `talk.rs` (`_process_branch` ported line-by-line incl. Python `or`
  truthiness and first-maximal `max()` semantics), and IndexMap use wherever
  Python dict insertion order reaches the output.
- Access tracking mirrors Python's `TrackingScope`: per-item `Scope`s collect
  talk/readable ids (cross-pass exclusion), text-map hashes (unused stats),
  and non-fatal parsing issues; a failed item's accesses and issues are
  dropped, and load-time (Python: parent-scope) accesses fold in only after
  all passes. `talkparse.rs` and the chapter hidden-check use untracked
  lookups, and hierarchy building discards its scope — all matching Python.
- The output language is a `lang::Language` config (only `Chs` implemented;
  the CHS source map doubles as the output map). An ENG port needs the
  source/output map split, localized render strings, and non-CHS error
  handling.
- Intentional divergence from Python: per-type error limits are NOT enforced.
  Any per-item failure is logged to `errors.info`, the item is skipped, and
  the run exits 1 at the end; Python instead aborts a pass once its per-type
  limit is exceeded. There is also no `--only`/`--sample-rate`/`--strict`/
  `--allow-errors` — the CLI is deliberately minimal (`-f`, `-v`).
- BinOutput/Quest duplicate resolution scans paths in sorted order (Python
  uses unsorted filesystem order; the canonical-name rule makes the result
  order-independent in practice).
