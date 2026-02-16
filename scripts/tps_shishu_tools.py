#!/usr/bin/env python3
"""TPS Shishu manual extraction and split tools.

Example - run stages individually:

  python scripts/tps_shishu_tools.py extract manual.pdf out/manual.md
  python scripts/tps_shishu_tools.py split-chapters out/manual.md out/chapters
"""

import pathlib
import sys

import click

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.tps.shishu import extraction, split


@click.group()
def main() -> None:
    """Shishu (诗漱) Genshin lore manual tools."""
    pass


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.argument("output", type=click.Path(path_type=pathlib.Path))
@click.option("--progress/--no-progress", default=True, help="Show conversion progress")
def extract(pdf_path: pathlib.Path, output: pathlib.Path, progress: bool) -> None:
    """Convert PDF to markdown."""
    md_text = extraction.pdf_to_markdown(pdf_path, show_progress=progress)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(md_text, encoding="utf-8")
    click.echo(f"Wrote {len(md_text):,} chars to {output}")


@main.command()
@click.argument("md_path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.argument("out_dir", type=click.Path(path_type=pathlib.Path))
def split_chapters(md_path: pathlib.Path, out_dir: pathlib.Path) -> None:
    """Split markdown into one file per heading."""
    n = split.split_markdown_by_headings(md_path, out_dir)
    click.echo(f"Wrote {n} files to {out_dir}")


if __name__ == "__main__":
    main()
