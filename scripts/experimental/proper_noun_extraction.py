#!/usr/bin/env python3
"""Batch extract proper nouns from game text using Gemini, with checkpointing."""

import argparse
import asyncio
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from istaroth import llm_manager, logging_utils
from istaroth.text import proper_noun_extraction

logging_utils.setup_logging()
_log = logging.getLogger(__name__)

_SKIP_DIRS = {"manifest", "stats", "misc"}

_CHECKPOINT_DIR = pathlib.Path("tmp/proper_noun_extraction")
_OUTPUT_PATH = pathlib.Path("text/chs/misc/proper_nouns.txt")


def _discover_files(*, dirs: list[str] | None = None) -> list[pathlib.Path]:
    if dirs:
        return sorted(p for d in dirs for p in pathlib.Path(d).rglob("*.txt"))
    return sorted(
        p
        for p in pathlib.Path("text/chs").rglob("*.txt")
        if p.parts[2] not in _SKIP_DIRS
    )


def _load_checkpoint(progress_file: pathlib.Path) -> dict[str, list[str]]:
    """Load completed files from checkpoint. Returns {relative_path: [nouns]}."""
    completed: dict[str, list[str]] = {}
    if not progress_file.exists():
        return completed
    for line in progress_file.read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            completed[record["file"]] = record["nouns"]
    return completed


def _write_output(completed: dict[str, list[str]]) -> None:
    all_nouns = sorted({noun for nouns in completed.values() for noun in nouns})
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text("\n".join(all_nouns) + "\n")
    _log.info(f"Wrote {len(all_nouns)} unique proper nouns to {_OUTPUT_PATH}")


async def _process_file(
    filepath: pathlib.Path, *, llm, semaphore: asyncio.Semaphore
) -> tuple[str, list[str]]:
    async with semaphore:
        text = filepath.read_text()
        nouns = await proper_noun_extraction.extract_proper_nouns(text, llm=llm)
        return str(filepath), nouns


async def _run(args: argparse.Namespace) -> None:
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = _CHECKPOINT_DIR / "progress.jsonl"

    if args.restart and progress_file.exists():
        progress_file.unlink()
        _log.info("Cleared checkpoint")

    completed = _load_checkpoint(progress_file)
    all_files = _discover_files(dirs=args.dirs)
    _log.info(f"Found {len(all_files)} files, {len(completed)} already completed")

    remaining = [f for f in all_files if str(f) not in completed]
    if not remaining:
        _log.info("All files already processed")
        _write_output(completed)
        return

    llm = llm_manager.create_llm(args.model)
    semaphore = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()

    async def _process_and_save(filepath: pathlib.Path, pf) -> None:
        try:
            file_str, nouns = await _process_file(
                filepath, llm=llm, semaphore=semaphore
            )
        except Exception as exc:
            _log.error(f"FAILED {filepath}: {exc}")
            return
        async with lock:
            record = {"file": file_str, "nouns": nouns}
            pf.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            pf.flush()
            completed[file_str] = nouns
            _log.info(
                f"[{len(completed)}/{len(all_files)}] {filepath} ({len(nouns)} nouns)"
            )

    with open(progress_file, "a") as pf:
        await asyncio.gather(*(_process_and_save(f, pf) for f in remaining))

    _write_output(completed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract proper nouns from game text")
    parser.add_argument(
        "--model",
        default="gemini-3-flash-preview",
        help="Model to use (default: gemini-3-flash-preview)",
    )
    parser.add_argument(
        "--restart", action="store_true", help="Discard checkpoint and start fresh"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of parallel API calls (default: 10)",
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        help="Directories to process (e.g. text/chs/agd_book text/chs/agd_quest)",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
