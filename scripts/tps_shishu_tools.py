#!/usr/bin/env python3
"""TPS Shishu manual extraction and generation tools.

Usage:

  # Step 1 (can run on a separate machine with GPU):
  python scripts/tps_shishu_tools.py extract manual.pdf tmp/manual.md

  # Step 2 (split + manifest):
  python scripts/tps_shishu_tools.py generate tmp/manual.md text/chs/
"""

import pathlib
import shutil
import sys

import click

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth import utils
from istaroth.text import manifest
from istaroth.text import types as text_types
from istaroth.tps.shishu import extraction, split


@click.group()
def main() -> None:
    """Shishu (诗漱) Genshin lore manual tools."""
    pass


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.argument("output", type=click.Path(path_type=pathlib.Path))
def extract(pdf_path: pathlib.Path, output: pathlib.Path) -> None:
    """Convert PDF to markdown."""
    md_text = extraction.pdf_to_markdown(pdf_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(md_text, encoding="utf-8")
    click.echo(f"Wrote {len(md_text):,} chars to {output}")


@main.command()
@click.argument("md_path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.argument("output_dir", type=click.Path(path_type=pathlib.Path))
@click.option("-f", "--force", is_flag=True, help="Overwrite existing tps_shishu dir")
def generate(md_path: pathlib.Path, output_dir: pathlib.Path, force: bool) -> None:
    """Split extracted markdown into chapters and write manifest.

    MD_PATH is the markdown file produced by the extract command.
    OUTPUT_DIR is the language-specific text directory (e.g. text/chs/).
    """
    category_dir = output_dir / text_types.TextCategory.TPS_SHISHU.value
    if category_dir.exists():
        if not force:
            raise click.ClickException(
                f"{category_dir} already exists. Use -f to overwrite."
            )
        shutil.rmtree(category_dir)
    category_dir.mkdir(parents=True, exist_ok=True)

    chapters = split.split_markdown_by_headings(md_path)

    manifest_list: list[text_types.TextMetadata] = []
    pad = len(str(len(chapters)))
    for idx, (title, content) in enumerate(chapters, start=1):
        part = utils.make_safe_filename_part(title, max_length=75) or "untitled"
        relative_path = (
            f"{text_types.TextCategory.TPS_SHISHU.value}/{idx:0{pad}d}_{part}.md"
        )
        (output_dir / relative_path).write_text(content + "\n", encoding="utf-8")
        manifest_list.append(
            text_types.TextMetadata(
                category=text_types.TextCategory.TPS_SHISHU,
                title=title,
                id=idx,
                relative_path=relative_path,
            )
        )

    manifest_path = manifest.write_manifest(
        output_dir, manifest_list, name=text_types.TextCategory.TPS_SHISHU.value
    )
    click.echo(
        f"{len(chapters)} chapters written to {category_dir}\n"
        f"Manifest written to {manifest_path} ({len(manifest_list)} entries)"
    )


if __name__ == "__main__":
    main()
