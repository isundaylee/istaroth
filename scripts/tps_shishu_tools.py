#!/usr/bin/env python3
"""TPS Shishu manual generation tools.

Usage:

  # Download the published markdown chapters, clean them, and write the manifest:
  python scripts/tps_shishu_tools.py generate text/chs/
"""

import pathlib
import shutil
import sys

import click
import httpx

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth import utils
from istaroth.text import manifest
from istaroth.text import types as text_types
from istaroth.tps.shishu import clean, source


@click.group()
def main() -> None:
    """Shishu (诗漱) Genshin lore manual tools."""
    pass


@main.command()
@click.argument("output_dir", type=click.Path(path_type=pathlib.Path))
@click.option("-f", "--force", is_flag=True, help="Overwrite existing tps_shishu dir")
def generate(output_dir: pathlib.Path, force: bool) -> None:
    """Download chapters from the source site, clean them, and write the manifest.

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

    with httpx.Client(timeout=60.0) as client:
        stems = source.list_chapter_stems(client=client)
        manifest_list: list[text_types.TextMetadata] = []
        pad = len(str(len(stems)))
        for idx, stem in enumerate(stems, start=1):
            title, content = clean.clean_chapter(source.download(stem, client=client))
            part = utils.make_safe_filename_part(title, max_length=75) or "untitled"
            relative_path = (
                f"{text_types.TextCategory.TPS_SHISHU.value}/{idx:0{pad}d}_{part}.md"
            )
            (output_dir / relative_path).write_text(content, encoding="utf-8")
            manifest_list.append(
                text_types.TextMetadata(
                    category=text_types.TextCategory.TPS_SHISHU,
                    title=title,
                    id=idx,
                    relative_path=relative_path,
                    min_version=None,
                    max_version=None,
                )
            )

    manifest_path = manifest.write_manifest(
        output_dir, manifest_list, name=text_types.TextCategory.TPS_SHISHU.value
    )
    click.echo(
        f"{len(manifest_list)} chapters written to {category_dir}\n"
        f"Manifest written to {manifest_path} ({len(manifest_list)} entries)"
    )


if __name__ == "__main__":
    main()
