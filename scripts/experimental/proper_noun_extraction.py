#!/usr/bin/env python3
"""Batch extract proper nouns from game text using Gemini, with checkpointing."""

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from langchain_core import messages

from istaroth import llm_manager, logging_utils

logging_utils.setup_logging()
_log = logging.getLogger(__name__)

_SKIP_DIRS = {"manifest", "stats", "misc"}

_SYSTEM_PROMPT = """\
你是一个专门从文本中提取专有名词的工具。请从给定文本中提取所有专有名词，包括：
- 人名（角色、历史人物、神明等）
- 地名（城市、区域、遗迹、自然地标等）
- 组织名（骑士团、教会、势力等）
- 特殊物品名（武器、圣遗物、书名等）
- 种族/物种名
- 事件名（战争、仪式等）
- 头衔/称号

规则：
- 每行输出一个专有名词，不要编号
- 只输出原文中出现的原始文本，不要翻译或解释
- 不要输出普通名词或形容词
- 不要输出任何说明文字"""

_CHECKPOINT_DIR = pathlib.Path("tmp/proper_noun_extraction")
_OUTPUT_PATH = pathlib.Path("text/chs/misc/proper_nouns.txt")


def _discover_files() -> list[pathlib.Path]:
    files = []
    for p in sorted(pathlib.Path("text/chs").rglob("*.txt")):
        if p.parts[2] not in _SKIP_DIRS:
            files.append(p)
    return files


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


def _extract_proper_nouns(text: str, *, llm) -> list[str]:
    response = llm.invoke(
        [
            messages.SystemMessage(content=_SYSTEM_PROMPT),
            messages.HumanMessage(content=text),
        ]
    )
    raw = llm_manager.extract_text_from_response(response)
    return [line.strip() for line in raw.strip().splitlines() if line.strip()]


def _write_output(completed: dict[str, list[str]]) -> None:
    all_nouns = sorted({noun for nouns in completed.values() for noun in nouns})
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text("\n".join(all_nouns) + "\n")
    _log.info(f"\nWrote {len(all_nouns)} unique proper nouns to {_OUTPUT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract proper nouns from game text")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Model to use (default: gemini-2.5-flash)")
    parser.add_argument("--restart", action="store_true", help="Discard checkpoint and start fresh")
    args = parser.parse_args()

    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = _CHECKPOINT_DIR / "progress.jsonl"

    if args.restart and progress_file.exists():
        progress_file.unlink()
        _log.info("Cleared checkpoint")

    completed = _load_checkpoint(progress_file)
    all_files = _discover_files()
    _log.info(f"Found {len(all_files)} files, {len(completed)} already completed")

    remaining = [f for f in all_files if str(f) not in completed]
    if not remaining:
        _log.info("All files already processed")
        _write_output(completed)
        return

    llm = llm_manager.create_llm(args.model)

    with open(progress_file, "a") as pf:
        for i, filepath in enumerate(remaining, 1):
            try:
                text = filepath.read_text()
                nouns = _extract_proper_nouns(text, llm=llm)
                record = {"file": str(filepath), "nouns": nouns}
                pf.write(json.dumps(record, ensure_ascii=False) + "\n")
                pf.flush()
                completed[str(filepath)] = nouns
                total_done = len(completed)
                _log.info(f"[{total_done}/{len(all_files)}] {filepath} ({len(nouns)} nouns)")
            except Exception:
                _log.exception(f"[{len(completed)}/{len(all_files)}] FAILED {filepath}")

    _write_output(completed)


if __name__ == "__main__":
    main()
